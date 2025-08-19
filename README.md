# Easy Data Deletion

Automated data broker deletion requests using a hybrid approach: deterministic automation for known brokers and AI-powered fallback for new brokers.

## Features

- **Unified System**: Single script processes all brokers automatically
- **Hybrid Approach**: Deterministic configs for speed, AI fallback for flexibility  
- **Gmail Integration**: Monitors confirmation emails automatically
- **Auto-Config Generation**: AI successes create configs for future deterministic use
- **CAPTCHA Solving**: Automated reCAPTCHA handling
- **Screenshot Documentation**: Visual record of all form interactions

## Getting started

1. Create virtual env and install dependencies:
    ```
    uv venv
    source .venv/bin/activate
    uv pip install .
    playwright install
    ```

2. Create a `.env`:
    ```
    cp .env.template .env
    ```

3. Set up env vars in `.env`: `OPENAI_API_KEY` from OpenAI and optionally `ANTICAPTCHA_API_KEY` from [AntiCaptcha](https://anti-captcha.com).

4. Download Google OAuth credentials into the main directory of this repo under `credentials.json` (Gmail accounts only).
    - Go to [Google Cloud Console](https://console.cloud.google.com/)
    - Create a new project or select existing one
    - Enable Gmail API ("APIs & Services" > "Library", search for Gmail API, click "Enable")
    - Create OAuth 2.0 credentials ("APIs & Services" > "Credentials"; click "Create Credentials" > "OAuth client ID"; choose "Desktop app" type)
    - Download and save as `credentials.json` in the main directory of this repo
    - **Note:** The OAuth system only works with Gmail accounts. Other email providers are not supported.

## Usage

### Process All Brokers (Recommended)
Run deletion requests across all configured brokers:
```bash
python broker_agent.py --first-name John --last-name Doe --email john.doe@gmail.com --state CA
```

### Process Specific Broker
Target a single broker:
```bash
python broker_agent.py --broker Acxiom --first-name John --last-name Doe --email john.doe@gmail.com --state CA
```

### Full Command Options
```bash
python broker_agent.py \
  --first-name <First-Name> \
  --last-name <Last-Name> \
  --email <Your-Gmail-Address> \
  --date-of-birth MM/DD/YYYY \
  --address "Your Address" \
  --city <City> \
  --state <XX> \
  --zip-code <XXXXX> \
  --broker <Optional-Broker-Name>
```

**Note**: Use Gmail addresses only - other email providers are not supported.

## How It Works

### Deterministic Mode
For brokers with full configurations (like Acxiom):
1. Loads predefined field mappings and API endpoints
2. Extracts authentication tokens (JWT, CSRF) automatically
3. Submits forms via direct API calls
4. Monitors Gmail for confirmation emails

### AI Fallback Mode  
For brokers with minimal configurations:
1. Uses AI to analyze form structure
2. Maps form fields to user data with validation
3. Fills forms using browser automation
4. Requires manual review before submission
5. Auto-generates full config for future deterministic use

## Broker Configurations

Brokers are defined in `broker_configs/*.json`. The system automatically detects:

- **Full configs**: Complete submission details → deterministic automation
- **Minimal configs**: Just name and URL → AI fallback

### Adding New Brokers

1. **Minimal config** (triggers AI analysis):
```json
{
  "name": "New Broker",
  "type": "web_form",
  "url": "https://newbroker.com/privacy-request",
  "email_domains": ["newbroker.com"]
}
```

2. **Full config** (deterministic automation):
```json
{
  "name": "Broker Name",
  "type": "web_form",
  "url": "https://broker.com/form",
  "email_domains": ["broker.com"],
  "form_config": {
    "field_mappings": { "firstName": "first_name" },
    "submission": {
      "method": "api_post",
      "endpoint": "https://api.broker.com/requests",
      "payload_template": { "firstName": "{first_name}" }
    }
  }
}
```

## Architecture

- **Single Entry Point**: `broker_agent.py` handles all brokers
- **Modular Utils**: Specialized modules for browser automation, AI analysis, authentication, etc.
- **JSON Configs**: Broker-specific configurations in `broker_configs/`
- **Gmail Integration**: OAuth2-based email monitoring
- **Screenshot Documentation**: Visual record in `screenshots/` directory

## Contributing

To set up git hooks properly, please run:
```bash
git config core.hooksPath .githooks
```
This enables automatic code formatting with `yapf` on commit.
