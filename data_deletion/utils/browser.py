"""Browser automation utility functions for data deletion automation."""
import logging
from typing import Dict, Optional, List, Tuple
from pathlib import Path
from playwright.sync_api import Page, Browser, BrowserContext, ElementHandle
import json
from difflib import get_close_matches

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_browser_context(browser: Browser) -> BrowserContext:
    """Create a new browser context with standard settings.
    
    Args:
        browser: Playwright browser instance
    
    Returns:
        Browser context with standard settings
    """
    return browser.new_context(
        viewport={'width': 1366, 'height': 768},  # Standard laptop screen size
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    )

def ensure_screenshots_dir() -> Path:
    """Ensure the screenshots directory exists.
    
    Returns:
        Path to screenshots directory
    """
    screenshots_dir = Path(__file__).parent.parent / 'screenshots'
    screenshots_dir.mkdir(exist_ok=True)
    return screenshots_dir

def take_screenshot(page: Page, name: str) -> Path:
    """Take a screenshot and save it to the screenshots directory.
    
    Args:
        page: Playwright page instance
        name: Name of the screenshot file (without extension)
    
    Returns:
        Path to the saved screenshot
    """
    screenshots_dir = ensure_screenshots_dir()
    screenshot_path = screenshots_dir / f"{name}.png"
    page.screenshot(path=str(screenshot_path))
    return screenshot_path

def analyze_form(page: Page) -> Dict:
    """Analyze the form structure and return field information."""
    try:
        # Get basic form fields
        fields = page.evaluate('''() => {
            return Array.from(document.querySelectorAll('input, select, textarea, [role="combobox"], [role="listbox"]'))
                .map(field => {
                    // Determine the correct type based on element properties
                    let fieldType = field.type || 'text';
                    if (field.getAttribute('role') === 'listbox') {
                        fieldType = 'option';
                    } else if (field.getAttribute('role') === 'combobox') {
                        fieldType = 'autocomplete';
                    } else if (field.tagName === 'SELECT') {
                        fieldType = 'option';
                    }
                    
                    return {
                        id: field.id || field.name || '',
                        name: field.name || '',
                        type: fieldType,
                        label: field.getAttribute('aria-label') || '',
                        required: field.hasAttribute('required'),
                        value: field.value || '',
                        role: field.getAttribute('role') || ''
                    };
                });
        }''')

        # Get submit button
        submit_button = page.query_selector('button[type="submit"], input[type="submit"], button:has-text("Submit")')
        button_info = None
        if submit_button:
            button_info = {
                'type': 'explicit',
                'id': submit_button.get_attribute('id') or '',
                'text': submit_button.inner_text().strip() or submit_button.get_attribute('value') or '',
                'selector': 'button[type="submit"], input[type="submit"], button:has-text("Submit")'
            }

        return {
            'fields': fields,
            'submit_button': button_info
        }

    except Exception as e:
        logger.error(f"Error analyzing form: {str(e)}")
        return {'fields': [], 'submit_button': None}

def submit_form(page: Page, submit_info: Optional[Dict] = None) -> None:
    """Submit a form using the provided submit button information.
    
    Args:
        page: Playwright page instance
        submit_info: Optional dictionary containing submit button information
    
    Raises:
        ValueError: If form cannot be submitted
    """
    try:
        if submit_info and submit_info.get('selector'):
            # Try to submit using the provided selector
            submit_button = page.query_selector(submit_info['selector'])
            if submit_button:
                submit_button.click()
                page.wait_for_load_state('networkidle')
                return

        # Fallback strategies if no submit_info or selector didn't work
        strategies = [
            'button[type="submit"], input[type="submit"]',  # Standard submit buttons
            'button:has-text("Submit"), input[value*="Submit"]',  # Text-based submit
            'button:has-text("Send"), input[value*="Send"]',
            'button:has-text("Continue"), input[value*="Continue"]',
            'button.primary, button[class*="primary"]',  # Primary action buttons
            'button[class*="submit"], button[class*="action"]'
        ]

        for selector in strategies:
            submit_button = page.query_selector(selector)
            if submit_button:
                submit_button.click()
                page.wait_for_load_state('networkidle')
                return

        raise ValueError("Could not find a suitable submit button")
    except Exception as e:
        raise ValueError(f"Error submitting form: {str(e)}")

