import argparse
import csv
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    """Get Gmail API service instance."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("credentials.json not found. See README.md for instructions.")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)

def read_broker_data(csv_path: str) -> List[Dict[str, str]]:
    """Read data broker information from CSV file."""
    brokers = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['email'] != 'no email':
                brokers.append(row)
    return brokers

def create_deletion_email(first_name: str, last_name: str, user_email: str, broker_name: str) -> MIMEMultipart:
    """Create a data deletion request email."""
    msg = MIMEMultipart()
    msg['Subject'] = f'Data Deletion Request - {first_name} {last_name}'
    
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

def send_deletion_requests(first_name: str, last_name: str, user_email: str, test_email: str = None):
    """Send data deletion requests to all data brokers with email addresses."""
    # Get the directory of the current script
    script_dir = Path(__file__).parent
    csv_path = script_dir / 'broker_lists' / 'current.csv'
    
    brokers = read_broker_data(str(csv_path))
    
    # Get Gmail service
    service = get_gmail_service()
    
    for broker in brokers:
        try:
            msg = create_deletion_email(first_name, last_name, user_email, broker['name'])
            msg['From'] = user_email
            
            # If in dev mode, send to test email instead
            if test_email:
                msg['To'] = test_email
                print(f"DEV MODE: Would send to {broker['name']} ({broker['email']})")
            else:
                msg['To'] = broker['email']
            
            # Convert message to raw format
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            # Send message
            service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            if test_email:
                print(f"✓ Sent test email to {test_email} (simulating {broker['name']})")
            else:
                print(f"✓ Sent deletion request to {broker['name']} ({broker['email']})")
        except Exception as e:
            print(f"✗ Failed to send to {broker['name']}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Send data deletion requests to data brokers.')
    parser.add_argument('--first-name', required=True, help='Your first name')
    parser.add_argument('--last-name', required=True, help='Your last name')
    parser.add_argument('--email', required=True, help='Your Gmail address')
    parser.add_argument('--dev', action='store_true', help='Run in development mode (sends to test email)')
    parser.add_argument('--test-email', help='Test email address for development mode')
    
    args = parser.parse_args()
    
    if args.dev and not args.test_email:
        parser.error("--test-email is required when using --dev flag")
    
    send_deletion_requests(
        args.first_name,
        args.last_name,
        args.email,
        args.test_email if args.dev else None
    )

if __name__ == '__main__':
    main()
