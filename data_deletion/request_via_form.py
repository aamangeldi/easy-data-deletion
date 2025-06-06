import argparse
from playwright.sync_api import sync_playwright
import csv
from pathlib import Path
from typing import Dict
import json
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def ensure_screenshots_dir():
    """Ensure the screenshots directory exists."""
    screenshots_dir = Path(__file__).parent / 'screenshots'
    screenshots_dir.mkdir(exist_ok=True)
    return screenshots_dir


def get_broker_url(broker_name: str) -> str:
    """Get the form URL for a specific broker."""
    script_dir = Path(__file__).parent
    csv_path = script_dir / 'broker_lists' / 'current.csv'

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] == broker_name:
                return row['website']
    return None


def analyze_form(page) -> Dict:
    """Analyze the form structure and return field information."""
    # Get all form elements
    form_elements = page.query_selector_all('input, select, textarea')

    form_info = {
        'fields': [],
        'submit_button': None,
        'page_title': page.title(),
        'url': page.url
    }

    for element in form_elements:
        field_info = {
            'type': element.get_attribute('type') or 'text',
            'name': element.get_attribute('name'),
            'id': element.get_attribute('id'),
            'placeholder': element.get_attribute('placeholder'),
            'required': element.get_attribute('required') is not None,
            'label': None
        }

        # Try to find associated label
        if field_info['id']:
            label = page.query_selector(f"label[for='{field_info['id']}']")
            if label:
                field_info['label'] = label.inner_text()

        form_info['fields'].append(field_info)

    # Find submit button
    submit_button = page.query_selector(
        'button[type="submit"], input[type="submit"]')
    if submit_button:
        form_info['submit_button'] = {
            'text': submit_button.inner_text(),
            'type': submit_button.get_attribute('type')
        }

    return form_info


def create_browser_tools(page, user_data: Dict[str, str]):
    """Create browser interaction tools for the agent."""

    def get_page_content() -> str:
        """Get the current page content and form structure."""
        return json.dumps(analyze_form(page))

    def fill_user_data() -> str:
        """Fill in the user's data using the provided information."""
        try:
            # Map field IDs to user data
            field_mapping = {
                'firstNameDSARElement': user_data['first_name'],
                'lastNameDSARElement': user_data['last_name'],
                'emailDSARElement': user_data['email']
            }

            # Fill each field and track what was filled
            filled_fields = {}
            for field_id, value in field_mapping.items():
                page.fill(f"#{field_id}", value)
                filled_fields[field_id] = value

            # Return a JSON string with the actual filled values
            return json.dumps({
                "status": "success",
                "filled_fields": filled_fields
            })
        except Exception as e:
            raise ValueError(f"Error filling user data: {str(e)}")

    return [
        StructuredTool.from_function(
            func=get_page_content,
            name="get_page_content",
            description="Get the current page content and form structure."),
        StructuredTool.from_function(
            func=fill_user_data,
            name="fill_user_data",
            description="Fill in the user's personal information in the form.")
    ]


def fill_acxiom_form(first_name: str, last_name: str, email: str):
    """Fill out Acxiom's data deletion form using Playwright and LangChain."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    # Ensure screenshots directory exists
    screenshots_dir = ensure_screenshots_dir()

    # Store user data locally
    user_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email
    }

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={
                'width': 1920,
                'height': 1080
            },
            user_agent=
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )

        # Create a new page
        page = context.new_page()

        try:
            # Navigate to the form
            url = get_broker_url('Acxiom')
            if not url:
                raise ValueError("Acxiom URL not found in broker list")

            print(f"Navigating to {url}")
            page.goto(url)
            page.wait_for_load_state('networkidle')

            # Take initial screenshot
            initial_screenshot = screenshots_dir / "acxiom_form_initial.png"
            page.screenshot(path=str(initial_screenshot))
            print(f"\nInitial form state saved as {initial_screenshot}")

            # Create tools for the agent
            tools = create_browser_tools(page, user_data)

            # Create the agent
            llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 """You are an AI assistant helping to fill out a data deletion request form.
                Your goal is to help the user request deletion of their personal information.
                You have access to the following tools:
                - get_page_content: Get the current page content and form structure
                - fill_user_data: Fill in the user's personal information
                
                IMPORTANT: This is a TEST run. DO NOT submit the form. Only fill in the fields.
                
                First, analyze the form structure. Then:
                1. Use fill_user_data to fill in the user's information
                2. Take a screenshot
                3. Print a summary of what fields were filled using the actual values returned by fill_user_data
                4. DO NOT click any submit buttons
                5. Wait for user review

                For each field you fill:
                1. Verify the field's purpose
                2. Confirm the value is appropriate
                3. Check for any special requirements
                """),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])

            agent = create_openai_functions_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(agent=agent,
                                           tools=tools,
                                           verbose=True)

            print("\n=== TEST MODE ===")
            print("The agent will fill the form but WILL NOT submit it.")
            print("Please review the form before proceeding.\n")

            # Start the agent
            agent_executor.invoke({})

            # Take a screenshot
            filled_screenshot = screenshots_dir / "acxiom_form_filled.png"
            page.screenshot(path=str(filled_screenshot))
            print(
                f"\nForm was filled successfully. Screenshot saved as {filled_screenshot}"
            )
            print("\n=== TEST COMPLETE ===")
            print("Please review the form in the browser and the screenshots.")
            print("The form has NOT been submitted.")

            # Keep the browser open for review
            input("\nPress Enter to close the browser...")

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            error_screenshot = screenshots_dir / "acxiom_form_error.png"
            page.screenshot(path=str(error_screenshot))
            print(f"Error screenshot saved as {error_screenshot}")
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(
        description='Fill out data broker deletion forms.')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')

    args = parser.parse_args()

    fill_acxiom_form(args.first_name, args.last_name, args.email)


if __name__ == '__main__':
    main()
