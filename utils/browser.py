"""Browser automation utility functions for data deletion automation."""
import logging
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime
from playwright.sync_api import Page, Browser, BrowserContext, ElementHandle
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
        viewport={
            'width': 1366,
            'height': 768
        },  # Standard laptop screen size
        user_agent=
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
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
    """Take a screenshot and save it to the screenshots directory with timestamp.

    Args:
        page: Playwright page instance
        name: Name of the screenshot file (without extension)

    Returns:
        Path to the saved screenshot
    """
    screenshots_dir = ensure_screenshots_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshots_dir / f"{name}_{timestamp}.png"
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
        submit_button = page.query_selector(
            'button[type="submit"], input[type="submit"], button:has-text("Submit")'
        )
        button_info = None
        if submit_button:
            button_info = {
                'type':
                'explicit',
                'id':
                submit_button.get_attribute('id') or '',
                'text':
                submit_button.inner_text().strip()
                or submit_button.get_attribute('value') or '',
                'selector':
                'button[type="submit"], input[type="submit"], button:has-text("Submit")'
            }

        return {'fields': fields, 'submit_button': button_info}

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


def _find_field_by_id(page: Page, field_id: str) -> Optional[ElementHandle]:
    """Find a form field using common selector strategies.
    
    Args:
        page: Playwright page instance
        field_id: ID of the field to find
        
    Returns:
        ElementHandle if found, None otherwise
    """
    selectors = [
        f"#{field_id}",  # ID selector
        f"[name='{field_id}']",  # Name selector
        f"[id*='{field_id}']",  # Partial ID match
        f"[name*='{field_id}']",  # Partial name match
        f"[aria-label*='{field_id}']",  # Aria label match
    ]

    for selector in selectors:
        field = page.query_selector(selector)
        if field:
            logger.info(f"Found field using selector: {selector}")
            return field

    return None


def _find_dropdown_option(page: Page,
                          value: str,
                          timeout: int = 2000) -> Optional[ElementHandle]:
    """Find a dropdown option using common selector strategies.
    
    Args:
        page: Playwright page instance
        value: Value to search for
        timeout: Timeout for waiting for selectors
        
    Returns:
        ElementHandle if found, None otherwise
    """
    # Simplified dropdown selectors - most common patterns
    selectors = [
        f'[role="option"]:has-text("{value}")', f'li:has-text("{value}")',
        f'div:has-text("{value}")', f'text="{value}"'
    ]

    for selector in selectors:
        try:
            option = page.wait_for_selector(selector, timeout=timeout)
            if option:
                logger.info(f"Found option using selector: {selector}")
                return option
        except Exception:
            continue

    return None


def fill_autocomplete_field(page: Page,
                            field_id: str,
                            value: str,
                            wait_time: int = 1000) -> None:
    """Fill an autocomplete/dropdown field by typing and selecting from dropdown.

    Args:
        page: Playwright page instance
        field_id: ID of the field to fill
        value: Value to fill in and select
        wait_time: Time to wait for dropdown in milliseconds

    Raises:
        ValueError: If field not found or value cannot be selected
    """
    """Fill an autocomplete/dropdown field by typing and selecting from dropdown.

    Args:
        page: Playwright page instance
        field_id: ID of the field to fill
        value: Value to fill in and select
        wait_time: Time to wait for dropdown in milliseconds

    Raises:
        ValueError: If field not found or value cannot be selected
    """
    try:
        logger.info(
            f"Attempting to fill autocomplete field {field_id} with value {value}"
        )

        # Find the field
        field = _find_field_by_id(page, field_id)
        if not field:
            raise ValueError(f"Field {field_id} not found")

        # Fill in value and wait for dropdown
        field.click()
        field.fill(value)
        page.wait_for_timeout(wait_time)

        # Find and click the dropdown option
        option = _find_dropdown_option(page, value)
        if not option:
            raise ValueError(
                f"Could not find dropdown option for value: {value}")

        option.scroll_into_view_if_needed()
        option.click()
        page.wait_for_timeout(500)
        logger.info(f"Successfully selected option: {value}")

    except Exception as e:
        logger.error(f"Error filling autocomplete field {field_id}: {str(e)}")
        raise ValueError(
            f"Error filling autocomplete field {field_id}: {str(e)}")


