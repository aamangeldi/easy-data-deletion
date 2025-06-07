"""Utility modules for data deletion automation."""

from .gmail import (
    get_gmail_service,
    ensure_label_exists,
    create_deletion_email,
    send_email,
    check_confirmation_email
)

from .browser import (
    create_browser_context,
    ensure_screenshots_dir,
    take_screenshot,
    analyze_form,
    fill_form_field,
    submit_form,
    wait_for_navigation
)

from .agent import (
    create_browser_tools,
    create_form_agent,
    get_default_form_prompt
)

from .broker import (
    get_broker_url,
    read_broker_data,
    get_broker_email_domains,
    ACXIOM_DELETE_FORM_URL,
    ACXIOM_OPTOUT_URL
)

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
    
    # Agent utilities
    'create_browser_tools',
    'create_form_agent',
    'get_default_form_prompt',
    
    # Broker utilities
    'get_broker_url',
    'read_broker_data',
    'get_broker_email_domains',
    'ACXIOM_DELETE_FORM_URL',
    'ACXIOM_OPTOUT_URL'
] 