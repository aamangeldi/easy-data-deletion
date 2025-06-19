"""Constrained AI utilities for broker form automation with guardrails."""
import json
import os
from datetime import datetime
from typing import Dict, Optional
from langchain_openai import ChatOpenAI


class ConstrainedFormMapper:
    """AI form mapper with strict constraints and validation."""

    def __init__(self, model: str = "gpt-3.5-turbo", temperature: float = 0):
        """Initialize with minimal temperature for deterministic behavior."""
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY required for AI fallback")

        self.llm = ChatOpenAI(temperature=temperature, model=model)
        self.max_attempts = 3

    def map_form_fields(self, form_analysis: Dict, user_data: Dict,
                        broker_name: str) -> Dict:
        """Map form fields to user data with strict validation.
        
        Args:
            form_analysis: Form structure from analyze_form()
            user_data: Available user data
            broker_name: Name of the broker for context
            
        Returns:
            Validated field mapping dictionary
            
        Raises:
            ValueError: If mapping fails validation after max attempts
        """
        print(f"🤖 AI Fallback: Analyzing {broker_name} form (no config found)")

        # Sanitize user data for prompt (remove actual values)
        sanitized_data = {k: f"<{k.upper()}>" for k in user_data.keys()}

        prompt = self._create_mapping_prompt(form_analysis, sanitized_data,
                                             broker_name)

        for attempt in range(self.max_attempts):
            try:
                print(f"   Attempt {attempt + 1}/{self.max_attempts}")

                response = self.llm.invoke(prompt)
                mapping = self._parse_and_validate_mapping(
                    response.content, form_analysis, user_data)

                if mapping:
                    print(f"   ✓ Successfully mapped {len(mapping)} fields")
                    return mapping

            except Exception as e:
                print(f"   ⚠ Attempt {attempt + 1} failed: {str(e)}")

        raise ValueError(
            f"Failed to generate valid field mapping for {broker_name} after {self.max_attempts} attempts"
        )

    def _create_mapping_prompt(self, form_analysis: Dict, sanitized_data: Dict,
                               broker_name: str) -> str:
        """Create a constrained prompt for field mapping."""
        return f"""You are a form analysis expert. Map form fields to user data fields for {broker_name}.

STRICT RULES:
1. Only return valid JSON - no explanations, no markdown
2. Only map fields that clearly correspond to user data
3. Use exact field IDs from the form analysis
4. Map to user data keys that exist
5. Include field type (text/select/autocomplete)

Form Fields Available:
{json.dumps(form_analysis.get('fields', []), indent=2)}

User Data Available:
{json.dumps(list(sanitized_data.keys()), indent=2)}

Return ONLY this JSON format:
{{
  "field_id_1": {{"user_data_key": "first_name", "field_type": "text"}},
  "field_id_2": {{"user_data_key": "state", "field_type": "autocomplete"}}
}}

Requirements:
- Map first_name, last_name, email if fields exist
- Map address fields if available
- Identify state field as autocomplete type if it's a dropdown/combobox
- Only include confident mappings
- Return empty object {{}} if no clear mappings found"""

    def _parse_and_validate_mapping(self, response: str, form_analysis: Dict,
                                    user_data: Dict) -> Optional[Dict]:
        """Parse and validate the AI response."""
        try:
            # Extract JSON from response
            response = response.strip()
            if response.startswith('```'):
                # Remove markdown code blocks
                lines = response.split('\n')
                json_lines = []
                in_json = False
                for line in lines:
                    if line.startswith('```'):
                        in_json = not in_json
                        continue
                    if in_json:
                        json_lines.append(line)
                response = '\n'.join(json_lines)

            mapping_raw = json.loads(response)

            # Validate the mapping
            return self._validate_mapping(mapping_raw, form_analysis,
                                          user_data)

        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON response: {e}")
            return None
        except Exception as e:
            print(f"   ❌ Validation error: {e}")
            return None

    def _validate_mapping(self, mapping: Dict, form_analysis: Dict,
                          user_data: Dict) -> Optional[Dict]:
        """Validate that the mapping is safe and correct."""
        if not isinstance(mapping, dict):
            return None

        form_fields = {
            field.get('id', ''): field
            for field in form_analysis.get('fields', [])
        }
        validated_mapping = {}

        for field_id, field_mapping in mapping.items():
            # Validate structure
            if not isinstance(field_mapping, dict):
                continue
            if 'user_data_key' not in field_mapping:
                continue

            user_key = field_mapping['user_data_key']
            field_type = field_mapping.get('field_type', 'text')

            # Validate field exists in form
            if field_id not in form_fields:
                print(f"   ⚠ Field '{field_id}' not found in form")
                continue

            # Validate user data key exists
            if user_key not in user_data:
                print(f"   ⚠ User data key '{user_key}' not available")
                continue

            # Validate field type
            if field_type not in [
                    'text', 'select', 'autocomplete', 'textarea'
            ]:
                print(f"   ⚠ Invalid field type '{field_type}'")
                continue

            # Add to validated mapping with actual user data value
            validated_mapping[field_id] = {
                'value': user_data[user_key],
                'type': field_type,
                'user_key': user_key
            }

        return validated_mapping if validated_mapping else None


def generate_broker_config(broker_name: str, form_analysis: Dict,
                           field_mapping: Dict, form_url: str,
                           user_data: Dict) -> Dict:
    """Generate a broker config from successful AI analysis.
    
    Args:
        broker_name: Name of the broker
        form_analysis: Form structure analysis
        field_mapping: Validated field mapping
        form_url: URL of the form
        user_data: User data used
        
    Returns:
        Generated broker configuration
    """
    # Extract field mappings for config
    config_field_mappings = {}
    for field_id, mapping in field_mapping.items():
        config_field_mappings[field_id] = mapping['user_key']

    # Determine state format (code vs full name)
    state_format = "full"  # Default to full names
    if 'state' in user_data:
        # If state value is 2 characters, probably expects codes
        if len(str(user_data['state'])) == 2:
            state_format = "code"

    config = {
        "name": broker_name,
        "type": "web_form",
        "url": form_url,
        "email_domains": [f"{broker_name.lower()}.com"],  # Default guess
        "form_config": {
            "state_format": state_format,
            "field_mappings": config_field_mappings,
            "submission": {
                "method": "browser_submit",  # Default to browser submission
                "requires_captcha": False,  # Conservative default
                "requires_jwt": False  # Conservative default
            }
        },
        "_generated": {
            "timestamp": datetime.now().isoformat(),
            "ai_generated": True,
            "form_analysis": form_analysis,
            "note": "Auto-generated config - review and adjust as needed"
        }
    }

    return config


def save_discovered_config(broker_name: str, config: Dict) -> str:
    """Save auto-generated config for future use.
    
    Args:
        broker_name: Name of the broker
        config: Generated configuration
        
    Returns:
        Path where config was saved
    """
    from pathlib import Path

    # Save to broker_configs directory
    config_dir = Path(__file__).parent.parent / 'broker_configs'
    config_dir.mkdir(exist_ok=True)

    config_path = config_dir / f'{broker_name.lower()}.json'

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"💾 Generated config saved: {config_path}")
    print(f"   Review and adjust the config as needed for {broker_name}")

    return str(config_path)