def select_option(page: Page, field_id: str, target_value: str) -> None:
    """Select an option in a form field by clicking and finding the closest match."""
    try:
        logger.info(
            f"Attempting to select '{target_value}' in field {field_id}")

        # Find the field
        field = _find_field_by_id(page, field_id)
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
            logger.info(
                "Field is a listbox, looking for options within the listbox")

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

            logger.info(
                f"Found {len(options)} options in listbox: {[opt['text'] for opt in options]}"
            )

            # Find the closest match
            option_texts = [opt['text'] for opt in options]
            matches = get_close_matches(
                target_value.lower(), [text.lower() for text in option_texts],
                n=1,
                cutoff=0.6)

            if not matches:
                raise ValueError(
                    f"Could not find option matching '{target_value}' in {option_texts}"
                )

            best_match = matches[0]
            logger.info(
                f"Found closest match: '{best_match}' for target '{target_value}'"
            )

            # Click the matching option within the listbox
            option_selector = f"#{field_id} [role='option']:has-text('{best_match}'), #{field_id} div:has-text('{best_match}'), #{field_id} li:has-text('{best_match}'), #{field_id} span:has-text('{best_match}')"
            option = page.query_selector(option_selector)

            if option:
                option.scroll_into_view_if_needed()
                option.click()
                logger.info(
                    f"Successfully clicked option '{best_match}' within listbox"
                )
            else:
                # Fallback: try clicking by text within the listbox
                page.click(f"#{field_id} >> text='{best_match}'")
                logger.info(
                    f"Successfully clicked option '{best_match}' using fallback method"
                )

        else:
            # For other field types, use the original logic
            logger.info(
                "Field is not a listbox, using generic option selection")

            # Get all visible text that could be options
            options = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('div, li, span, button'))
                    .filter(el => el.offsetParent !== null)
                    .map(el => el.textContent.trim())
                    .filter(text => text.length > 0);
            }''')

            # Find the closest match
            matches = get_close_matches(target_value.lower(),
                                        [text.lower() for text in options],
                                        n=1,
                                        cutoff=0.6)
            if not matches:
                raise ValueError(
                    f"Could not find option matching '{target_value}' in {options}"
                )

            best_match = matches[0]
            logger.info(
                f"Found closest match: '{best_match}' for target '{target_value}'"
            )

            # Click the matching option
            page.click(f"text='{best_match}'")
            logger.info("Successfully clicked option")

    except Exception as e:
        logger.error(f"Error selecting option in field {field_id}: {str(e)}")
        raise ValueError(
            f"Error selecting option in field {field_id}: {str(e)}")


def fill_form_deterministically(page: Page, field_mapping: Dict,
                                user_data: Dict) -> Dict:
    """Fill form using AI-discovered field mapping.
    
    Args:
        page: Playwright page instance
        field_mapping: Mapping from constrained AI
        user_data: User data to fill
        
    Returns:
        Dictionary with fill results
    """
    results = {"filled": 0, "failed": 0, "errors": []}

    for field_id, mapping in field_mapping.items():
        try:
            value = mapping['value']
            field_type = mapping.get('type', 'text')

            success = fill_form_field(page, field_id, value, field_type)
            if success:
                results["filled"] += 1
                print(
                    f"   ✓ Filled {field_id}: {mapping.get('user_key', 'unknown')}"
                )
            else:
                results["failed"] += 1
                results["errors"].append(f"Failed to fill {field_id}")

        except Exception as e:
            results["failed"] += 1
            error_msg = f"Error filling {field_id}: {str(e)}"
            results["errors"].append(error_msg)
            print(f"   ❌ {error_msg}")

    return results


def fill_form_field(page: Page,
                    field_id: str,
                    value: str,
                    field_type: str = 'text') -> bool:
    """Fill a form field with the given value.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(
            f"Filling field {field_id} with value {value} (type: {field_type})"
        )

        if field_type == 'autocomplete':
            fill_autocomplete_field(page, field_id, value)
        elif field_type == 'option':
            select_option(page, field_id, value)
        else:
            # Find the field using helper
            field = _find_field_by_id(page, field_id)
            if not field:
                raise ValueError(f"Field {field_id} not found")

            # Fill the field
            field.fill(value)
            logger.info(f"Successfully filled field {field_id}")

        return True

    except Exception as e:
        logger.error(f"Error filling field {field_id}: {str(e)}")
        return False


def wait_for_navigation(page: Page, timeout: Optional[int] = None) -> None:
    """Wait for page navigation to complete.
    
    Args:
        page: Playwright page instance
        timeout: Optional timeout in milliseconds
    """
    page.wait_for_load_state('networkidle', timeout=timeout)
