"""Pytest configuration and fixtures for easy-data-deletion tests."""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
import json


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john.doe@example.com',
        'date_of_birth': '01/01/1990',
        'address': '123 Main St',
        'city': 'Anytown',
        'state': 'CA',
        'zip_code': '12345'
    }


@pytest.fixture
def minimal_broker_config():
    """Minimal broker configuration for AI fallback testing."""
    return {
        "name": "Test Broker",
        "type": "web_form",
        "url": "https://testbroker.com/privacy-form",
        "email_domains": ["testbroker.com"]
    }


@pytest.fixture
def full_broker_config():
    """Full broker configuration for deterministic testing."""
    return {
        "name": "Test Broker Full",
        "type": "web_form",
        "url": "https://testbroker.com/privacy-form",
        "email_domains": ["testbroker.com"],
        "form_config": {
            "state_format": "full",
            "field_mappings": {
                "firstName": "first_name",
                "lastName": "last_name",
                "email": "email"
            },
            "submission": {
                "method": "api_post",
                "endpoint": "https://testbroker.com/api/requests",
                "requires_jwt": True,
                "payload_template": {
                    "firstName": "{first_name}",
                    "lastName": "{last_name}",
                    "email": "{email}"
                },
                "headers": {
                    "content-type": "application/json"
                }
            }
        }
    }


@pytest.fixture
def mock_page():
    """Mock Playwright page for browser automation testing."""
    page = Mock()
    page.url = "https://testbroker.com/form"
    page.goto = Mock()
    page.wait_for_load_state = Mock()
    page.screenshot = Mock(return_value=b"fake_screenshot")
    return page


@pytest.fixture
def mock_browser_context():
    """Mock browser context for testing."""
    context = Mock()
    context.new_page = Mock()
    return context


@pytest.fixture
def mock_playwright():
    """Mock Playwright instance."""
    playwright = Mock()
    browser = Mock()
    playwright.chromium.launch = Mock(return_value=browser)
    return playwright


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary directory with broker configs for testing."""
    config_dir = tmp_path / "broker_configs"
    config_dir.mkdir()

    # Create test config files
    minimal_config = {
        "name": "Minimal Broker",
        "type": "web_form",
        "url": "https://minimal.com/form",
        "email_domains": ["minimal.com"]
    }

    full_config = {
        "name": "Full Broker",
        "type": "web_form",
        "url": "https://full.com/form",
        "email_domains": ["full.com"],
        "form_config": {
            "field_mappings": {
                "name": "first_name"
            },
            "submission": {
                "method": "api_post",
                "endpoint": "https://full.com/api"
            }
        }
    }

    (config_dir / "minimal.json").write_text(json.dumps(minimal_config))
    (config_dir / "full.json").write_text(json.dumps(full_config))

    return config_dir
