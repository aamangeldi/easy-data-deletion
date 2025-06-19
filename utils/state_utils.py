"""State validation and formatting utilities."""
from typing import Dict

# State code to full name mapping
STATE_MAPPING: Dict[str, str] = {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming',
    'DC': 'District of Columbia'
}

# Reverse mapping for full name to code
NAME_TO_CODE: Dict[str, str] = {v: k for k, v in STATE_MAPPING.items()}


def validate_state_input(state: str) -> str:
    """Validate state input and return standardized form.
    
    Args:
        state: State as 2-letter code or full name
        
    Returns:
        Standardized state (2-letter code)
        
    Raises:
        ValueError: If state is invalid
    """
    state = state.strip()

    # Try as uppercase code first
    state_upper = state.upper()
    if state_upper in STATE_MAPPING:
        return state_upper

    # Try as full name (case-insensitive)
    state_title = state.title()
    if state_title in NAME_TO_CODE:
        return NAME_TO_CODE[state_title]

    # Handle common variations
    state_variations = {
        'District Of Columbia': 'DC',
        'Washington DC': 'DC',
        'Washington D.C.': 'DC',
        'D.C.': 'DC'
    }

    if state_title in state_variations:
        return state_variations[state_title]

    # If nothing matches, provide helpful error
    valid_codes = ', '.join(sorted(STATE_MAPPING.keys()))
    valid_names = ', '.join(sorted(STATE_MAPPING.values()))
    raise ValueError(f"Invalid state '{state}'. Must be either:\n"
                     f"- 2-letter code: {valid_codes}\n"
                     f"- Full name: {valid_names}")


def get_state_format(state_code: str, format_type: str) -> str:
    """Get state in the specified format.
    
    Args:
        state_code: 2-letter state code (validated)
        format_type: 'code' for 2-letter code, 'full' for full name
        
    Returns:
        State in requested format
        
    Raises:
        ValueError: If format_type is invalid
    """
    if format_type == 'code':
        return state_code
    elif format_type == 'full':
        return STATE_MAPPING[state_code]
    else:
        raise ValueError(
            f"Invalid format_type '{format_type}'. Must be 'code' or 'full'")


class StateHandler:
    """Handles state formatting for different broker requirements."""

    def __init__(self, state_format: str = 'full'):
        """Initialize state handler.
        
        Args:
            state_format: 'code' for 2-letter codes, 'full' for full names
        """
        if state_format not in ['code', 'full']:
            raise ValueError("state_format must be 'code' or 'full'")
        self.format = state_format

    def format_state(self, state_input: str) -> str:
        """Format state according to broker requirements.
        
        Args:
            state_input: State as code or full name
            
        Returns:
            State formatted for the broker
        """
        # First validate and get standardized code
        state_code = validate_state_input(state_input)

        # Return in requested format
        return get_state_format(state_code, self.format)
