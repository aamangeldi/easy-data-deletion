"""Generic broker data deletion automation script."""
import argparse
import json
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv
from typing import Dict, List

from utils import (get_gmail_service, create_browser_context, take_screenshot,
                   solve_captcha, validate_state_input, extract_auth_tokens,
                   prepare_user_data, validate_date_of_birth,
                   substitute_template_variables, analyze_form,
                   fill_form_deterministically)
from utils.constrained_ai import ConstrainedFormMapper, generate_broker_config, save_discovered_config

# Load environment variables
load_dotenv()


def handle_web_form_submission(config: Dict, user_data: Dict, page) -> Dict:
    """Handle deterministic web form submission using broker config.
    
    Args:
        config: Broker configuration
        user_data: User data dictionary
        page: Playwright page instance
        
    Returns:
        Submission result dictionary
    """
    submission_config = config['form_config']['submission']

    # Solve CAPTCHA if required
    if submission_config.get('requires_captcha'):
        print("Solving CAPTCHA...")

        # Get CAPTCHA config from broker configuration
        captcha_config = config.get('captcha_config', {})
        website_key = captcha_config.get('website_key')
        website_url = config.get('url')

        if not website_key:
            raise ValueError(
                f"CAPTCHA required but no website_key found in config for {config.get('name')}"
            )

        captcha_response = solve_captcha(website_url, website_key)
        if not captcha_response:
            raise ValueError("CAPTCHA solving failed")
        user_data['captcha_response'] = captcha_response
        print("CAPTCHA solved successfully")

    # Extract auth tokens if required
    auth_data = {}
    if submission_config.get('requires_jwt'):
        print("Extracting authentication tokens...")
        auth_data = extract_auth_tokens(page)
        if auth_data.get('jwtToken'):
            print(
                f"JWT token found from: {auth_data.get('jwtTokenSource', 'unknown')}"
            )

    # Prepare payload using template
    payload = substitute_template_variables(
        submission_config['payload_template'], user_data)

    # Prepare headers
    headers = submission_config['headers'].copy()
    headers['referer'] = page.url

    # Add authentication tokens
    if auth_data.get('jwtToken'):
        headers['Authorization'] = f'Bearer {auth_data["jwtToken"]}'
        payload['jwtToken'] = auth_data[
            'jwtToken']  # KEY FIX: Add JWT to payload
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
        print(f"✓ JWT token included (length: {len(auth_data['jwtToken'])})")
    else:
        print("⚠ No JWT token found")

    # Record submission time for email checking
    import time
    submission_time = time.time()

    response = requests.post(submission_config['endpoint'],
                             json=payload,
                             headers=headers)

    print(f"Response status: {response.status_code}")
    if response.status_code not in [200, 201]:
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text[:500]}...")  # First 500 chars

    if response.status_code in [200, 201]:
        return {
            "status": "success",
            "response": response.json() if response.text else {},
            "message":
            f"Form submitted successfully with status {response.status_code}",
            "submission_time": submission_time
        }
    else:
        return {
            "status": "error",
            "status_code": response.status_code,
            "response": response.text,
            "message":
            f"Form submission failed with status {response.status_code}",
            "submission_time": submission_time
        }


def handle_email_request(config: Dict, user_data: Dict) -> Dict:
    """Handle email-based deletion request.
    
    Args:
        config: Broker configuration
        user_data: User data dictionary
        
    Returns:
        Email sending result dictionary
    """
    # This would use the existing email functionality
    # For now, return a placeholder
    return {
        "status": "success",
        "message": "Email-based deletion request would be sent here"
    }


def check_email_confirmation(config: Dict,
                             user_data: Dict,
                             submission_time: float,
                             wait_time: int = 300) -> Dict:
    """Check for email confirmation from the broker.
    
    Args:
        config: Broker configuration
        user_data: User data dictionary
        submission_time: Unix timestamp when the form was submitted
        wait_time: Time to wait for confirmation email
        
    Returns:
        Confirmation check result
    """
    from utils.gmail import check_confirmation_email

    try:
        gmail_service = get_gmail_service()
        domains = config.get('email_domains', [])

        if not domains:
            return {
                "status": "warning",
                "message": f"No email domains configured for {config['name']}"
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
            "status": "error",
            "message": f"Error checking confirmation email: {str(e)}"
        }


def get_all_broker_configs() -> List[Dict]:
    """Get all broker configurations from the broker_configs directory.
    
    Returns:
        List of broker configuration dictionaries
    """
    config_dir = Path(__file__).parent / 'broker_configs'
    configs = []

    if not config_dir.exists():
        print(f"Warning: {config_dir} directory not found")
        return configs

    for config_file in config_dir.glob('*.json'):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                configs.append(config)
        except Exception as e:
            print(f"Error loading {config_file}: {e}")

    return configs


