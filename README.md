# easy-data-deletion

## Getting started

1. Create virtual env and install dependencies:
    ```
    python -m venv .venv
    source .venv/bin/activate
    pip install .
    ```

2. Create a `.env`:
    ```
    cp .env.template .env
    ```

3. Get an OpenAI API key and fill it in `.env`. Also add ANTICAPTCHA_API_KEY if using CAPTCHA solving features.

4. Download Google OAuth credentials into the main directory of this repo under `credentials.json` (Gmail accounts only).
    - Go to https://console.cloud.google.com/
    - Create a new project or select existing one
    - Enable Gmail API ("APIs & Services" > "Library", search for Gmail API, click "Enable")
    - Create OAuth 2.0 credentials ("APIs & Services" > "Credentials"; click "Create Credentials" > "OAuth client ID"; choose "Desktop app" type)
    - Download and save as `credentials.json` in the main directory of this repo
    - **Note:** The OAuth system only works with Gmail accounts. Other email providers are not supported.

## Running the scripts

### Generic broker agent (recommended)
1. Run the script for any supported broker:
```
python broker_agent.py --broker Acxiom --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --date-of-birth MM/DD/YYYY --address "Your Address" --city <City> --state <XX> --zip-code <XXXXX>
```

### Legacy scripts
#### Acxiom agent
```
python acxiom_agent.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --date-of-birth MM/DD/YYYY --address "Your Address" --city <City> --state <XX> --zip-code <XXXXX>
```

#### Request via email script
```
python request_via_email.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --dev --test-email <Test-Email-To-Send-Emails-To>
```

#### Request via form script
```
python request_via_form.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email>
```

## Contributing

To set up git hooks properly, please run
`git config core.hooksPath .githooks`
(once). This will enable hooks such as running `yapf` on all python files
