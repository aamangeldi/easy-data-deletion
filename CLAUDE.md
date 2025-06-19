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
# Acxiom agent (AI-powered form automation)
python data_deletion/acxiom_agent.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --date-of-birth MM/DD/YYYY --address "Your Address" --city <City> --state <XX> --zip-code <XXXXX>

# Email-based deletion requests
python data_deletion/request_via_email.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --dev --test-email <Test-Email-To-Send-Emails-To>

# Generic form automation
python data_deletion/request_via_form.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email>
```

### Code Formatting
```bash
# Format Python files (done automatically via git hooks)
yapf -i <filename.py>
```

## Architecture

This is a CLI-based data deletion automation suite that combines traditional browser automation with AI agents to handle data broker removal requests.

### Core Components

- **Primary Scripts**: Three main entry points for different automation approaches:
  - `acxiom_agent.py`: Specialized Acxiom automation with AI agents, CAPTCHA solving, and email confirmation
  - `request_via_form.py`: Generic web form automation using Playwright + LangChain
  - `request_via_email.py`: Bulk email sending to brokers accepting email requests

- **Utils Module**: Modular utilities for different functionalities:
  - `agent.py`: LangChain AI agent framework with FormManager for intelligent form analysis
  - `browser.py`: Playwright browser automation with screenshot management
  - `gmail.py`: Gmail API integration with OAuth2 authentication
  - `broker.py`: CSV-based broker database management and domain mapping
  - `captcha.py`: Anti-captcha service integration for reCAPTCHA solving

### Data Flow

1. **Form Automation**: Uses LLM (OpenAI) to intelligently map user data to form fields
2. **Browser Control**: Playwright handles browser automation with sophisticated form detection
3. **Authentication**: Captures JWT tokens, handles CSRF tokens, and manages session state
4. **Email Integration**: Gmail API for sending requests and monitoring confirmations
5. **CAPTCHA Handling**: Automated solving using anti-captcha service

### Key Technologies

- **Poetry**: Dependency management
- **Playwright**: Browser automation
- **LangChain + OpenAI**: AI-powered form interaction
- **Gmail API**: Email automation with Google OAuth2
- **Anti-captcha**: CAPTCHA solving service

### Configuration Requirements

- `credentials.json`: Google OAuth2 credentials for Gmail API (download from Google Cloud Console)
- `.env`: Contains `OPENAI_API_KEY` (required) and optional `ANTICAPTCHA_API_KEY`
- `token.pickle`: Gmail API token persistence (generated automatically)
- `broker_lists/current.csv`: Broker database with URLs and contact information

### Authentication Setup

For Gmail integration:
1. Go to Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download as `credentials.json` in root directory

The system uses sophisticated authentication handling including JWT token capture, network monitoring, and email confirmation processing with domain-specific filtering.