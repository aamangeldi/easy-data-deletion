"""Browser automation utility functions for data deletion automation."""
from typing import Dict, Optional
from pathlib import Path
from playwright.sync_api import Page, Browser, BrowserContext

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
    """Analyze the form structure and return field information.
    
    Args:
        page: Playwright page instance
    
    Returns:
        Dictionary containing form structure information
    """
    form_info = {
        'fields': [],
        'submit_button': None,
        'page_title': page.title(),
        'url': page.url
    }

    # Get all form elements
    form_elements = page.query_selector_all('input, select, textarea')
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
        page.fill(f"#{field_id}", value)
    except Exception as e:
        raise ValueError(f"Error filling field {field_id}: {str(e)}")

def submit_form(page: Page) -> None:
    """Submit a form by clicking the submit button.
    
    Args:
        page: Playwright page instance
    
    Raises:
        ValueError: If submit button not found or form cannot be submitted
    """
    try:
        submit_button = page.query_selector('button[type="submit"], input[type="submit"]')
        if submit_button:
            submit_button.click()
            page.wait_for_load_state('networkidle')
        else:
            raise ValueError("Submit button not found")
    except Exception as e:
        raise ValueError(f"Error submitting form: {str(e)}")

def wait_for_navigation(page: Page, timeout: Optional[int] = None) -> None:
    """Wait for page navigation to complete.
    
    Args:
        page: Playwright page instance
        timeout: Optional timeout in milliseconds
    """
    page.wait_for_load_state('networkidle', timeout=timeout)
