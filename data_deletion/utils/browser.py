"""Browser automation utility functions for data deletion automation."""
from typing import Dict, Optional, List
from pathlib import Path
from playwright.sync_api import Page, Browser, BrowserContext, ElementHandle

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
    """Analyze a form's structure and elements.
    
    Args:
        page: Playwright page instance
    
    Returns:
        Dictionary containing form structure information
    """
    form_info = {
        'fields': [],
        'submit_button': None,
        'form_element': None
    }

    # Find all form elements
    forms = page.query_selector_all('form')
    if not forms:
        # If no form element found, look for input fields that might be part of a form
        inputs = page.query_selector_all('input, select, textarea')
        if inputs:
            form_info['form_element'] = {'type': 'implicit', 'fields': len(inputs)}
    else:
        # Analyze each form
        for form in forms:
            form_id = form.get_attribute('id') or ''
            form_class = form.get_attribute('class') or ''
            form_info['form_element'] = {
                'type': 'explicit',
                'id': form_id,
                'class': form_class
            }

    # Find all input fields
    inputs = page.query_selector_all('input, select, textarea')
    for input_elem in inputs:
        field_info = {
            'id': input_elem.get_attribute('id') or '',
            'name': input_elem.get_attribute('name') or '',
            'type': input_elem.get_attribute('type') or 'text',
            'label': '',
            'placeholder': input_elem.get_attribute('placeholder') or '',
            'required': input_elem.get_attribute('required') is not None,
            'value': input_elem.get_attribute('value') or ''
        }

        # Try to find associated label
        if field_info['id']:
            label = page.query_selector(f'label[for="{field_info["id"]}"]')
            if label:
                field_info['label'] = label.inner_text().strip()
        else:
            # Look for parent label
            parent_label = input_elem.evaluate('elem => elem.closest("label")')
            if parent_label:
                field_info['label'] = parent_label.inner_text().strip()

        form_info['fields'].append(field_info)

    # Find submit button with various strategies
    submit_button = None
    button_info = None

    # Strategy 1: Look for explicit submit buttons
    submit_button = page.query_selector('button[type="submit"], input[type="submit"]')
    if submit_button:
        button_info = {
            'type': 'explicit_submit',
            'id': submit_button.get_attribute('id') or '',
            'name': submit_button.get_attribute('name') or '',
            'text': submit_button.inner_text().strip() or submit_button.get_attribute('value') or '',
            'selector': 'button[type="submit"], input[type="submit"]'
        }

    # Strategy 2: Look for buttons with submit-like text
    if not submit_button:
        submit_texts = ['submit', 'send', 'continue', 'next', 'proceed', 'request', 'delete', 'remove']
        for text in submit_texts:
            button = page.query_selector(f'button:has-text("{text}"), input[value*="{text}"]')
            if button:
                submit_button = button
                button_info = {
                    'type': 'text_match',
                    'id': button.get_attribute('id') or '',
                    'name': button.get_attribute('name') or '',
                    'text': button.inner_text().strip() or button.get_attribute('value') or '',
                    'selector': f'button:has-text("{text}"), input[value*="{text}"]'
                }
                break

    # Strategy 3: Look for primary action buttons
    if not submit_button:
        primary_buttons = page.query_selector_all('button.primary, button[class*="primary"], button[class*="submit"], button[class*="action"]')
        if primary_buttons:
            submit_button = primary_buttons[0]  # Take the first primary button
            button_info = {
                'type': 'primary_action',
                'id': submit_button.get_attribute('id') or '',
                'name': submit_button.get_attribute('name') or '',
                'text': submit_button.inner_text().strip(),
                'selector': 'button.primary, button[class*="primary"], button[class*="submit"], button[class*="action"]'
            }

    form_info['submit_button'] = button_info
    return form_info

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

def fill_form_field(page: Page, field_id: str, value: str) -> None:
    """Fill a form field by its ID.
    
    Args:
        page: Playwright page instance
        field_id: ID of the field to fill
        value: Value to fill in
    
    Raises:
        ValueError: If field not found or cannot be filled
    """
    try:
        # Try different selectors to find the field
        selectors = [
            f"#{field_id}",  # ID selector
            f"[name='{field_id}']",  # Name selector
            f"[id*='{field_id}']",  # Partial ID match
            f"[name*='{field_id}']"  # Partial name match
        ]

        for selector in selectors:
            field = page.query_selector(selector)
            if field:
                field.fill(value)
                return

        raise ValueError(f"Field {field_id} not found")
    except Exception as e:
        raise ValueError(f"Error filling field {field_id}: {str(e)}")

def wait_for_navigation(page: Page, timeout: Optional[int] = None) -> None:
    """Wait for page navigation to complete.
    
    Args:
        page: Playwright page instance
        timeout: Optional timeout in milliseconds
    """
    page.wait_for_load_state('networkidle', timeout=timeout)
