# easy-data-deletion

## Getting started

1. Create virtual env and install dependencies:
    ```
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements
    ```

2. Create a `.env`:
    ```
    cp .env.template .env
    ```

3. Get an OpenAI API key and fill it in `.env`.

4. Download Google OAuth credentials into the main directory of this repo under `credentials.json`.
    - Go to https://console.cloud.google.com/
    - Create a new project or select existing one
    - Enable Gmail API ("APIs & Services" > "Library", search for Gmail API, click "Enable")
    - Create OAuth 2.0 credentials ("APIs & Services" > "Credentials"; click "Create Credentials" > "OAuth client ID"; choose "Desktop app" type)
    - Download and save as `credentials.json` in the main directory of this repo

## Running the script
### Acxiom agent
1. Run the script:
```
python data_deletion/acxiom_agent.p --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --date-of-birth MM/DD/YYYY --address "Your Address" --city <City> --state <XX> --zip-code <XXXXX>
```

### Request via email script
1. Run the script:
    ```
    python data_deletion/request_via_email.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email> --dev --test-email <Test-Email-To-Send-Emails-To>
    ```

### Request via form script (Acxiom)
1. Run the script:
    ```
    python data_deletion/request_via_form.py --first-name <First-Name> --last-name <Last-Name> --email <Your-Email>
    ```

## Contributing

To set up git hooks properly, please run
`git config core.hooksPath .githooks`
(once). This will enable hooks such as running `yapf` on all python files
