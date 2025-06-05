# easy-data-deletion

## Getting started
1. Create virtual env and install dependencies:
    ```
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements
    ```

2. Download Google OAuth credentials into the main directory of this repo under `credentials.json`.
    - Go to https://console.cloud.google.com/
    - Create a new project or select existing one
    - Enable Gmail API ("APIs & Services" > "Library", search for Gmail API, click "Enable")
    - Create OAuth 2.0 credentials ("APIs & Services" > "Credentials"; click "Create Credentials" > "OAuth client ID"; choose "Desktop app" type)
    - Download and save as `credentials.json` in the main directory of this repo

3. Run in test mode:
    ```
    python data_deletion/request_via_email.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --dev --test-email <Test-Email-To-Send-Emails-To>
    ```
