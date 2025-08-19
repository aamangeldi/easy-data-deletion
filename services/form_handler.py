"""Form handling service for web-based broker interactions."""
import time
from typing import Dict, Optional
from dataclasses import dataclass
from playwright.sync_api import Page

from utils import (solve_captcha, extract_auth_tokens,
                   substitute_template_variables)
from utils.gmail import check_confirmation_email, get_gmail_service


@dataclass
class SubmissionResult:
    """Result of form submission operation."""
    success: bool
    message: str
    response_data: Optional[Dict] = None
    status_code: Optional[int] = None
    submission_time: Optional[float] = None


class FormSubmissionError(Exception):
    """Raised when form submission fails."""

    def __init__(self,
                 message: str,
                 status_code: int = None,
                 response_data: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class FormHandler:
    """Handles web form submission for broker data deletion requests."""

    def submit_web_form(self, config: Dict, user_data: Dict,
                        page: Page) -> SubmissionResult:
        """Submit web form using deterministic configuration.
        
        Args:
            config: Broker configuration with form submission details
            user_data: User data dictionary  
            page: Playwright page instance
            
        Returns:
            SubmissionResult with outcome details
            
        Raises:
            FormSubmissionError: If submission fails with unrecoverable error
        """
        try:
            submission_config = config['form_config']['submission']

            # Handle CAPTCHA if required
            if submission_config.get('requires_captcha'):
                user_data = self._handle_captcha(config, user_data)

            # Extract authentication tokens if required
            auth_data = self._extract_auth_tokens(submission_config, page)

            # Prepare and submit request
            submission_time = time.time()
            response = self._submit_request(submission_config, user_data,
                                            auth_data, page)

            if response.status_code in [200, 201]:
                return SubmissionResult(
                    success=True,
                    message=
                    f"Form submitted successfully with status {response.status_code}",
                    response_data=response.json() if response.text else {},
                    status_code=response.status_code,
                    submission_time=submission_time)
            else:
                return SubmissionResult(
                    success=False,
                    message=
                    f"Form submission failed with status {response.status_code}",
                    response_data=response.text,
                    status_code=response.status_code,
                    submission_time=submission_time)

        except Exception as e:
            raise FormSubmissionError(
                f"Form submission error: {str(e)}",
                status_code=getattr(e, 'status_code', None),
                response_data=getattr(e, 'response_data', None))

    def check_email_confirmation(self,
                                 config: Dict,
                                 user_data: Dict,
                                 submission_time: float,
                                 wait_time: int = 300) -> Dict:
        """Check for email confirmation after form submission.
        
        Args:
            config: Broker configuration  
            user_data: User data dictionary
            submission_time: Unix timestamp when form was submitted
            wait_time: Seconds to wait for confirmation email
            
        Returns:
            Confirmation check result dictionary
        """
        try:
            gmail_service = get_gmail_service()
            domains = config.get('email_domains', [])

            if not domains:
                return {
                    "status":
                    "warning",
                    "message":
                    f"No email domains configured for {config['name']}",
                    "recommendations": [
                        f"Add 'email_domains' array to {config['name']} configuration",
                        "Check broker documentation for confirmation email domains"
                    ]
                }

            confirmed = check_confirmation_email(service=gmail_service,
                                                 user_email=user_data['email'],
                                                 from_domains=domains,
                                                 wait_time=wait_time,
                                                 after_time=submission_time)

            return {
                "status":
                "success",
                "confirmed":
                confirmed,
                "message":
                "Confirmation email found"
                if confirmed else "No confirmation email received"
            }

        except Exception as e:
            return {
                "status":
                "error",
                "message":
                f"Error checking confirmation email: {str(e)}",
                "recommendations": [
                    "Check Gmail API credentials and permissions",
                    "Verify email address has access to Gmail",
                    "Check network connectivity"
                ]
            }

    def _handle_captcha(self, config: Dict, user_data: Dict) -> Dict:
        """Handle CAPTCHA solving if required.
        
        Args:
            config: Broker configuration
            user_data: User data dictionary
            
        Returns:
            Updated user_data with captcha_response
            
        Raises:
            FormSubmissionError: If CAPTCHA solving fails
        """
        print("Solving CAPTCHA...")

        captcha_config = config.get('captcha_config', {})
        website_key = captcha_config.get('website_key')
        website_url = config.get('url')

        if not website_key:
            raise FormSubmissionError(
                f"CAPTCHA required but no website_key found in config for {config.get('name')}",
                recovery_suggestions=[
                    f"Add 'captcha_config.website_key' to {config.get('name')} configuration",
                    "Inspect page source to find reCAPTCHA site key"
                ])

        captcha_response = solve_captcha(website_url, website_key)
        if not captcha_response:
            raise FormSubmissionError(
                "CAPTCHA solving failed",
                recovery_suggestions=[
                    "Check ANTICAPTCHA_API_KEY environment variable",
                    "Verify anti-captcha service account has credits",
                    "Try manual submission as fallback"
                ])

        user_data['captcha_response'] = captcha_response
        print("CAPTCHA solved successfully")
        return user_data

    def _extract_auth_tokens(self, submission_config: Dict,
                             page: Page) -> Dict:
        """Extract authentication tokens if required.
        
        Args:
            submission_config: Form submission configuration
            page: Playwright page instance
            
        Returns:
            Dictionary with extracted authentication data
        """
        auth_data = {}

        if submission_config.get('requires_jwt'):
            print("Extracting authentication tokens...")
            auth_data = extract_auth_tokens(page)

            if auth_data.get('jwtToken'):
                print(
                    f"JWT token found from: {auth_data.get('jwtTokenSource', 'unknown')}"
                )

        return auth_data

    def _submit_request(self, submission_config: Dict, user_data: Dict,
                        auth_data: Dict, page: Page):
        """Submit the actual HTTP request.
        
        Args:
            submission_config: Form submission configuration
            user_data: User data dictionary
            auth_data: Authentication data
            page: Playwright page instance
            
        Returns:
            HTTP response object
        """
        import requests

        # Prepare payload using template
        payload = substitute_template_variables(
            submission_config['payload_template'], user_data)

        # Prepare headers
        headers = submission_config['headers'].copy()
        headers['referer'] = page.url

        # Add authentication tokens
        if auth_data.get('jwtToken'):
            headers['Authorization'] = f'Bearer {auth_data["jwtToken"]}'
            payload['jwtToken'] = auth_data['jwtToken']
            print("Added JWT token to request")

        if auth_data.get('csrfToken'):
            headers['X-CSRF-Token'] = auth_data['csrfToken']
            print("Added CSRF token to request")

        if auth_data.get('cookies'):
            headers['Cookie'] = auth_data['cookies']
            print("Added cookies to request")

        # Submit form
        print(f"Submitting form to {submission_config['endpoint']}")
        print(f"Request headers: {len(headers)} headers")
        print(f"Payload size: {len(str(payload))} characters")

        # Print auth status for debugging
        if auth_data.get('jwtToken'):
            print(
                f"✓ JWT token included (length: {len(auth_data['jwtToken'])})")
        else:
            print("⚠ No JWT token found")

        response = requests.post(submission_config['endpoint'],
                                 json=payload,
                                 headers=headers)

        print(f"Response status: {response.status_code}")
        if response.status_code not in [200, 201]:
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response body: {response.text[:500]}...")

        return response
