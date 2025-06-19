"""Template substitution utilities."""
from typing import Dict, Union, List, Any


def substitute_template_variables(
        template: Union[Dict, List, str,
                        Any], user_data: Dict) -> Union[Dict, List, str, Any]:
    """Recursively substitute template variables in a data structure.
    
    Args:
        template: Data structure containing template variables like {first_name}
        user_data: Dictionary containing actual user data
        
    Returns:
        Data structure with substituted values
    """
    if isinstance(template, dict):
        return {
            key: substitute_template_variables(value, user_data)
            for key, value in template.items()
        }
    elif isinstance(template, list):
        return [
            substitute_template_variables(item, user_data) for item in template
        ]
    elif isinstance(template, str):
        # Replace template variables like {first_name} with actual values
        result = template
        for key, value in user_data.items():
            result = result.replace(f'{{{key}}}', str(value))
        return result
    else:
        return template
