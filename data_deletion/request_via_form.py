import argparse
from playwright.sync_api import sync_playwright
import csv
from pathlib import Path
from typing import Dict, Optional
import json
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    submit_button = page.query_selector('button[type="submit"], input[type="submit"]')
    if submit_button:
        form_info['submit_button'] = {
            'text': submit_button.inner_text(),
            'type': submit_button.get_attribute('type')
        }
    
    return form_info

def create_browser_tools(page):
    """Create browser interaction tools for the agent."""
    def fill_field(selector: str, value: str) -> str:
        """Fill a form field with a value.
        
        Args:
            selector: The ID of the field to fill (without the # prefix)
            value: The value to fill in the field
        """
        try:
            return page.fill(f"#{selector}", value)
        except Exception as e:
            raise ValueError(f"Error filling field: {str(e)}")

    def get_page_content() -> str:
        """Get the current page content and form structure."""
        return json.dumps(analyze_form(page))

    return [
        StructuredTool.from_function(
            func=fill_field,
            name="fill_field",
            description="""Fill a form field with a value.
            Example: fill_field("firstNameDSARElement", "John")"""
        ),
        StructuredTool.from_function(
            func=get_page_content,
            name="get_page_content",
            description="Get the current page content and form structure."
        )
    ]

def fill_acxiom_form(first_name: str, last_name: str, email: str):
    """Fill out Acxiom's data deletion form using Playwright and LangChain."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Please set OPENAI_API_KEY environment variable")
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
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
            page.screenshot(path="acxiom_form_initial.png")
            print("\nInitial form state saved as acxiom_form_initial.png")
            
            # Create tools for the agent
            tools = create_browser_tools(page)
            
            # Create the agent
            llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an AI assistant helping to fill out a data deletion request form.
                Your goal is to help the user request deletion of their personal information.
                You have access to the following tools:
                - fill_field: Fill a form field with a value
                - get_page_content: Get the current page content and form structure
                
                IMPORTANT: This is a TEST run. DO NOT submit the form. Only fill in the fields.
                
                First, analyze the form structure. Then, fill in the user's information:
                - First Name: {first_name}
                - Last Name: {last_name}
                - Email: {email}
                
                Be careful and methodical. After filling the form:
                1. Take a screenshot
                2. Print a summary of what fields were filled
                3. DO NOT click any submit buttons
                4. Wait for user review

                For each field you fill:
                1. Verify the field's purpose
                2. Confirm the value is appropriate
                3. Check for any special requirements
                """),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            agent = create_openai_functions_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
            
            print("\n=== TEST MODE ===")
            print("The agent will fill the form but WILL NOT submit it.")
            print("Please review the form before proceeding.\n")
            
            # Start the agent
            agent_executor.invoke({
                "first_name": first_name,
                "last_name": last_name,
                "email": email
            })
            
            # Take a screenshot
            page.screenshot(path="acxiom_form_filled.png")
            print("\nForm was filled successfully. Screenshot saved as acxiom_form_filled.png")
            print("\n=== TEST COMPLETE ===")
            print("Please review the form in the browser and the screenshots.")
            print("The form has NOT been submitted.")
            
            # Keep the browser open for review
            input("\nPress Enter to close the browser...")
            
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            page.screenshot(path="acxiom_form_error.png")
            print("Error screenshot saved as acxiom_form_error.png")
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description='Fill out data broker deletion forms.')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your email address')
    
    args = parser.parse_args()
    
    fill_acxiom_form(
        args.first_name,
        args.last_name,
        args.email
    )

if __name__ == '__main__':
    main()
