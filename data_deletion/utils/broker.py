"""Data broker utility functions for data deletion automation."""
from typing import Dict, List, Optional
from pathlib import Path
import csv

# Broker-specific constants
ACXIOM_DELETE_FORM_URL = "https://privacyportal.onetrust.com/webform/342ca6ac-4177-4827-b61e-19070296cbd3/7229a09c-578f-4ac6-a987-e0428a7b877e"
ACXIOM_OPTOUT_URL = "https://www.acxiom.com/optout/"

def get_broker_url(broker_name: str) -> Optional[str]:
    """Get the form URL for a specific broker.
    
    Args:
        broker_name: Name of the data broker

    Returns:
        URL for the broker's form, or None if not found
    """
    script_dir = Path(__file__).parent.parent
    csv_path = script_dir / 'broker_lists' / 'current.csv'

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] == broker_name:
                return row['website']
    return None

def read_broker_data() -> List[Dict[str, str]]:
    """Read data broker information from CSV file.

    Returns:
        List of dictionaries containing broker information
    """
    script_dir = Path(__file__).parent.parent
    csv_path = script_dir / 'broker_lists' / 'current.csv'

    brokers = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['email'] != 'no email':
                brokers.append(row)
    return brokers

def get_broker_email_domains(broker_name: str) -> List[str]:
    """Get the email domains associated with a broker.

    Args:
        broker_name: Name of the data broker

    Returns:
        List of email domains to monitor for confirmations
    """
    # Map of broker names to their email domains
    broker_domains = {
        'Acxiom': ['acxiom.com', 'onetrust.com'],
        # Add more brokers as needed
    }
    return broker_domains.get(broker_name, [])
