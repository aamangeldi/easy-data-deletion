# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup and Dependencies
```bash
# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install .

# Set up environment variables
cp .env.template .env
# Edit .env to add OPENAI_API_KEY and ANTICAPTCHA_API_KEY

# Configure git hooks for automatic yapf formatting
git config core.hooksPath .githooks
```

### Running Scripts
```bash
# Unified broker agent - processes all brokers in broker_configs/
python broker_agent.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Gmail-Address> --date-of-birth MM/DD/YYYY --address "Your Address" --city <City> --state <XX> --zip-code <XXXXX>

# Process specific broker only
python broker_agent.py --broker <Broker-Name> --first-name <First-Name> --last-name <Last-Name> --email <Your-Gmail-Address> --date-of-birth MM/DD/YYYY --address "Your Address" --city <City> --state <XX> --zip-code <XXXXX>

# Example: Process all brokers
python broker_agent.py --first-name John --last-name Doe --email john.doe@gmail.com --state CA

# Example: Process only Acxiom
python broker_agent.py --broker Acxiom --first-name John --last-name Doe --email john.doe@gmail.com --state CA
```

### Code Formatting
```bash
# Format Python files (done automatically via git hooks)
yapf -i <filename.py>
```

## Architecture

This is a CLI-based data deletion automation suite that uses a hybrid approach: deterministic automation for known brokers and AI-powered fallback for new brokers.

### Core Components

- **Primary Script**: Single unified entry point:
  - `broker_agent.py`: Hybrid broker automation system that processes all brokers in broker_configs/

- **Broker Configurations**: JSON-based broker definitions in `broker_configs/`:
  - **Full configs**: Complete submission details for deterministic automation (e.g., `acxiom.json`)
  - **Minimal configs**: Just name and URL, triggers AI-powered form analysis

- **Utils Module**: Modular utilities for different functionalities:
  - `constrained_ai.py`: Constrained AI form mapper with validation and guardrails
  - `browser.py`: Playwright browser automation with form analysis and screenshot management
  - `gmail.py`: Gmail API integration with OAuth2 authentication and confirmation monitoring
  - `broker.py`: Broker configuration loading and user data preparation
  - `captcha.py`: Anti-captcha service integration for reCAPTCHA solving
  - `auth.py`: JWT and CSRF token extraction from web pages
  - `templates.py`: Template variable substitution for dynamic payloads
  - `state_utils.py`: State name/code conversion utilities

### Data Flow

**Hybrid Approach**: Deterministic by default, agentic when needed

**For Full Broker Configs** (deterministic):
1. **Configuration Loading**: Loads predefined broker configuration with field mappings and API endpoints
2. **Data Preparation**: Formats user data according to broker requirements (state format, date format, etc.)
3. **Authentication**: Extracts JWT/CSRF tokens from web pages using pattern matching
4. **Form Submission**: Direct API calls with proper headers and authentication
5. **CAPTCHA Handling**: Automated solving using anti-captcha service
6. **Email Confirmation**: Monitors Gmail for confirmation emails with time-based filtering

**For Minimal Broker Configs** (AI fallback):
1. **Form Analysis**: AI analyzes web form structure and identifies field types
2. **Field Mapping**: Constrained AI maps form fields to user data with validation
3. **Form Filling**: Browser automation fills form using AI-discovered mappings
4. **User Review**: Manual review step before submission for safety
5. **Config Generation**: Auto-generates full config from successful AI analysis for future use

### Key Technologies

- **Python packaging**: Standard pip-based dependency management (replaces Poetry)
- **Playwright**: Browser automation
- **LangChain + OpenAI**: Constrained AI form interaction with validation guardrails
- **Gmail API**: Email automation with Google OAuth2
- **Anti-captcha**: CAPTCHA solving service

### Configuration Requirements

- `credentials.json`: Google OAuth2 credentials for Gmail API (download from Google Cloud Console)
- `.env`: Contains `OPENAI_API_KEY` (required) and optional `ANTICAPTCHA_API_KEY`
- `token.pickle`: Gmail API token persistence (generated automatically)
- `broker_configs/*.json`: Individual broker configurations with submission details

### Authentication Setup

For Gmail integration (Gmail accounts only):
1. Go to Google Cloud Console (https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Gmail API ("APIs & Services" > "Library", search for Gmail API, click "Enable")
4. Create OAuth 2.0 credentials ("APIs & Services" > "Credentials"; click "Create Credentials" > "OAuth client ID"; choose "Desktop app" type)
5. Download as `credentials.json` in root directory

**Note:** The OAuth system only works with Gmail accounts. Other email providers are not supported.

### Broker Configuration Format

**Full Configuration** (deterministic automation):
```json
{
  "name": "Broker Name",
  "type": "web_form",
  "url": "https://broker.com/privacy-form",
  "email_domains": ["broker.com"],
  "form_config": {
    "state_format": "full",
    "field_mappings": { "firstName": "first_name" },
    "submission": {
      "method": "api_post",
      "endpoint": "https://api.broker.com/requests",
      "requires_jwt": true,
      "payload_template": { "firstName": "{first_name}" },
      "headers": { "content-type": "application/json" }
    }
  }
}
```

**Minimal Configuration** (triggers AI fallback):
```json
{
  "name": "New Broker",
  "type": "web_form",
  "url": "https://newbroker.com/privacy-request",
  "email_domains": ["newbroker.com"]
}
```

The system uses sophisticated authentication handling including JWT token capture, constrained AI form analysis with guardrails, and email confirmation processing with domain-specific filtering.