"""Script to send data deletion requests via email."""
import argparse
import os
from dotenv import load_dotenv

from utils import (
    get_gmail_service,
    ensure_label_exists,
    create_deletion_email,
    send_email,
    read_broker_data
)

# Load environment variables
load_dotenv()

def send_deletion_requests(first_name: str, last_name: str, user_email: str, test_email: str = None):
    """Send data deletion requests to all data brokers with email addresses."""
    # Get Gmail service
    service = get_gmail_service()

    # Ensure the label exists
    label_id = ensure_label_exists(service, 'Data Deletion Requests')

    # Get broker data
    brokers = read_broker_data()

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

            # Send email and apply label
            send_email(service, msg, label_id)

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

    send_deletion_requests(args.first_name, args.last_name, args.email, args.test_email if args.dev else None)

if __name__ == '__main__':
    main()
