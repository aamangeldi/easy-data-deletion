"""Gmail API utility functions for data deletion automation."""
import os
import pickle
from typing import Optional, List, Dict
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import time

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def get_gmail_service(creds: Optional[Credentials] = None) -> build:
    """Get Gmail API service instance.
    
    Args:
        creds: Optional credentials object. If not provided, will try to load from token.pickle.
    
    Returns:
        Gmail API service instance.
    
    Raises:
        FileNotFoundError: If credentials.json is not found.
    """
    if creds is None:
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError("credentials.json not found. See README.md for instructions.")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)

def ensure_label_exists(service: build, label_name: str) -> str:
    """Ensure the label exists and return its ID.
    
    Args:
        service: Gmail API service instance
        label_name: Name of the label to create/verify
    
    Returns:
        Label ID
    """
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    for label in labels:
        if label['name'] == label_name:
            return label['id']

    label_object = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    created_label = service.users().labels().create(userId='me', body=label_object).execute()
    return created_label['id']

def create_deletion_email(first_name: str, last_name: str, user_email: str, broker_name: str) -> MIMEMultipart:
    """Create a data deletion request email.
    
    Args:
        first_name: User's first name
        last_name: User's last name
        user_email: User's email address
        broker_name: Name of the data broker
    
    Returns:
        MIME multipart message object
    """
    msg = MIMEMultipart()
    msg['Subject'] = f'[Data Deletion Request] {broker_name} - {first_name} {last_name}'

    body = f"""Dear {broker_name} Data Privacy Team,

I am writing to request the deletion of my personal information from your database under my rights under various privacy laws including CCPA, GDPR, and other applicable data protection regulations.

My information that may be in your database:
- First Name: {first_name}
- Last Name: {last_name}
- Email: {user_email}

Please confirm receipt of this request and provide information about the status of my data deletion request.

Thank you for your attention to this matter.

Best regards,
{first_name} {last_name}"""

    msg.attach(MIMEText(body, 'plain'))
    return msg

def send_email(service: build, msg: MIMEMultipart, label_id: Optional[str] = None) -> Dict:
    """Send an email using Gmail API.
    
    Args:
        service: Gmail API service instance
        msg: MIME multipart message object
        label_id: Optional label ID to apply to the sent message
    
    Returns:
        Response from Gmail API
    """
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    sent_message = service.users().messages().send(
        userId='me',
        body={'raw': raw_message}
    ).execute()

    if label_id:
        service.users().messages().modify(
            userId='me',
            id=sent_message['id'],
            body={'addLabelIds': [label_id]}
        ).execute()

    return sent_message

def check_confirmation_email(
    service: build,
    user_email: str,
    from_domains: List[str],
    wait_time: int = 300,
    check_interval: int = 10
) -> bool:
    """Check for confirmation email from specified domains.
    
    Args:
        service: Gmail API service instance
        user_email: User's email address
        from_domains: List of domains to check for emails from
        wait_time: Maximum time to wait in seconds
        check_interval: Time between checks in seconds
    
    Returns:
        True if confirmation email found, False otherwise
    """
    print(f"\nWaiting for confirmation email (up to {wait_time} seconds)...")
    
    from_query = ' OR '.join(f'from:{domain}' for domain in from_domains)
    query = f'({from_query}) to:{user_email} newer_than:1d'
    
    start_time = time.time()
    while time.time() - start_time < wait_time:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject = next(h['value'] for h in headers if h['name'].lower() == 'subject')
            
            if 'confirmation' in subject.lower():
                print(f"\n✓ Found confirmation email: {subject}")
                return True

        time.sleep(check_interval)
        print(".", end="", flush=True)

    print("\n✗ No confirmation email received within the time limit")
    return False
