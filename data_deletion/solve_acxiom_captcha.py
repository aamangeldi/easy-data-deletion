"""Script to solve Acxiom form captcha using anticaptchaofficial."""
import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from data_deletion.utils.captcha import get_solver, solve_captcha, ACXIOM_WEBSITE_KEY
from data_deletion.utils.broker import ACXIOM_DELETE_FORM_URL

# Load environment variables
load_dotenv()


def fill_acxiom_form(first_name: str, last_name: str, email: str,
                     date_of_birth: str, address: str, city: str, state: str,
                     zip_code: str):
    """Fill out Acxiom form and solve captcha."""
    if not os.getenv("ANTICAPTCHA_API_KEY"):
        raise ValueError("Please set ANTICAPTCHA_API_KEY environment variable")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            print("\n=== Starting Acxiom Form Fill ===")

            # Navigate to the form
            print("\nNavigating to Acxiom deletion form...")
            page.goto(ACXIOM_DELETE_FORM_URL)
            page.wait_for_load_state('networkidle')

            # Fill out the form fields
            print("\nFilling out form fields...")

            # Fill each field
            page.fill('input[name="firstName"]', first_name)
            page.fill('input[name="lastName"]', last_name)
            page.fill('input[name="email"]', email)
            page.fill('input[name="dateOfBirth"]', date_of_birth)
            page.fill('input[name="address"]', address)
            page.fill('input[name="city"]', city)

            # Handle state field (might be a dropdown)
            state_field = page.query_selector(
                'select[name="state"], input[name="state"]')
            if state_field:
                if state_field.tag_name() == 'SELECT':
                    state_field.select_option(label=state)
                else:
                    state_field.fill(state)

            page.fill('input[name="zipCode"]', zip_code)

            # Select "as Myself" for subject type
            page.select_option('select[name="subjectType"]', label="as Myself")

            # Select "Delete" for request type
            page.select_option('select[name="requestType"]', label="Delete")

            print("\nForm filled successfully!")
            print("\nSolving captcha...")

            # Solve captcha
            solver = get_solver(website_url=ACXIOM_DELETE_FORM_URL,
                                website_key=ACXIOM_WEBSITE_KEY)
            g_response = solve_captcha(solver)

            if g_response:
                print(f"\nCaptcha solved! Response: {g_response}")

                # Inject the captcha response
                page.evaluate(
                    f'document.querySelector("#g-recaptcha-response").innerHTML="{g_response}";'
                )

                # Submit the form
                print("\nSubmitting form...")
                page.click('button[type="submit"]')

                # Wait for navigation
                page.wait_for_load_state('networkidle')
                print("\nForm submitted!")
            else:
                print("\nFailed to solve captcha!")

            # Keep browser open for review
            input("\nPress Enter to close the browser...")

        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
        finally:
            browser.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fill out Acxiom form and solve captcha.')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')
    parser.add_argument('--date-of-birth',
                        required=True,
                        help='Your date of birth (MM/DD/YYYY)')
    parser.add_argument('--address', required=True, help='Your street address')
    parser.add_argument('--city', required=True, help='Your city')
    parser.add_argument('--state',
                        required=True,
                        help='Your state (full name, e.g., California)')
    parser.add_argument('--zip-code', required=True, help='Your ZIP code')

    args = parser.parse_args()
    fill_acxiom_form(args.first_name, args.last_name, args.email,
                     args.date_of_birth, args.address, args.city, args.state,
                     args.zip_code)


if __name__ == '__main__':
    main()
