"""Utility modules for data deletion automation."""

from .gmail import (get_gmail_service, ensure_label_exists,
                    create_deletion_email, send_email,
                    check_confirmation_email)

from .browser import (create_browser_context, ensure_screenshots_dir,
                      take_screenshot, analyze_form, fill_form_field,
                      submit_form, wait_for_navigation,
                      fill_form_deterministically)

from .broker import (get_broker_url, read_broker_data,
                     get_broker_email_domains, ACXIOM_DELETE_FORM_URL,
                     ACXIOM_OPTOUT_URL, load_broker_config, prepare_user_data)

from .captcha import (solve_captcha)

from .state_utils import (validate_state_input, get_state_format, StateHandler,
                          STATE_MAPPING)

from .auth import (extract_auth_tokens)

from .validation import (validate_date_of_birth)

from .templates import (substitute_template_variables)

__all__ = [
    # Gmail utilities
    'get_gmail_service',
    'ensure_label_exists',
    'create_deletion_email',
    'send_email',
    'check_confirmation_email',

    # Browser utilities
    'create_browser_context',
    'ensure_screenshots_dir',
    'take_screenshot',
    'analyze_form',
    'fill_form_field',
    'submit_form',
    'wait_for_navigation',
    'fill_form_deterministically',

    # Broker utilities
    'get_broker_url',
    'read_broker_data',
    'get_broker_email_domains',
    'ACXIOM_DELETE_FORM_URL',
    'ACXIOM_OPTOUT_URL',
    'load_broker_config',
    'prepare_user_data',

    # Captcha utilities
    'solve_captcha',

    # State utilities
    'validate_state_input',
    'get_state_format',
    'StateHandler',
    'STATE_MAPPING',

    # Auth utilities
    'extract_auth_tokens',

    # Validation utilities
    'validate_date_of_birth',

    # Template utilities
    'substitute_template_variables'
]