def analyze_dropdown_behavior(page: Page, field_id: str, value: str, llm) -> Dict:
    """Use LLM to analyze how to interact with a dropdown field.
    
    Args:
        page: Playwright page instance
        field_id: ID of the field to analyze
        value: Value to select
        llm: LLM instance for analysis
    
    Returns:
        Dictionary with analysis results and recommended actions
    """
    try:
        # Get field information
        field = page.query_selector(f"#{field_id}, [name='{field_id}'], [id*='{field_id}'], [name*='{field_id}']")
        if not field:
            raise ValueError(f"Field {field_id} not found")

        # Get field properties
        field_props = {
            'tag': field.evaluate('el => el.tagName'),
            'type': field.evaluate('el => el.type'),
            'role': field.evaluate('el => el.getAttribute("role")'),
            'class': field.evaluate('el => el.className'),
            'aria-expanded': field.evaluate('el => el.getAttribute("aria-expanded")'),
            'aria-autocomplete': field.evaluate('el => el.getAttribute("aria-autocomplete")'),
        }

        # Click field and wait for dropdown
        field.click()
        page.wait_for_timeout(1000)

        # Get dropdown information
        dropdown = page.query_selector('[role="listbox"], .dropdown-menu, .select2-results, .autocomplete-results, [role="combobox"]')
        dropdown_info = {}
        if dropdown:
            dropdown_info = {
                'tag': dropdown.evaluate('el => el.tagName'),
                'role': dropdown.evaluate('el => el.getAttribute("role")'),
                'class': dropdown.evaluate('el => el.className'),
                'visible': dropdown.is_visible(),
                'options': dropdown.evaluate('''el => {
                    const options = Array.from(el.querySelectorAll('[role="option"], .dropdown-item, .select2-results__option, .autocomplete-item, li, div'));
                    return options.map(opt => ({
                        text: opt.textContent,
                        tag: opt.tagName,
                        role: opt.getAttribute('role'),
                        class: opt.className,
                        visible: opt.offsetParent !== null
                    }));
                }''')
            }

        # Construct prompt for LLM
        prompt = f"""Analyze this dropdown field behavior and recommend how to interact with it.
        Field Properties: {json.dumps(field_props, indent=2)}
        Dropdown Information: {json.dumps(dropdown_info, indent=2)}
        Target Value: {value}

        Based on the field and dropdown properties, determine:
        1. What type of dropdown/autocomplete this is
        2. How to best interact with it (typing, clicking, keyboard)
        3. What selectors to use to find and select the option
        4. Any special handling needed

        Return a JSON object with:
        - dropdown_type: Type of dropdown (e.g., "standard", "autocomplete", "combobox")
        - interaction_method: How to interact ("type", "click", "keyboard", or combination)
        - selectors: List of selectors to try in order for finding the dropdown option (not the input field)
        - special_handling: Any special steps needed
        - explanation: Brief explanation of the analysis
        - wait_time: How long to wait for dropdown to appear after typing (in milliseconds)
        """

        # Get LLM analysis
        response = llm.invoke(prompt)
        try:
            analysis = json.loads(response.content)
            logger.info(f"Dropdown analysis for {field_id}: {json.dumps(analysis, indent=2)}")
            return analysis
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response: {response.content}")
            return {}

    except Exception as e:
        logger.error(f"Error analyzing dropdown: {str(e)}")
        return {}

