"""LangChain agent utility functions for data deletion automation."""
import json
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from playwright.sync_api import Page

class FormManager:
    """Manages form state and operations for the agent."""
    
    def __init__(self, page: Page, user_data: Dict[str, str], llm: ChatOpenAI):
        """Initialize the form manager.
        
        Args:
            page: Playwright page instance
            user_data: Dictionary containing user information
            llm: LLM instance to use for field mapping
        """
        self.page = page
        self.user_data = user_data
        self.llm = llm
        self._form_analysis: Optional[Dict] = None

    @property
    def form_analysis(self) -> Dict:
        """Get the current form analysis, performing it if necessary."""
        if self._form_analysis is None:
            from .browser import analyze_form
            self._form_analysis = analyze_form(self.page)
        return self._form_analysis

    def get_field_mapping(self) -> Dict[str, str]:
        """Use LLM to map form fields to user data without exposing actual values."""
        # Create a sanitized version of user data that only includes keys
        sanitized_user_data = {key: "[REDACTED]" for key in self.user_data.keys()}

        # Add field type information to help the LLM understand how to fill each field
        form_info = {
            'fields': [
                {
                    **field,
                    # Explicitly mark state field as autocomplete
                    'field_type': 'autocomplete' if (
                        field.get('id', '').lower() in ['state', 'state-input', 'statedsarelement'] or
                        field.get('label', '').lower() == 'state'
                    ) else 'text'
                }
                for field in self.form_analysis['fields']
            ],
            'submit_button': self.form_analysis.get('submit_button')
        }

        prompt = f"""Given a form structure and available user data fields, map the form fields to the appropriate user data keys.
        Return ONLY a JSON object mapping field IDs to user data keys and field types.

        Form Structure:
        {json.dumps(form_info, indent=2)}

        Available User Data Fields:
        {json.dumps(list(sanitized_user_data.keys()), indent=2)}

        Rules:
        1. Only map fields that clearly correspond to user data fields
        2. Use field IDs as keys and user data field names as values
        3. Return a JSON object like {{"fieldId1": {{"key": "first_name", "type": "text"}}, "fieldId2": {{"key": "state", "type": "autocomplete"}}}}
        4. If no clear mapping can be made, return an empty object {{}}
        5. Do not include any actual user data values
        6. Pay special attention to field types:
           - The state field should ALWAYS be marked as 'autocomplete' type
           - Fields with role="listbox" should be marked as 'option' type
           - Fields with role="combobox" should be marked as 'autocomplete' type
           - Other fields should be marked as 'text' type
        7. For the state field, ensure it's mapped to the 'state' key in user data
        """

        response = self.llm.invoke(prompt)
        try:
            # Get the mapping of field IDs to user data keys and types
            field_mapping = json.loads(response.content)

            # Convert the mapping to use actual user data values
            return {
                field_id: {
                    'value': self.user_data[mapping['key']],
                    'type': mapping.get('type', 'text')
                }
                for field_id, mapping in field_mapping.items()
                if mapping['key'] in self.user_data
            }
        except json.JSONDecodeError:
            return {}

    def get_page_content(self) -> str:
        """Get the current page content and form structure."""
        return json.dumps(self.form_analysis)

    def fill_user_data(self) -> str:
        """Fill in the user's data using the provided information."""
        try:
            from .browser import fill_form_field
            
            # Use LLM to map fields
            field_mapping = self.get_field_mapping()

            if not field_mapping:
                raise ValueError("Could not determine field mappings for user data")

            # Fill each field and track what was filled
            filled_fields = {}
            for field_id, field_info in field_mapping.items():
                fill_form_field(
                    self.page, 
                    field_id, 
                    field_info['value'],
                    field_type=field_info.get('type', 'text')
                )
                filled_fields[field_id] = field_info

            return json.dumps({
                "status": "success",
                "filled_fields": filled_fields,
                "field_mapping": field_mapping
            })
        except Exception as e:
            raise ValueError(f"Error filling user data: {str(e)}")

    def submit_form(self) -> str:
        """Submit the form and return the result."""
        try:
            from .browser import submit_form
            
            submit_info = self.form_analysis.get('submit_button')
            submit_form(self.page, submit_info)
            
            return json.dumps({
                "status": "success",
                "message": "Form submitted successfully",
                "submit_info": submit_info
            })
        except Exception as e:
            raise ValueError(f"Error submitting form: {str(e)}")

