"""AI-powered fallback service for analyzing unknown broker forms."""
from typing import Dict, Optional, List
from dataclasses import dataclass
from playwright.sync_api import Page

from utils.constrained_ai import ConstrainedFormMapper, generate_broker_config, save_discovered_config
from utils.browser import analyze_form, fill_form_deterministically, submit_form


@dataclass
class AIAnalysisResult:
    """Result of AI form analysis."""
    success: bool
    fields_found: int
    fields_filled: int
    field_mapping: Optional[Dict] = None
    errors: Optional[List[str]] = None


class AIFallbackError(Exception):
    """Raised when AI fallback processing fails."""

    def __init__(self,
                 message: str,
                 broker_name: str = None,
                 recovery_suggestions: List[str] = None):
        super().__init__(message)
        self.broker_name = broker_name
        self.recovery_suggestions = recovery_suggestions or []


class AIFallbackService:
    """Handles AI-powered form analysis and filling for unknown brokers."""

    def __init__(self):
        """Initialize the AI fallback service."""
        self.ai_mapper = ConstrainedFormMapper()

    def analyze_and_fill_form(self, config: Dict, user_data: Dict,
                              page: Page) -> AIAnalysisResult:
        """Analyze form structure and fill using AI mapping.
        
        Args:
            config: Minimal broker configuration  
            user_data: User data dictionary
            page: Playwright page instance
            
        Returns:
            AIAnalysisResult with analysis outcome
            
        Raises:
            AIFallbackError: If analysis fails unrecoverably
        """
        broker_name = config.get('name', 'Unknown')

        try:
            # Analyze form structure
            print("Analyzing form structure...")
            form_analysis = analyze_form(page)

            if not form_analysis.get('fields'):
                raise AIFallbackError(
                    "No form fields found on the page",
                    broker_name=broker_name,
                    recovery_suggestions=[
                        "Verify the URL points to the correct privacy form",
                        "Check if the page requires login or additional navigation",
                        "Ensure JavaScript is enabled and page is fully loaded"
                    ])

            print(f"Found {len(form_analysis['fields'])} form fields")

            # Use constrained AI to map fields
            field_mapping = self.ai_mapper.map_form_fields(
                form_analysis, user_data, broker_name)

            # Fill form using AI mapping
            print("\n🤖 Filling form using AI field mapping...")
            fill_results = fill_form_deterministically(page, field_mapping,
                                                       user_data)

            return AIAnalysisResult(success=fill_results['filled'] > 0,
                                    fields_found=len(form_analysis['fields']),
                                    fields_filled=fill_results['filled'],
                                    field_mapping=field_mapping,
                                    errors=fill_results.get('errors', []))

        except Exception as e:
            raise AIFallbackError(
                f"AI form analysis failed: {str(e)}",
                broker_name=broker_name,
                recovery_suggestions=[
                    "Check OpenAI API key is valid and has credits",
                    "Verify network connectivity to OpenAI services",
                    "Try manual form submission as fallback",
                    f"Add full configuration for {broker_name} to avoid AI fallback"
                ])

    def attempt_form_submission(self, config: Dict, form_analysis: Dict,
                                field_mapping: Dict, page: Page,
                                user_data: Dict) -> bool:
        """Attempt to submit the form after user confirmation.
        
        Args:
            config: Broker configuration
            form_analysis: Form structure analysis
            field_mapping: AI-generated field mapping
            page: Playwright page instance
            user_data: User data dictionary
            
        Returns:
            True if submission successful, False otherwise
        """
        broker_name = config.get('name', 'Unknown')

        try:
            # Try to submit the form
            submit_form(page, form_analysis.get('submit_button'))
            print("✓ Form submitted successfully")

            # Generate config for future use
            generated_config = generate_broker_config(
                broker_name=broker_name,
                form_analysis=form_analysis,
                field_mapping=field_mapping,
                form_url=config.get('url'),
                user_data=user_data)

            config_path = save_discovered_config(broker_name, generated_config)
            print(f"\n💾 Generated config saved for future use: {config_path}")

            return True

        except Exception as e:
            print(f"❌ Form submission failed: {str(e)}")
            return False

    def get_user_confirmation(self, analysis_result: AIAnalysisResult) -> bool:
        """Get user confirmation before form submission.
        
        Args:
            analysis_result: Results from form analysis
            
        Returns:
            True if user confirms submission, False otherwise
        """
        print(f"\n=== Fill Results ===")
        print(f"Filled: {analysis_result.fields_filled} fields")
        print(f"Total fields found: {analysis_result.fields_found}")

        if analysis_result.errors:
            print("Errors:")
            for error in analysis_result.errors:
                print(f"  - {error}")

        if analysis_result.fields_filled > 0:
            print(
                "\n⚠ IMPORTANT: Please review the filled form before submitting."
            )
            submit_choice = input("Submit the form? (y/N): ").strip().lower()
            return submit_choice == 'y'
        else:
            print("❌ No fields were successfully filled. Cannot submit form.")
            return False

    def handle_full_ai_workflow(self, config: Dict, user_data: Dict,
                                page: Page) -> bool:
        """Handle complete AI fallback workflow.
        
        Args:
            config: Minimal broker configuration
            user_data: User data dictionary  
            page: Playwright page instance
            
        Returns:
            True if workflow completed successfully, False otherwise
        """
        broker_name = config.get('name', 'Unknown')

        try:
            # Step 1: Analyze and fill form
            analysis_result = self.analyze_and_fill_form(
                config, user_data, page)

            # Step 2: Get user confirmation
            if not self.get_user_confirmation(analysis_result):
                print("Form submission cancelled by user")
                return False

            # Step 3: Submit form and generate config
            return self.attempt_form_submission(
                config,
                {'submit_button': None},  # Simplified for now
                analysis_result.field_mapping,
                page,
                user_data)

        except AIFallbackError as e:
            print(f"\n❌ AI fallback error: {str(e)}")
            if e.recovery_suggestions:
                print("Recovery suggestions:")
                for suggestion in e.recovery_suggestions:
                    print(f"  - {suggestion}")
            return False
