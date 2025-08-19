"""Refactored broker data deletion automation script using services."""
import argparse
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

from services.broker_processor import BrokerProcessor, BrokerConfigurationError
from services.form_handler import FormHandler, FormSubmissionError
from services.ai_fallback_service import AIFallbackService, AIFallbackError
from utils import (create_browser_context, take_screenshot, prepare_user_data,
                   validate_date_of_birth, validate_state_input)

# Load environment variables
load_dotenv()


class DataDeletionOrchestrator:
    """Orchestrates the entire data deletion workflow."""

    def __init__(self):
        """Initialize with service dependencies."""
        self.broker_processor = BrokerProcessor()
        self.form_handler = FormHandler()
        self.ai_fallback = AIFallbackService()

    def run_deletion_workflow(self, user_args: dict) -> dict:
        """Run the complete data deletion workflow.
        
        Args:
            user_args: Dictionary with user data and processing options
            
        Returns:
            Summary dictionary with processing results
        """
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("Please set OPENAI_API_KEY environment variable")

        try:
            # Load and filter configurations
            configs = self.broker_processor.get_all_configurations()
            configs = self.broker_processor.filter_configurations(
                configs, user_args.get('broker_filter'))

            print(f"\n=== Processing {len(configs)} broker(s) ===")

            successful_deletions = []
            failed_deletions = []

            # Process each broker
            for config in configs:
                broker_name = config.get('name', 'Unknown')
                print(f"\n{'='*60}")
                print(f"Processing: {broker_name}")
                print(f"{'='*60}")

                try:
                    success = self._process_single_broker(config, user_args)
                    if success:
                        successful_deletions.append(broker_name)
                    else:
                        failed_deletions.append(broker_name)

                except Exception as e:
                    print(f"❌ Error processing {broker_name}: {str(e)}")
                    failed_deletions.append(broker_name)

            # Generate and display summary
            summary = self.broker_processor.get_processing_summary(
                successful_deletions, failed_deletions)
            self._print_summary(summary)

            return summary

        except BrokerConfigurationError as e:
            print(f"❌ Configuration Error: {str(e)}")
            if e.recovery_suggestions:
                print("Recovery suggestions:")
                for suggestion in e.recovery_suggestions:
                    print(f"  - {suggestion}")
            return {"error": str(e)}

    def _process_single_broker(self, config: dict, user_args: dict) -> bool:
        """Process a single broker configuration.
        
        Args:
            config: Broker configuration dictionary
            user_args: User arguments dictionary
            
        Returns:
            True if processing successful, False otherwise
        """
        broker_name = config.get('name', 'Unknown')

        # Determine processing approach
        use_ai_fallback = self.broker_processor.is_minimal_configuration(
            config)

        if use_ai_fallback:
            return self._handle_ai_workflow(config, user_args)
        else:
            return self._handle_deterministic_workflow(config, user_args)

    def _handle_deterministic_workflow(self, config: dict,
                                       user_args: dict) -> bool:
        """Handle deterministic workflow with full broker configuration.
        
        Args:
            config: Full broker configuration
            user_args: User arguments dictionary
            
        Returns:
            True if successful, False otherwise
        """
        broker_name = config.get('name', 'Unknown')
        print(f"✓ Using deterministic config for {broker_name}")

        # Prepare formatted user data
        user_data = prepare_user_data(
            config,
            first_name=user_args['first_name'],
            last_name=user_args['last_name'],
            email=user_args['email'],
            date_of_birth=user_args.get('date_of_birth'),
            address=user_args.get('address'),
            city=user_args.get('city'),
            state=user_args.get('state'),
            zip_code=user_args.get('zip_code'))

        if config['type'] == 'web_form':
            return self._handle_web_form(config, user_data)
        elif config['type'] == 'email_only':
            return self._handle_email_request(config, user_data)
        else:
            print(f"Unknown broker type: {config['type']}")
            return False

    def _handle_ai_workflow(self, config: dict, user_args: dict) -> bool:
        """Handle AI fallback workflow for minimal configurations.
        
        Args:
            config: Minimal broker configuration
            user_args: User arguments dictionary
            
        Returns:
            True if successful, False otherwise
        """
        broker_name = config.get('name', 'Unknown')
        print(f"🤖 Using AI fallback for {broker_name} (minimal config)")

        # Prepare basic user data for AI
        user_data = {
            k: v
            for k, v in user_args.items()
            if v is not None and k != 'broker_filter'
        }

        form_url = config.get('url')
        if not form_url:
            print(f"No URL found in config for {broker_name}. Skipping.")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = create_browser_context(browser)
            page = context.new_page()

            try:
                print(f"\n🤖 Analyzing {broker_name} form with AI...")

                # Navigate to form
                print(f"Navigating to form: {form_url}")
                page.goto(form_url)
                page.wait_for_load_state('networkidle')

                # Take initial screenshot
                take_screenshot(page, f"{broker_name.lower()}_ai_initial")

                # Handle AI workflow
                success = self.ai_fallback.handle_full_ai_workflow(
                    config, user_data, page)

                # Take final screenshot
                screenshot_suffix = "ai_success" if success else "ai_cancelled"
                take_screenshot(page,
                                f"{broker_name.lower()}_{screenshot_suffix}")

                return success

            except AIFallbackError as e:
                print(f"\n❌ AI fallback error: {str(e)}")
                if e.recovery_suggestions:
                    print("Recovery suggestions:")
                    for suggestion in e.recovery_suggestions:
                        print(f"  - {suggestion}")
                take_screenshot(page, f"{broker_name.lower()}_ai_error")
                return False
            finally:
                browser.close()

    def _handle_web_form(self, config: dict, user_data: dict) -> bool:
        """Handle web form submission workflow.
        
        Args:
            config: Broker configuration
            user_data: Prepared user data
            
        Returns:
            True if successful, False otherwise
        """
        broker_name = config.get('name', 'Unknown')

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = create_browser_context(browser)
            page = context.new_page()

            try:
                print(f"\n=== Starting {broker_name} Data Deletion Flow ===")

                # Navigate to form
                print(f"Navigating to {broker_name} deletion form...")
                page.goto(config['url'])
                page.wait_for_load_state('networkidle')

                # Take initial screenshot
                take_screenshot(page, f"{broker_name.lower()}_form_initial")

                # Submit form
                result = self.form_handler.submit_web_form(
                    config, user_data, page)

                # Take screenshot after submission
                take_screenshot(page, f"{broker_name.lower()}_form_submitted")

                print(f"\n=== Form Submission Result ===")
                print(f"Status: {'Success' if result.success else 'Failed'}")
                print(f"Message: {result.message}")

                if result.success:
                    # Check for email confirmation
                    print(f"\nChecking for confirmation email...")
                    confirmation_result = self.form_handler.check_email_confirmation(
                        config, user_data, result.submission_time)
                    print(
                        f"Confirmation check: {confirmation_result['message']}"
                    )

                return result.success

            except FormSubmissionError as e:
                print(f"\n❌ Form submission error: {str(e)}")
                take_screenshot(page, f"{broker_name.lower()}_form_error")
                return False
            except Exception as e:
                print(f"\n❌ Unexpected error: {str(e)}")
                take_screenshot(page, f"{broker_name.lower()}_form_error")
                return False
            finally:
                browser.close()

    def _handle_email_request(self, config: dict, user_data: dict) -> bool:
        """Handle email-based deletion request.
        
        Args:
            config: Broker configuration
            user_data: User data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        broker_name = config.get('name', 'Unknown')
        print(f"\n=== Starting {broker_name} Email Deletion Flow ===")

        # Placeholder for email functionality
        print(f"Email-based deletion request would be sent to {broker_name}")
        return True

    def _print_summary(self, summary: dict):
        """Print processing summary to console.
        
        Args:
            summary: Summary dictionary from broker processor
        """
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Total brokers processed: {summary['total_brokers']}")
        print(f"Successful: {summary['successful_count']}")
        print(f"Failed: {summary['failed_count']}")

        if summary.get('success_rate'):
            print(f"Success rate: {summary['success_rate']}%")

        if summary.get('successful_brokers'):
            print(f"\n✓ Successful deletions:")
            for broker in summary['successful_brokers']:
                print(f"  - {broker}")

        if summary.get('failed_brokers'):
            print(f"\n❌ Failed deletions:")
            for broker in summary['failed_brokers']:
                print(f"  - {broker}")

        if summary.get('recommendations'):
            print(f"\n💡 Recommendations:")
            for rec in summary['recommendations']:
                print(f"  - {rec}")


def main():
    """Main entry point for the refactored broker agent."""
    parser = argparse.ArgumentParser(
        description=
        'Run data deletion flow for all brokers using refactored services.')
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

    # Convert args to dictionary for easier passing
    user_args = {
        'broker_filter': args.broker,
        'first_name': args.first_name,
        'last_name': args.last_name,
        'email': args.email,
        'date_of_birth': args.date_of_birth,
        'address': args.address,
        'city': args.city,
        'state': args.state,
        'zip_code': args.zip_code
    }

    # Run workflow
    orchestrator = DataDeletionOrchestrator()
    orchestrator.run_deletion_workflow(user_args)


if __name__ == '__main__':
    main()