def create_browser_tools(
    page: Page,
    user_data: Dict[str, str],
    llm: ChatOpenAI,
    gmail_service: Dict = None
) -> List[StructuredTool]:
    """Create browser interaction tools for the agent.
    
    Args:
        page: Playwright page instance
        user_data: Dictionary containing user information
        llm: LLM instance to use for field mapping
        gmail_service: Optional Gmail service for email functionality
    
    Returns:
        List of StructuredTool instances for the agent
    """
    from .gmail import create_deletion_email, send_email, ensure_label_exists, check_confirmation_email
    from .broker import get_broker_email_domains

    # Create form manager instance
    form_manager = FormManager(page, user_data, llm)

    def send_deletion_email(broker_name: str) -> str:
        """Send a data deletion request email to a broker."""
        if not gmail_service:
            raise ValueError("Gmail service not configured")

        try:
            ensure_label_exists(gmail_service, "Data Deletion Requests")
            message = create_deletion_email(
                gmail_service,
                broker_name,
                user_data['first_name'],
                user_data['last_name'],
                user_data['email']
            )
            send_email(gmail_service, message)
            
            return json.dumps({
                "status": "success",
                "message": f"Deletion request email sent to {broker_name}",
                "message_id": message['id']
            })
        except Exception as e:
            raise ValueError(f"Error sending deletion email: {str(e)}")

    def check_email_confirmation(broker_name: str, wait_time: int = 300) -> str:
        """Check for confirmation email from a broker."""
        if not gmail_service:
            raise ValueError("Gmail service not configured")

        try:
            domains = get_broker_email_domains(broker_name)
            if not domains:
                raise ValueError(f"No email domains configured for {broker_name}")

            confirmed = check_confirmation_email(
                service=gmail_service,
                user_email=user_data['email'],
                from_domains=domains,
                wait_time=wait_time
            )

            return json.dumps({
                "status": "success",
                "confirmed": confirmed,
                "message": "Confirmation email found" if confirmed else "No confirmation email received"
            })
        except Exception as e:
            raise ValueError(f"Error checking confirmation email: {str(e)}")

    tools = [
        StructuredTool.from_function(
            func=form_manager.get_page_content,
            name="get_page_content",
            description="Get the current page content and form structure."
        ),
        StructuredTool.from_function(
            func=form_manager.fill_user_data,
            name="fill_user_data",
            description="Fill in the user's personal information in the form."
        ),
        StructuredTool.from_function(
            func=form_manager.submit_form,
            name="submit_form",
            description="Submit the form after filling in the data."
        )
    ]

    # Add email tools if Gmail service is available
    if gmail_service:
        tools.extend([
            StructuredTool.from_function(
                func=send_deletion_email,
                name="send_deletion_email",
                description="Send a data deletion request email to a broker."
            ),
            StructuredTool.from_function(
                func=check_email_confirmation,
                name="check_email_confirmation",
                description="Check for confirmation email from a broker after form submission or email request."
            )
        ])

    return tools

def create_form_agent(
    page: Page,
    user_data: Dict[str, str],
    system_prompt: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0,
    gmail_service: Dict = None
) -> AgentExecutor:
    """Create a LangChain agent for form automation.
    
    Args:
        page: Playwright page instance
        user_data: Dictionary containing user information
        system_prompt: System prompt for the agent
        model: OpenAI model to use
        temperature: Temperature for model generation
        gmail_service: Optional Gmail service for email functionality
    
    Returns:
        AgentExecutor instance
    """
    llm = ChatOpenAI(temperature=temperature, model=model)
    tools = create_browser_tools(page, user_data, llm, gmail_service)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)

def get_default_form_prompt() -> str:
    """Get the default system prompt for form automation.
    
    Returns:
        Default system prompt string
    """
    return """You are an AI assistant helping to request deletion of personal information from data brokers.
    Your goal is to help the user submit data deletion requests either through web forms or email.

    You have access to the following tools:
    - get_page_content: Get the current page content and form structure, including submit button information
    - fill_user_data: Fill in the user's personal information in the form
    - submit_form: Submit the form after filling in the data, using the analyzed submit button
    - send_deletion_email: Send a data deletion request email to a broker (if available)
    - check_email_confirmation: Check for confirmation email from a broker (if available)

    Follow these steps:
    1. Determine the best method for the deletion request:
       - If a web form is available, use the form submission flow
       - If email is the only option, use the email submission flow
       - If both are available, prefer the web form for better tracking

    2. For web form submission:
       a. Use get_page_content to analyze the form structure and submit button
       b. Use fill_user_data to fill in the user's information
       c. Submit the form using submit_form, which will use the analyzed submit button
       d. Use check_email_confirmation to verify the submission
       e. Wait for confirmation

    3. For email submission:
       a. Use send_deletion_email with the broker's name
       b. Use check_email_confirmation to verify the request
       c. Wait for confirmation

    4. After submission:
       - Track the request status
       - Note any follow-up actions needed
       - Report the result to the user

    The fill_user_data tool will automatically:
    1. Analyze the form fields
    2. Map them to the appropriate user data
    3. Fill in the values
    4. Return information about what was filled

    The submit_form tool will:
    1. Use the submit button information from form analysis
    2. Try multiple strategies to find and click the submit button
    3. Handle various types of submit buttons (explicit, text-based, primary action)
    4. Report the submission status

    For email confirmation:
    1. Always check for confirmation after form submission or email request
    2. Wait for the specified time period
    3. Report whether confirmation was received
    4. If no confirmation is received, note that manual follow-up may be needed"""