def fill_autocomplete_field(page: Page, field_id: str, value: str, llm=None, wait_time: int = 1000) -> None:
    """Fill an autocomplete/dropdown field by typing and selecting from dropdown.
    
    Args:
        page: Playwright page instance
        field_id: ID of the field to fill
        value: Value to fill in and select
        llm: Optional LLM instance for dropdown analysis
        wait_time: Time to wait for dropdown in milliseconds
    
    Raises:
        ValueError: If field not found or value cannot be selected
    """
    try:
        logger.info(f"Attempting to fill autocomplete field {field_id} with value {value}")
        
        # Try different selectors to find the field
        selectors = [
            f"#{field_id}",  # ID selector
            f"[name='{field_id}']",  # Name selector
            f"[id*='{field_id}']",  # Partial ID match
            f"[name*='{field_id}']"  # Partial name match
        ]

        field = None
        for selector in selectors:
            field = page.query_selector(selector)
            if field:
                logger.info(f"Found field using selector: {selector}")
                break

        if not field:
            raise ValueError(f"Field {field_id} not found")

        # If LLM is provided, analyze the dropdown behavior
        if llm:
            analysis = analyze_dropdown_behavior(page, field_id, value, llm)
            if analysis:
                logger.info(f"Using LLM analysis for dropdown interaction: {analysis['explanation']}")
                
                # Click the field to focus it
                field.click()
                field.fill("")  # Clear existing value
                
                # Follow the recommended interaction method
                if 'type' in analysis['interaction_method']:
                    # Type the value
                    field.fill(value)
                    # Wait for dropdown to appear
                    wait_time = analysis.get('wait_time', 1000)
                    logger.info(f"Waiting {wait_time}ms for dropdown to appear")
                    page.wait_for_timeout(wait_time)
                    
                    # Try to find and click the dropdown option
                    for selector in analysis['selectors']:
                        try:
                            logger.info(f"Trying to find dropdown option with selector: {selector}")
                            # Wait for the option to be visible
                            option = page.wait_for_selector(selector, timeout=2000)
                            if option:
                                logger.info("Found dropdown option, attempting to click")
                                # Scroll the option into view if needed
                                option.scroll_into_view_if_needed()
                                # Click the option
                                option.click()
                                # Wait a bit to ensure the selection is registered
                                page.wait_for_timeout(500)
                                logger.info("Successfully clicked dropdown option")
                                return
                        except Exception as e:
                            logger.warning(f"Failed to select option with selector {selector}: {str(e)}")
                            continue
                    
                    # If no option was found with selectors, try keyboard navigation
                    if 'keyboard' in analysis['interaction_method']:
                        try:
                            logger.info("Attempting keyboard navigation")
                            field.press("Enter")
                            page.wait_for_timeout(500)
                            if field.input_value() == value:
                                logger.info("Successfully selected option using keyboard")
                                return
                        except Exception as e:
                            logger.warning(f"Keyboard navigation failed: {str(e)}")

        # Fallback to standard behavior if LLM analysis fails or isn't provided
        logger.info("Falling back to standard dropdown interaction")
        field.click()
        field.fill("")
        field.fill(value)
        page.wait_for_timeout(wait_time)
        
        # Try different strategies to find and click the dropdown option
        dropdown_selectors = [
            f'[role="option"]:has-text("{value}")',
            f'[role="listbox"] [role="option"]:has-text("{value}")',
            f'.dropdown-item:has-text("{value}")',
            f'.select2-results__option:has-text("{value}")',
            f'.autocomplete-item:has-text("{value}")',
            f'li:has-text("{value}")',
            f'div:has-text("{value}")',
            f'text="{value}"'
        ]

        for selector in dropdown_selectors:
            try:
                logger.info(f"Trying fallback selector: {selector}")
                option = page.wait_for_selector(selector, timeout=2000)
                if option:
                    option.scroll_into_view_if_needed()
                    option.click()
                    page.wait_for_timeout(500)
                    logger.info(f"Successfully selected option using fallback selector: {selector}")
                    return
            except Exception as e:
                logger.warning(f"Fallback selector {selector} failed: {str(e)}")
                continue

        raise ValueError(f"Could not find or select dropdown option for value: {value}")

    except Exception as e:
        logger.error(f"Error filling autocomplete field {field_id}: {str(e)}")
        raise ValueError(f"Error filling autocomplete field {field_id}: {str(e)}")

