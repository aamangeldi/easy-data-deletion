"""LangChain agent utility functions for data deletion automation."""
import json
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from playwright.sync_api import Page

def create_browser_tools(page: Page, user_data: Dict[str, str]) -> List[StructuredTool]:
    """Create browser interaction tools for the agent.
    
    Args:
        page: Playwright page instance
        user_data: Dictionary containing user information
    
    Returns:
        List of StructuredTool instances for the agent
    """
    from .browser import analyze_form, fill_form_field, submit_form

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
                fill_form_field(page, field_id, value)
                filled_fields[field_id] = value

            return json.dumps({
                "status": "success",
                "filled_fields": filled_fields
            })
        except Exception as e:
            raise ValueError(f"Error filling user data: {str(e)}")

    def submit_form_tool() -> str:
        """Submit the form and return the result."""
        try:
            submit_form(page)
            return json.dumps({
                "status": "success",
                "message": "Form submitted successfully"
            })
        except Exception as e:
            raise ValueError(f"Error submitting form: {str(e)}")

    return [
        StructuredTool.from_function(
            func=get_page_content,
            name="get_page_content",
            description="Get the current page content and form structure."
        ),
        StructuredTool.from_function(
            func=fill_user_data,
            name="fill_user_data",
            description="Fill in the user's personal information in the form."
        ),
        StructuredTool.from_function(
            func=submit_form_tool,
            name="submit_form",
            description="Submit the form after filling in the data."
        )
    ]

def create_form_agent(
    tools: List[StructuredTool],
    system_prompt: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0
) -> AgentExecutor:
    """Create a LangChain agent for form automation.
    
    Args:
        tools: List of tools for the agent to use
        system_prompt: System prompt for the agent
        model: OpenAI model to use
        temperature: Temperature for model generation
    
    Returns:
        AgentExecutor instance
    """
    llm = ChatOpenAI(temperature=temperature, model=model)

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
    return """You are an AI assistant helping to fill out a data deletion request form.
    Your goal is to help the user request deletion of their personal information.
    You have access to the following tools:
    - get_page_content: Get the current page content and form structure
    - fill_user_data: Fill in the user's personal information
    - submit_form: Submit the form after filling in the data
    
    Follow these steps:
    1. Analyze the form structure using get_page_content
    2. Fill in the user's information using fill_user_data
    3. Submit the form using submit_form
    4. Wait for confirmation
    
    For each field you fill:
    1. Verify the field's purpose
    2. Confirm the value is appropriate
    3. Check for any special requirements"""
