"""Validation utilities for user input."""
from datetime import datetime


def validate_date_of_birth(date_str: str) -> str:
    """Validate and format date of birth.
    
    Args:
        date_str: Date string in MM/DD/YYYY format
        
    Returns:
        Formatted date string
        
    Raises:
        ValueError: If date is invalid
    """
    try:
        date_obj = datetime.strptime(date_str, '%m/%d/%Y')
        if date_obj > datetime.now():
            raise ValueError("Date of birth cannot be in the future")
        return date_obj.strftime('%m/%d/%Y')
    except ValueError as e:
        if "time data" in str(e):
            raise ValueError("Date must be in MM/DD/YYYY format")
        raise