def is_minimal_config(config: Dict) -> bool:
    """Determine if a broker config is minimal (requires AI fallback).
    
    Args:
        config: Broker configuration dictionary
        
    Returns:
        True if config is minimal and needs AI fallback
    """
    # Check if it has the full form_config with submission details
    form_config = config.get('form_config', {})
    submission = form_config.get('submission', {})

    # Minimal config if missing key submission components
    if not submission.get('method') or not submission.get('endpoint'):
        return True

    # Minimal config if missing field mappings
    if not form_config.get('field_mappings'):
        return True

    return False


def run_broker_deletion(first_name: str,
                        last_name: str,
                        email: str,
                        date_of_birth: str = None,
                        address: str = None,
                        city: str = None,
                        state: str = None,
                        zip_code: str = None,
                        broker_filter: str = None):
    """Run data deletion flow for all brokers.
    
    Args:
        first_name: User's first name
        last_name: User's last name
        email: User's email address
        date_of_birth: User's date of birth (optional)
        address: User's address (optional)  
        city: User's city (optional)
        state: User's state (optional)
        zip_code: User's ZIP code (optional)
        broker_filter: Optional broker name to process only that broker
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    # Get all broker configurations
    configs = get_all_broker_configs()

    if not configs:
        print("No broker configurations found in broker_configs directory")
        return

    # Filter to specific broker if requested
    if broker_filter:
        configs = [
            c for c in configs
            if c.get('name', '').lower() == broker_filter.lower()
        ]
        if not configs:
            print(f"No configuration found for broker: {broker_filter}")
            return

    print(f"\n=== Processing {len(configs)} broker(s) ===")

    successful_deletions = []
    failed_deletions = []

    for config in configs:
        broker_name = config.get('name', 'Unknown')
        print(f"\n{'='*60}")
        print(f"Processing: {broker_name}")
        print(f"{'='*60}")

        try:
            # Determine if this is a minimal config requiring AI fallback
            use_ai_fallback = is_minimal_config(config)

            if use_ai_fallback:
                print(
                    f"🤖 Using AI fallback for {broker_name} (minimal config)")
                # Prepare basic user data for AI
                user_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'date_of_birth': date_of_birth,
                    'address': address,
                    'city': city,
                    'state': state,
                    'zip_code': zip_code
                }
                # Remove None values
                user_data = {
                    k: v
                    for k, v in user_data.items() if v is not None
                }

                # Handle AI fallback
                result = handle_ai_fallback_flow(config, user_data)
                if result:
                    successful_deletions.append(broker_name)
                else:
                    failed_deletions.append(broker_name)
            else:
                print(f"✓ Using deterministic config for {broker_name}")
                # Prepare formatted user data
                user_data = prepare_user_data(config,
                                              first_name=first_name,
                                              last_name=last_name,
                                              email=email,
                                              date_of_birth=date_of_birth,
                                              address=address,
                                              city=city,
                                              state=state,
                                              zip_code=zip_code)

                # Handle deterministic flow
                result = handle_deterministic_flow(config, user_data)
                if result:
                    successful_deletions.append(broker_name)
                else:
                    failed_deletions.append(broker_name)

        except Exception as e:
            print(f"❌ Error processing {broker_name}: {str(e)}")
            failed_deletions.append(broker_name)

    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total brokers processed: {len(configs)}")
    print(f"Successful: {len(successful_deletions)}")
    print(f"Failed: {len(failed_deletions)}")

    if successful_deletions:
        print(f"\n✓ Successful deletions:")
        for broker in successful_deletions:
            print(f"  - {broker}")

    if failed_deletions:
        print(f"\n❌ Failed deletions:")
        for broker in failed_deletions:
            print(f"  - {broker}")


def handle_deterministic_flow(config: Dict, user_data: Dict) -> bool:
    """Handle deterministic flow for fully configured brokers.
    
    Args:
        config: Broker configuration
        user_data: User data dictionary
        
    Returns:
        True if successful, False otherwise
    """
    broker_name = config.get('name', 'Unknown')

    # Handle based on broker type
    if config['type'] == 'web_form':
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = create_browser_context(browser)
            page = context.new_page()

            try:
                print(
                    f"\n=== Starting {config['name']} Data Deletion Flow ===")

                # Navigate to the form
                print(f"Navigating to {config['name']} deletion form...")
                page.goto(config['url'])
                page.wait_for_load_state('networkidle')

                # Take initial screenshot
                take_screenshot(page, f"{broker_name.lower()}_form_initial")

                # Handle form submission
                result = handle_web_form_submission(config, user_data, page)

                # Take screenshot after submission
                take_screenshot(page, f"{broker_name.lower()}_form_submitted")

                print(f"\n=== Form Submission Result ===")
                print(f"Status: {result['status']}")
                print(f"Message: {result['message']}")

                if result['status'] == 'success':
                    # Check for email confirmation
                    print(f"\nChecking for confirmation email...")
                    submission_time = result.get('submission_time')
                    confirmation_result = check_email_confirmation(
                        config, user_data, submission_time)
                    print(
                        f"Confirmation check: {confirmation_result['message']}"
                    )

                return result.get('status') == 'success'

            except Exception as e:
                print(f"\nAn error occurred: {str(e)}")
                take_screenshot(page, f"{broker_name.lower()}_form_error")
                return False
            finally:
                browser.close()

    elif config['type'] == 'email_only':
        print(f"\n=== Starting {config['name']} Email Deletion Flow ===")
        result = handle_email_request(config, user_data)
        print(f"Email result: {result['message']}")
        return result.get('status') == 'success'

    else:
        print(f"Unknown broker type: {config['type']}")
        return False


def handle_ai_fallback_flow(config: Dict, user_data: Dict) -> bool:
    """Handle AI-powered fallback flow for minimal broker configs.
    
    Args:
        config: Broker configuration (minimal)
        user_data: User data dictionary
        
    Returns:
        True if successful, False otherwise
    """
    broker_name = config.get('name', 'Unknown')
    form_url = config.get('url')

    print(f"\n=== AI Fallback Mode for {broker_name} ===")

    if not form_url:
        print(f"No URL found in config for {broker_name}. Skipping.")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = create_browser_context(browser)
        page = context.new_page()

        try:
            print(f"\n🤖 Analyzing {broker_name} form with AI...")

            # Navigate to the form
            print(f"Navigating to form: {form_url}")
            page.goto(form_url)
            page.wait_for_load_state('networkidle')

            # Take initial screenshot
            take_screenshot(page, f"{broker_name.lower()}_ai_initial")

            # Analyze form structure
            print("Analyzing form structure...")
            form_analysis = analyze_form(page)

            if not form_analysis.get('fields'):
                print("❌ No form fields found on the page")
                return False

            print(f"Found {len(form_analysis['fields'])} form fields")

            # Use constrained AI to map fields
            ai_mapper = ConstrainedFormMapper()
            field_mapping = ai_mapper.map_form_fields(form_analysis, user_data,
                                                      broker_name)

            # Fill form using AI mapping
            print("\n🤖 Filling form using AI field mapping...")
            fill_results = fill_form_deterministically(page, field_mapping,
                                                       user_data)

            print(f"\n=== Fill Results ===")
            print(f"Filled: {fill_results['filled']} fields")
            print(f"Failed: {fill_results['failed']} fields")

            if fill_results['errors']:
                print("Errors:")
                for error in fill_results['errors']:
                    print(f"  - {error}")

            # Ask user if they want to submit
            if fill_results['filled'] > 0:
                print(
                    "\n⚠ IMPORTANT: Please review the filled form before submitting."
                )
                submit_choice = input(
                    "Submit the form? (y/N): ").strip().lower()

                if submit_choice == 'y':
                    # Try to submit the form
                    try:
                        from utils.browser import submit_form
                        submit_form(page, form_analysis.get('submit_button'))
                        print("✓ Form submitted successfully")

                        # Generate config for future use
                        generated_config = generate_broker_config(
                            broker_name=broker_name,
                            form_analysis=form_analysis,
                            field_mapping=field_mapping,
                            form_url=form_url,
                            user_data=user_data)

                        config_path = save_discovered_config(
                            broker_name, generated_config)
                        print(
                            f"\n💾 Generated config saved for future use: {config_path}"
                        )

                        # Take final screenshot after success
                        take_screenshot(page,
                                        f"{broker_name.lower()}_ai_success")
                        return True

                    except Exception as e:
                        print(f"❌ Form submission failed: {str(e)}")
                        take_screenshot(
                            page, f"{broker_name.lower()}_ai_submit_error")
                        return False
                else:
                    print("Form submission cancelled by user")
                    take_screenshot(page,
                                    f"{broker_name.lower()}_ai_cancelled")
                    return False
            else:
                print(
                    "❌ No fields were successfully filled. Cannot submit form."
                )
                take_screenshot(page, f"{broker_name.lower()}_ai_no_fields")
                return False

        except Exception as e:
            print(f"\n❌ AI fallback error: {str(e)}")
            take_screenshot(page, f"{broker_name.lower()}_ai_error")
            return False
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description='Run data deletion flow for all brokers.')
    parser.add_argument(
        '--broker',
        help='Optional: specific broker name to process (e.g., Acxiom)')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')
    parser.add_argument('--date-of-birth',
                        help='Your date of birth (MM/DD/YYYY)',
                        type=validate_date_of_birth)
    parser.add_argument('--address', help='Your street address')
    parser.add_argument('--city', help='Your city')
    parser.add_argument(
        '--state',
        help='Your state (2-letter code or full name, e.g., CA or California)',
        type=validate_state_input)
    parser.add_argument('--zip-code', help='Your ZIP code')

    args = parser.parse_args()
    run_broker_deletion(args.first_name, args.last_name, args.email,
                        args.date_of_birth, args.address, args.city,
                        args.state, args.zip_code, args.broker)


if __name__ == '__main__':
    main()
