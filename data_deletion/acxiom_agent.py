"""Acxiom data deletion automation script."""
import argparse
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv

from utils import (
    get_gmail_service,
    create_browser_context,
    take_screenshot,
    create_browser_tools,
    create_form_agent,
    get_default_form_prompt,
    check_confirmation_email,
    ACXIOM_DELETE_FORM_URL,
    get_broker_email_domains
)

# Load environment variables
load_dotenv()

def run_delete_flow(first_name: str, last_name: str, email: str):
    """Run the Acxiom data deletion flow."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    # Store user data
    user_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email
    }

    # Initialize Gmail service for email monitoring
    gmail_service = get_gmail_service()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = create_browser_context(browser)
        page = context.new_page()

        try:
            print("\n=== Starting Acxiom Data Deletion Flow ===")
            
            # Navigate to the form
            print(f"\nNavigating to Acxiom deletion form...")
            page.goto(ACXIOM_DELETE_FORM_URL)
            page.wait_for_load_state('networkidle')

            # Take initial screenshot
            take_screenshot(page, "acxiom_form_initial")

            # Create tools and agent
            tools = create_browser_tools(page, user_data)
            agent = create_form_agent(
                tools=tools,
                system_prompt=get_default_form_prompt()
            )

            # Run the agent
            print("\nFilling out the form...")
            agent.invoke({})

            # Take a screenshot after form is filled
            take_screenshot(page, "acxiom_form_filled")

            # Wait for confirmation email
            if check_confirmation_email(
                service=gmail_service,
                user_email=email,
                from_domains=get_broker_email_domains('Acxiom')
            ):
                print("\n✓ Data deletion request submitted successfully!")
            else:
                print("\n⚠ Data deletion request may not have been processed. Please check your email manually.")

        except Exception as e:
            print(f"\n✗ An error occurred: {str(e)}")
            take_screenshot(page, "acxiom_form_error")
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description='Run Acxiom data deletion flow.')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')

    args = parser.parse_args()
    run_delete_flow(args.first_name, args.last_name, args.email)

if __name__ == '__main__':
    main() 