def analyze_form_field(page: Page, field_id: str, llm) -> Dict:
    """Use LLM to analyze a form field and determine how to interact with it.
    
    Args:
        page: Playwright page instance
        field_id: ID of the field to analyze
        llm: LLM instance for analysis
    
    Returns:
        Dictionary with analysis results and recommended actions
    """
    try:
        # Get field information
        field = page.query_selector(f"#{field_id}, [name='{field_id}'], [id*='{field_id}'], [name*='{field_id}']")
        if not field:
            raise ValueError(f"Field {field_id} not found")

        # Get field properties and structure
        field_info = {
            'tag': field.evaluate('el => el.tagName'),
            'type': field.evaluate('el => el.type'),
            'role': field.evaluate('el => el.getAttribute("role")'),
            'class': field.evaluate('el => el.className'),
            'aria-expanded': field.evaluate('el => el.getAttribute("aria-expanded")'),
            'aria-autocomplete': field.evaluate('el => el.getAttribute("aria-autocomplete")'),
            'aria-haspopup': field.evaluate('el => el.getAttribute("aria-haspopup")'),
            'aria-controls': field.evaluate('el => el.getAttribute("aria-controls")'),
            'aria-labelledby': field.evaluate('el => el.getAttribute("aria-labelledby")'),
            'aria-label': field.evaluate('el => el.getAttribute("aria-label")'),
            'innerHTML': field.evaluate('el => el.innerHTML'),
            'parentHTML': field.evaluate('el => el.parentElement.innerHTML'),
        }

        # Click the field to see what happens
        field.click()
        page.wait_for_timeout(1000)

        # Get any visible options
        options = page.evaluate('''() => {
            const elements = Array.from(document.querySelectorAll('div, li, span, button'));
            return elements
                .filter(el => el.offsetParent !== null)  // Only visible elements
                .map(el => ({
                    text: el.textContent.trim(),
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    class: el.className
                }))
                .filter(opt => opt.text.length > 0);
        }''')

        # Ask LLM to analyze the field
        prompt = f"""Analyze this form field and determine how to interact with it to select an option.
        Field Information: {json.dumps(field_info, indent=2)}
        Available Options: {json.dumps(options, indent=2)}

        Based on the field properties and available options, determine:
        1. What type of field this is (dropdown, radio, custom select, etc.)
        2. How to best interact with it
        3. What selectors to use to find and select options

        Return a JSON object with:
        - field_type: Type of field (e.g., "custom_select", "radio_group", "custom_dropdown")
        - selectors: List of selectors to try in order
        - explanation: Brief explanation of the analysis
        """

        # Get LLM analysis
        response = llm.invoke(prompt)
        try:
            analysis = json.loads(response.content)
            logger.info(f"Field analysis for {field_id}: {json.dumps(analysis, indent=2)}")
            return analysis
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response: {response.content}")
            return {}

    except Exception as e:
        logger.error(f"Error analyzing field: {str(e)}")
        return {}

