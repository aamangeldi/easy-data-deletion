"""Script to send data deletion requests via web forms."""
import argparse
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv

from utils import (
    create_browser_context,
    take_screenshot,
    create_browser_tools,
    create_form_agent,
    get_default_form_prompt,
    get_broker_url
)

# Load environment variables
load_dotenv()

def fill_broker_form(broker_name: str, first_name: str, last_name: str, email: str):
    """Fill out a data broker's deletion form using Playwright and LangChain."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    # Store user data
    user_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email
    }

    # Get broker URL
    url = get_broker_url(broker_name)
    if not url:
        raise ValueError(f"{broker_name} URL not found in broker list")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = create_browser_context(browser)
        page = context.new_page()

        try:
            print(f"\n=== Starting {broker_name} Data Deletion Flow ===")
            
            # Navigate to the form
            print(f"\nNavigating to {broker_name} deletion form...")
            page.goto(url)
            page.wait_for_load_state('networkidle')

            # Take initial screenshot
            take_screenshot(page, f"{broker_name.lower()}_form_initial")

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
            take_screenshot(page, f"{broker_name.lower()}_form_filled")

            print("\n✓ Form filled successfully!")
            print("Please review the form in the browser and the screenshots.")
            print("The form has NOT been submitted.")

            # Keep the browser open for review
            input("\nPress Enter to close the browser...")

        except Exception as e:
            print(f"\n✗ An error occurred: {str(e)}")
            take_screenshot(page, f"{broker_name.lower()}_form_error")
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description='Fill out data broker deletion forms.')
    parser.add_argument('--broker', required=True, help='Name of the data broker')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')

    args = parser.parse_args()
    fill_broker_form(args.broker, args.first_name, args.last_name, args.email)

if __name__ == '__main__':
    main()
