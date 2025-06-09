"""Acxiom data deletion automation script."""
import argparse
from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List

from utils import (get_gmail_service, create_browser_context, take_screenshot,
                   create_form_agent, get_default_form_prompt,
                   ACXIOM_DELETE_FORM_URL)

from data_deletion.utils.captcha import get_solver, solve_captcha, ACXIOM_WEBSITE_KEY

# Load environment variables
load_dotenv()

# State code to full name mapping
# TODO: make agent try both state code and full state name
STATE_MAPPING: Dict[str, str] = {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming',
    'DC': 'District of Columbia'
}


def validate_date_of_birth(date_str: str) -> str:
    """Validate and format date of birth.

    Args:
        date_str: Date string in MM/DD/YYYY format

    Returns:
        Formatted date string

    Raises:
        ValueError: If date is invalid
    """
    try:
        # Parse the date
        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
        # Ensure date is not in the future
        if date_obj > datetime.now():
            raise ValueError("Date of birth cannot be in the future")
        # Return formatted date
        return date_obj.strftime('%m/%d/%Y')
    except ValueError as e:
        if "time data" in str(e):
            raise ValueError("Date must be in MM/DD/YYYY format")
        raise


def validate_state_code(state: str) -> str:
    """Validate state code and return full state name.

    Args:
        state: Two-letter state code

    Returns:
        Full state name

    Raises:
        ValueError: If state code is invalid
    """
    state = state.upper()
    if state not in STATE_MAPPING:
        valid_states = ', '.join(sorted(STATE_MAPPING.keys()))
        raise ValueError(f"Invalid state code. Must be one of: {valid_states}")
    return STATE_MAPPING[state]


def run_delete_flow(first_name: str, last_name: str, email: str,
                    date_of_birth: str, address: str, city: str, state: str,
                    zip_code: str):
    """Run the Acxiom data deletion flow."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    # Store user data with form-specific values
    user_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'date_of_birth': date_of_birth,
        'address': address,
        'city': city,
        'state': state,  # This will be the full state name
        'zip_code': zip_code,
        # Acxiom-specific values
        'subject_type':
        'as Myself',  # "I am submitting this request: as Myself"
        'request_type':
        'Delete'  # "Select the Right You Want to Exercise: Delete"
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

            # Create agent with email capabilities
            agent = create_form_agent(page=page,
                                      user_data=user_data,
                                      system_prompt=get_default_form_prompt(),
                                      gmail_service=gmail_service)
            print(f"agent created")
            # Run the agent
            print("\nStarting deletion request process...")
            result = agent.invoke({"broker_name": "Acxiom", "wait_time": 300})

            # Take a screenshot after form is filled
            take_screenshot(page, "acxiom_form_filled")

            # The agent will handle email confirmation and report the status
            print("\n=== Deletion Request Status ===")
            print(result.get('output', 'No status information available'))

            print(f"solving captcha")
            # solve captcha
            solver = get_solver(website_url=ACXIOM_DELETE_FORM_URL,
                                website_key=ACXIOM_WEBSITE_KEY)
            g_response = solve_captcha(solver)
            print(f"g_response: {g_response}")

            # submit form
            page.click('button[type="submit"]')

        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            take_screenshot(page, "acxiom_form_error")
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description='Run Acxiom data deletion flow.')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')
    parser.add_argument('--date-of-birth',
                        required=True,
                        help='Your date of birth (MM/DD/YYYY)',
                        type=validate_date_of_birth)
    parser.add_argument('--address', required=True, help='Your street address')
    parser.add_argument('--city', required=True, help='Your city')
    parser.add_argument(
        '--state',
        required=True,
        help='Your state (2-letter code, e.g., CA for California)',
        type=validate_state_code)
    parser.add_argument('--zip-code', required=True, help='Your ZIP code')

    args = parser.parse_args()
    run_delete_flow(
        args.first_name,
        args.last_name,
        args.email,
        args.date_of_birth,
        args.address,
        args.city,
        args.
        state,  # This will be the full state name from validate_state_code
        args.zip_code)

    ## (Future) Opt out flow
    # 1. navigate to https://www.acxiom.com/optout/
    # 2. fill out the form with required information, hit submit
    # 3. check email, there should be a link to confirm the request, click it -> redirected to confirmation page


if __name__ == '__main__':
    main()