def select_option(page: Page, field_id: str, target_value: str) -> None:
    """Select an option in a form field by clicking and finding the closest match."""
    try:
        logger.info(f"Attempting to select '{target_value}' in field {field_id}")
        
        # Find the field
        field = page.query_selector(f"#{field_id}, [name='{field_id}'], [aria-label*='{field_id}']")
        if not field:
            raise ValueError(f"Field {field_id} not found")
        
        # Get field properties to understand its type
        field_role = field.get_attribute('role')
        logger.info(f"Field {field_id} has role: {field_role}")
        
        # Click the field to open/activate it
        field.click()
        page.wait_for_timeout(1000)  # Wait for options to appear
        
        # For listbox fields, look for options within the listbox container
        if field_role == 'listbox':
            logger.info("Field is a listbox, looking for options within the listbox")
            
            # Try to find options within this specific listbox
            options = page.evaluate(f'''() => {{
                const listbox = document.querySelector('#{field_id}');
                if (!listbox) return [];
                
                const optionElements = Array.from(listbox.querySelectorAll('[role="option"], div, li, span'));
                return optionElements
                    .filter(el => el.offsetParent !== null)  // Only visible elements
                    .map(el => ({{
                        text: el.textContent.trim(),
                        tag: el.tagName,
                        role: el.getAttribute('role'),
                        class: el.className
                    }}))
                    .filter(opt => opt.text.length > 0);
            }}''')
            
            logger.info(f"Found {len(options)} options in listbox: {[opt['text'] for opt in options]}")
            
            # Find the closest match
            option_texts = [opt['text'] for opt in options]
            matches = get_close_matches(target_value.lower(), [text.lower() for text in option_texts], n=1, cutoff=0.6)
            
            if not matches:
                raise ValueError(f"Could not find option matching '{target_value}' in {option_texts}")
            
            best_match = matches[0]
            logger.info(f"Found closest match: '{best_match}' for target '{target_value}'")
            
            # Click the matching option within the listbox
            option_selector = f"#{field_id} [role='option']:has-text('{best_match}'), #{field_id} div:has-text('{best_match}'), #{field_id} li:has-text('{best_match}'), #{field_id} span:has-text('{best_match}')"
            option = page.query_selector(option_selector)
            
            if option:
                option.scroll_into_view_if_needed()
                option.click()
                logger.info(f"Successfully clicked option '{best_match}' within listbox")
            else:
                # Fallback: try clicking by text within the listbox
                page.click(f"#{field_id} >> text='{best_match}'")
                logger.info(f"Successfully clicked option '{best_match}' using fallback method")
        
        else:
            # For other field types, use the original logic
            logger.info("Field is not a listbox, using generic option selection")
            
            # Get all visible text that could be options
            options = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('div, li, span, button'))
                    .filter(el => el.offsetParent !== null)
                    .map(el => el.textContent.trim())
                    .filter(text => text.length > 0);
            }''')
            
            # Find the closest match
            matches = get_close_matches(target_value.lower(), [text.lower() for text in options], n=1, cutoff=0.6)
            if not matches:
                raise ValueError(f"Could not find option matching '{target_value}' in {options}")
            
            best_match = matches[0]
            logger.info(f"Found closest match: '{best_match}' for target '{target_value}'")
            
            # Click the matching option
            page.click(f"text='{best_match}'")
            logger.info("Successfully clicked option")
        
    except Exception as e:
        logger.error(f"Error selecting option in field {field_id}: {str(e)}")
        raise ValueError(f"Error selecting option in field {field_id}: {str(e)}")

def fill_form_field(page: Page, field_id: str, value: str, field_type: str = 'text') -> None:
    """Fill a form field with the given value."""
    try:
        logger.info(f"Filling field {field_id} with value {value} (type: {field_type})")
        
        if field_type == 'autocomplete':
            fill_autocomplete_field(page, field_id, value)
        elif field_type == 'option':
            select_option(page, field_id, value)
        else:
            # Find the field
            field = page.query_selector(f"#{field_id}, [name='{field_id}'], [aria-label*='{field_id}']")
            if not field:
                raise ValueError(f"Field {field_id} not found")

            # Fill the field
            field.fill(value)
            logger.info(f"Successfully filled field {field_id}")

    except Exception as e:
        logger.error(f"Error filling field {field_id}: {str(e)}")
        raise ValueError(f"Error filling field {field_id}: {str(e)}")

def wait_for_navigation(page: Page, timeout: Optional[int] = None) -> None:
    """Wait for page navigation to complete.
    
    Args:
        page: Playwright page instance
        timeout: Optional timeout in milliseconds
    """
    page.wait_for_load_state('networkidle', timeout=timeout)
