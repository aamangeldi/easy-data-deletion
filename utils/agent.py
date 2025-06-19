"""LangChain agent utility functions for data deletion automation."""
import json
import requests
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from playwright.sync_api import Page


class FormManager:
    """Manages form state and operations for the agent."""

    def __init__(self, page: Page, user_data: Dict[str, str], llm: ChatOpenAI):
        """Initialize the form manager.

        Args:
            page: Playwright page instance
            user_data: Dictionary containing user information
            llm: LLM instance to use for field mapping
        """
        self.page = page
        self.user_data = user_data
        self.llm = llm
        self._form_analysis: Optional[Dict] = None

    @property
    def form_analysis(self) -> Dict:
        """Get the current form analysis, performing it if necessary."""
        if self._form_analysis is None:
            from .browser import analyze_form
            self._form_analysis = analyze_form(self.page)
        return self._form_analysis

    def get_field_mapping(self) -> Dict[str, str]:
        """Use LLM to map form fields to user data without exposing actual values."""
        # Create a sanitized version of user data that only includes keys
        sanitized_user_data = {
            key: "[REDACTED]"
            for key in self.user_data.keys()
        }

        # Add field type information to help the LLM understand how to fill each field
        form_info = {
            'fields': [
                {
                    **field,
                    # Explicitly mark state field as autocomplete
                    'field_type':
                    'autocomplete' if
                    (field.get('id', '').lower()
                     in ['state', 'state-input', 'statedsarelement']
                     or field.get('label', '').lower() == 'state') else 'text'
                } for field in self.form_analysis['fields']
            ]
        }

        prompt = f"""Given a form structure and available user data fields, map the form fields to the appropriate user data keys.
        Return ONLY a JSON object mapping field IDs to user data keys and field types.

        Form Structure:
        {json.dumps(form_info, indent=2)}

        Available User Data Fields:
        {json.dumps(list(sanitized_user_data.keys()), indent=2)}

        Rules:
        1. Only map fields that clearly correspond to user data fields
        2. Use field IDs as keys and user data field names as values
        3. Return a JSON object like {{"fieldId1": {{"key": "first_name", "type": "text"}}, "fieldId2": {{"key": "state", "type": "autocomplete"}}}}
        4. If no clear mapping can be made, return an empty object {{}}
        5. Do not include any actual user data values
        6. Pay special attention to field types:
           - The state field should ALWAYS be marked as 'autocomplete' type
           - Fields with role="listbox" should be marked as 'option' type
           - Fields with role="combobox" should be marked as 'autocomplete' type
           - Other fields should be marked as 'text' type
        7. For the state field, ensure it's mapped to the 'state' key in user data
        """

        response = self.llm.invoke(prompt)
        try:
            # Get the mapping of field IDs to user data keys and types
            field_mapping = json.loads(response.content)

            # Convert the mapping to use actual user data values
            result = {}
            for field_id, mapping in field_mapping.items():
                if isinstance(mapping, dict) and 'key' in mapping:
                    key = mapping['key']
                    if key in self.user_data:
                        result[field_id] = {
                            'value': self.user_data[key],
                            'type': mapping.get('type', 'text')
                        }

            return result
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error parsing field mapping: {e}")
            print(f"LLM response: {response.content}")
            return {}

    def get_page_content(self) -> str:
        """Get the current page content and form structure."""
        return json.dumps(self.form_analysis)

    def fill_user_data(self) -> str:
        """Fill in the user's data using the provided information."""
        try:
            from .browser import fill_form_field

            # Use LLM to map fields
            field_mapping = self.get_field_mapping()

            if not field_mapping:
                raise ValueError(
                    "Could not determine field mappings for user data")

            # Fill each field and track what was filled
            filled_fields = {}
            for field_id, field_info in field_mapping.items():
                fill_form_field(self.page,
                                field_id,
                                field_info['value'],
                                field_type=field_info.get('type', 'text'))
                filled_fields[field_id] = field_info

            return json.dumps({
                "status": "success",
                "filled_fields": filled_fields,
                "field_mapping": field_mapping
            })
        except Exception as e:
            raise ValueError(f"Error filling user data: {str(e)}")

    def solve_captcha(self) -> str:
        """Solve the CAPTCHA on the current page."""
        try:
            from .captcha import solve_captcha

            print("Solving CAPTCHA...")
            captcha_response = solve_captcha()

            if captcha_response:
                return json.dumps({
                    "status": "success",
                    "captcha_response": captcha_response,
                    "message": "CAPTCHA solved successfully"
                })
            else:
                raise ValueError("CAPTCHA solving failed")

        except Exception as e:
            raise ValueError(f"Error solving CAPTCHA: {str(e)}")

    def monitor_network_for_jwt(self) -> str:
        """Monitor network requests to capture JWT tokens from API responses."""
        try:
            # Set up network request monitoring
            jwt_tokens = self.page.evaluate('''() => {
                // Store any JWT tokens found in network responses
                window.capturedJwtTokens = [];
                
                // Override fetch to capture JWT tokens
                const originalFetch = window.fetch;
                window.fetch = function(...args) {
                    return originalFetch.apply(this, args).then(response => {
                        // Check response headers for JWT tokens
                        const authHeader = response.headers.get('Authorization');
                        if (authHeader && authHeader.startsWith('Bearer ')) {
                            const token = authHeader.substring(7);
                            if (token.startsWith('eyJ') && token.split('.').length === 3) {
                                window.capturedJwtTokens.push({
                                    source: 'response_header',
                                    token: token
                                });
                            }
                        }
                        
                        // Clone response to read body
                        const clonedResponse = response.clone();
                        clonedResponse.text().then(text => {
                            try {
                                const data = JSON.parse(text);
                                // Look for JWT tokens in response body
                                const findJwtInObject = (obj, path = '') => {
                                    for (const [key, value] of Object.entries(obj)) {
                                        const currentPath = path ? `${path}.${key}` : key;
                                        if (typeof value === 'string' && value.startsWith('eyJ') && value.split('.').length === 3) {
                                            window.capturedJwtTokens.push({
                                                source: `response_body.${currentPath}`,
                                                token: value
                                            });
                                        } else if (typeof value === 'object' && value !== null) {
                                            findJwtInObject(value, currentPath);
                                        }
                                    }
                                };
                                findJwtInObject(data);
                            } catch (e) {
                                // Not JSON, check if it contains JWT patterns
                                const jwtMatches = text.match(/eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/g);
                                if (jwtMatches) {
                                    jwtMatches.forEach(token => {
                                        window.capturedJwtTokens.push({
                                            source: 'response_text',
                                            token: token
                                        });
                                    });
                                }
                            }
                        });
                        
                        return response;
                    });
                };
                
                // Override XMLHttpRequest to capture JWT tokens
                const originalXHROpen = XMLHttpRequest.prototype.open;
                const originalXHRSend = XMLHttpRequest.prototype.send;
                
                XMLHttpRequest.prototype.open = function(...args) {
                    this._url = args[1];
                    return originalXHROpen.apply(this, args);
                };
                
                XMLHttpRequest.prototype.send = function(...args) {
                    const xhr = this;
                    const originalOnReadyStateChange = xhr.onreadystatechange;
                    
                    xhr.onreadystatechange = function() {
                        if (xhr.readyState === 4) {
                            // Check response headers
                            const authHeader = xhr.getResponseHeader('Authorization');
                            if (authHeader && authHeader.startsWith('Bearer ')) {
                                const token = authHeader.substring(7);
                                if (token.startsWith('eyJ') && token.split('.').length === 3) {
                                    window.capturedJwtTokens.push({
                                        source: `xhr_header_${xhr._url}`,
                                        token: token
                                    });
                                }
                            }
                            
                            // Check response body
                            try {
                                const data = JSON.parse(xhr.responseText);
                                const findJwtInObject = (obj, path = '') => {
                                    for (const [key, value] of Object.entries(obj)) {
                                        const currentPath = path ? `${path}.${key}` : key;
                                        if (typeof value === 'string' && value.startsWith('eyJ') && value.split('.').length === 3) {
                                            window.capturedJwtTokens.push({
                                                source: `xhr_body_${xhr._url}.${currentPath}`,
                                                token: value
                                            });
                                        } else if (typeof value === 'object' && value !== null) {
                                            findJwtInObject(value, currentPath);
                                        }
                                    }
                                };
                                findJwtInObject(data);
                            } catch (e) {
                                // Not JSON, check for JWT patterns
                                const jwtMatches = xhr.responseText.match(/eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/g);
                                if (jwtMatches) {
                                    jwtMatches.forEach(token => {
                                        window.capturedJwtTokens.push({
                                            source: `xhr_text_${xhr._url}`,
                                            token: token
                                        });
                                    });
                                }
                            }
                        }
                        
                        if (originalOnReadyStateChange) {
                            originalOnReadyStateChange.apply(this, arguments);
                        }
                    };
                    
                    return originalXHRSend.apply(this, args);
                };
                
                return "Network monitoring set up";
            }''')

            print("Network monitoring set up to capture JWT tokens")
            return jwt_tokens

        except Exception as e:
            print(f"Error setting up network monitoring: {e}")
            return "Failed to set up network monitoring"

    def get_captured_jwt_tokens(self) -> list:
        """Get any JWT tokens captured during network monitoring."""
        try:
            captured_tokens = self.page.evaluate('''() => {
                return window.capturedJwtTokens || [];
            }''')

            if captured_tokens:
                print(
                    f"Found {len(captured_tokens)} JWT tokens from network monitoring:"
                )
                for token_info in captured_tokens:
                    print(f"  - Source: {token_info['source']}")
                    print(f"    Token preview: {token_info['token'][:50]}...")

            return captured_tokens

        except Exception as e:
            print(f"Error getting captured JWT tokens: {e}")
            return []

    def submit_form_with_captcha(self, captcha_response: str) -> str:
        """Submit the form via POST request with CAPTCHA response."""
        try:
            # Get current page URL to determine the submission endpoint
            current_url = self.page.url

            # For Acxiom form, the submission endpoint is known
            if "privacyportal.onetrust.com" in current_url:
                submission_url = "https://privacyportal.onetrust.com/request/v1/dsarrequestqueue"
            else:
                # Try to extract submission URL from form action
                form_action = self.page.evaluate('''() => {
                    const form = document.querySelector('form');
                    return form ? form.action : null;
                }''')
                submission_url = form_action or current_url

            # Comprehensive JWT token extraction
            print("Extracting JWT token and authentication data...")
            auth_data = self.page.evaluate('''() => {
                const auth = {};
                
                // 1. Look for JWT tokens in hidden inputs
                const hiddenInputs = document.querySelectorAll('input[type="hidden"]');
                hiddenInputs.forEach(input => {
                    if (input.name && input.value) {
                        auth[input.name] = input.value;
                        // Check if it looks like a JWT token
                        if (input.value.startsWith('eyJ') && input.value.split('.').length === 3) {
                            auth.jwtToken = input.value;
                        }
                    }
                });
                
                // 2. Look for JWT tokens in meta tags
                const metaTags = document.querySelectorAll('meta');
                metaTags.forEach(meta => {
                    const name = meta.getAttribute('name') || meta.getAttribute('property');
                    const content = meta.getAttribute('content');
                    if (name && content) {
                        auth[`meta_${name}`] = content;
                        if (content.startsWith('eyJ') && content.split('.').length === 3) {
                            auth.jwtToken = content;
                        }
                    }
                });
                
                // 3. Check localStorage for JWT tokens
                try {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        const value = localStorage.getItem(key);
                        if (value && value.startsWith('eyJ') && value.split('.').length === 3) {
                            auth.jwtToken = value;
                            auth.jwtTokenSource = `localStorage.${key}`;
                        }
                        auth[`localStorage_${key}`] = value;
                    }
                } catch (e) {
                    console.log('localStorage access error:', e);
                }
                
                // 4. Check sessionStorage for JWT tokens
                try {
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        const value = sessionStorage.getItem(key);
                        if (value && value.startsWith('eyJ') && value.split('.').length === 3) {
                            auth.jwtToken = value;
                            auth.jwtTokenSource = `sessionStorage.${key}`;
                        }
                        auth[`sessionStorage_${key}`] = value;
                    }
                } catch (e) {
                    console.log('sessionStorage access error:', e);
                }
                
                // 5. Look for JWT tokens in script tags
                const scripts = document.querySelectorAll('script');
                scripts.forEach(script => {
                    const content = script.textContent || script.innerHTML;
                    if (content) {
                        // Look for JWT patterns in script content
                        const jwtMatches = content.match(/eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+/g);
                        if (jwtMatches) {
                            auth.jwtToken = jwtMatches[0];
                            auth.jwtTokenSource = 'script_content';
                        }
                    }
                });
                
                // 6. Check for any global variables that might contain JWT
                try {
                    if (window.jwtToken) {
                        auth.jwtToken = window.jwtToken;
                        auth.jwtTokenSource = 'window.jwtToken';
                    }
                    if (window.token) {
                        auth.jwtToken = window.token;
                        auth.jwtTokenSource = 'window.token';
                    }
                    if (window.authToken) {
                        auth.jwtToken = window.authToken;
                        auth.jwtTokenSource = 'window.authToken';
                    }
                } catch (e) {
                    console.log('window access error:', e);
                }
                
                // 7. Get all cookies
                auth.cookies = document.cookie;
                
                // 8. Look for CSRF tokens
                const csrfInput = document.querySelector('input[name="csrf"], input[name="_csrf"], meta[name="csrf-token"]');
                if (csrfInput) {
                    auth.csrfToken = csrfInput.value || csrfInput.getAttribute('content');
                }
                
                // 9. Get form data
                const form = document.querySelector('form');
                if (form) {
                    const formData = new FormData(form);
                    for (let [key, value] of formData.entries()) {
                        auth[`form_${key}`] = value;
                    }
                }
                
                return auth;
            }''')

            print(f"Found authentication data keys: {list(auth_data.keys())}")
            if auth_data.get('jwtToken'):
                print(
                    f"JWT token found from: {auth_data.get('jwtTokenSource', 'unknown')}"
                )
                print(f"JWT token preview: {auth_data['jwtToken'][:50]}...")
            else:
                print("No JWT token found in page data")

            # Get form data from the page
            form_data = self.page.evaluate('''() => {
                const form = document.querySelector('form');
                if (!form) return {};
                
                const formData = new FormData(form);
                const data = {};
                for (let [key, value] of formData.entries()) {
                    data[key] = value;
                }
                return data;
            }''')

            # Prepare the submission payload based on the Acxiom form structure
            payload = {
                "firstName": self.user_data.get('first_name', ''),
                "lastName": self.user_data.get('last_name', ''),
                "email": self.user_data.get('email', ''),
                "requestTypes": ["RequestType2"],  # Delete request
                "subjectTypes": ["SubjectType1"],  # As Myself
                "additionalData": {
                    "country": "US",
                    "formField29": "",
                    "formField38": "",
                    "address": self.user_data.get('address', ''),
                    "city": self.user_data.get('city', ''),
                    "state": self.user_data.get('state', ''),
                    "zip": self.user_data.get('zip_code', ''),
                    "formField31": "",
                    "formField60": "",
                    "formField33": "",
                    "formField34": "",
                    "formField48": "",
                    "formField50": "",
                    "formField49": "",
                    "formField51": "",
                    "formField62": "",
                    "formField63": "",
                    "formField65": "",
                    "address2": "",
                    "formField84": "",
                    "formField85": "",
                    "formField68": "",
                    "formField73": "",
                    "formField36": "",
                    "formField70": "",
                    "formField30": "",
                    "formField39": "",
                    "formField71": "",
                    "formField87": "",
                    "formField43": "",
                    "formField40": "",
                    "formField41": "",
                    "formField42": "",
                    "formField66": "",
                    "formField52": "",
                    "formField44": "",
                    "formField46": "",
                    "formField45": "",
                    "formField72": "",
                    "formField53": "",
                    "formField54": "",
                    "formField59": "",
                    "formField58": "",
                    "acknowledgement": "",
                    "formField55": "",
                    "formField56": "",
                    "formField57": "",
                    "formField86": "",
                    "dateOfBirth": self.user_data.get('date_of_birth', ''),
                    "requestDetails": "No additional request details provided."
                },
                "multiselectFields": {},
                "daysToRespond": "",
                "language": "en-us",
                "botDetectCaptcha": False,
                "googleRecaptcha": True,
                "captchaId": "",
                "captchaCode": "",
                "dataLocalizationEnabled": False,
                "recaptchaResponse": captcha_response,
                "webformConfig": {
                    "requestTypes": [{
                        "id": "f7aec3a6-1e9d-454c-8143-22149a72445d",
                        "order": 1,
                        "fieldValue": None,
                        "status": 10,
                        "canDelete": True,
                        "description": "RequestType1Desc",
                        "descriptionValue": None,
                        "fieldName": "RequestType1",
                        "isSelected": True,
                        "isUsed": False,
                        "isDefault": False
                    }, {
                        "id": "c257f9fe-77f1-4f7e-a2bf-20395ddaff70",
                        "order": 2,
                        "fieldValue": None,
                        "status": 10,
                        "canDelete": True,
                        "description": "RequestType2Desc",
                        "descriptionValue": None,
                        "fieldName": "RequestType2",
                        "isSelected": True,
                        "isUsed": False,
                        "isDefault": False
                    }],
                    "subjectTypes": [{
                        "id": "41b56bd7-72e9-435b-8d98-2ce0d5e2b671",
                        "order": 1,
                        "fieldValue": None,
                        "status": 10,
                        "canDelete": True,
                        "description": "SubjectType1Desc",
                        "descriptionValue": None,
                        "fieldName": "SubjectType1",
                        "isSelected": True,
                        "isUsed": False,
                        "isDefault": False
                    }]
                }
            }

            # Set up headers for the POST request
            headers = {
                'accept':
                'application/json',
                'accept-language':
                'en-US,en;q=0.9',
                'content-type':
                'application/json',
                'dnt':
                '1',
                'origin':
                'https://privacyportal.onetrust.com',
                'priority':
                'u=1, i',
                'referer':
                current_url,
                'sec-ch-ua':
                '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile':
                '?0',
                'sec-ch-ua-platform':
                '"macOS"',
                'sec-fetch-dest':
                'empty',
                'sec-fetch-mode':
                'cors',
                'sec-fetch-site':
                'same-origin',
                'user-agent':
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }

            # Add JWT token if found
            if auth_data.get('jwtToken'):
                headers['Authorization'] = f'Bearer {auth_data["jwtToken"]}'
                payload['jwtToken'] = auth_data['jwtToken']
                print("Added JWT token to request")

            # Add CSRF token if found
            if auth_data.get('csrfToken'):
                headers['X-CSRF-Token'] = auth_data['csrfToken']
                print("Added CSRF token to request")

            # Add cookies if found
            if auth_data.get('cookies'):
                headers['Cookie'] = auth_data['cookies']
                print("Added cookies to request")

            # Add any other authentication tokens found
            for key, value in auth_data.items():
                if key.startswith('meta_') and value:
                    headers[f'X-{key[5:]}'] = value
                elif key.startswith('form_') and value:
                    payload[key[5:]] = value

            print(
                f"Submitting form with {len(headers)} headers and {len(payload)} payload fields"
            )

            # Make the POST request
            response = requests.post(submission_url,
                                     json=payload,
                                     headers=headers)

            if response.status_code in [200, 201]:
                return json.dumps({
                    "status":
                    "success",
                    "response":
                    response.json(),
                    "message":
                    f"Form submitted successfully with status {response.status_code}"
                })
            else:
                return json.dumps({
                    "status":
                    "error",
                    "status_code":
                    response.status_code,
                    "response":
                    response.text,
                    "message":
                    f"Form submission failed with status {response.status_code}"
                })

        except Exception as e:
            raise ValueError(f"Error submitting form: {str(e)}")


def create_browser_tools(page: Page,
                         user_data: Dict[str, str],
                         llm: ChatOpenAI,
                         gmail_service: Dict = None) -> List[StructuredTool]:
    """Create browser interaction tools for the agent.

    Args:
        page: Playwright page instance
        user_data: Dictionary containing user information
        llm: LLM instance to use for field mapping
        gmail_service: Optional Gmail service for email functionality

    Returns:
        List of StructuredTool instances for the agent
    """
    from .gmail import create_deletion_email, send_email, ensure_label_exists, check_confirmation_email
    from .broker import get_broker_email_domains

    # Create form manager instance
    form_manager = FormManager(page, user_data, llm)

    def send_deletion_email(broker_name: str) -> str:
        """Send a data deletion request email to a broker."""
        if not gmail_service:
            raise ValueError("Gmail service not configured")

        try:
            ensure_label_exists(gmail_service, "Data Deletion Requests")
            message = create_deletion_email(gmail_service, broker_name,
                                            user_data['first_name'],
                                            user_data['last_name'],
                                            user_data['email'])
            send_email(gmail_service, message)

            return json.dumps({
                "status": "success",
                "message": f"Deletion request email sent to {broker_name}",
                "message_id": message['id']
            })
        except Exception as e:
            raise ValueError(f"Error sending deletion email: {str(e)}")

    def check_email_confirmation(broker_name: str,
                                 wait_time: int = 300) -> str:
        """Check for confirmation email from a broker."""
        if not gmail_service:
            raise ValueError("Gmail service not configured")

        try:
            domains = get_broker_email_domains(broker_name)
            if not domains:
                raise ValueError(
                    f"No email domains configured for {broker_name}")

            confirmed = check_confirmation_email(service=gmail_service,
                                                 user_email=user_data['email'],
                                                 from_domains=domains,
                                                 wait_time=wait_time)

            return json.dumps({
                "status":
                "success",
                "confirmed":
                confirmed,
                "message":
                "Confirmation email found"
                if confirmed else "No confirmation email received"
            })
        except Exception as e:
            raise ValueError(f"Error checking confirmation email: {str(e)}")

    tools = [
        StructuredTool.from_function(
            func=form_manager.get_page_content,
            name="get_page_content",
            description="Get the current page content and form structure."),
        StructuredTool.from_function(
            func=form_manager.fill_user_data,
            name="fill_user_data",
            description="Fill in the user's personal information in the form."
        ),
        StructuredTool.from_function(
            func=form_manager.solve_captcha,
            name="solve_captcha",
            description=
            "Solve the CAPTCHA on the current page using anti-captcha service."
        ),
        StructuredTool.from_function(
            func=form_manager.monitor_network_for_jwt,
            name="monitor_network_for_jwt",
            description=
            "Set up network monitoring to capture JWT tokens from API responses. Call this before filling the form to capture any tokens sent during form interaction."
        ),
        StructuredTool.from_function(
            func=form_manager.get_captured_jwt_tokens,
            name="get_captured_jwt_tokens",
            description=
            "Get any JWT tokens captured during network monitoring. Call this after form interaction to retrieve captured tokens."
        ),
        StructuredTool.from_function(
            func=form_manager.submit_form_with_captcha,
            name="submit_form_with_captcha",
            description=
            "Submit the form via POST request with CAPTCHA response. Requires the captcha_response from solve_captcha."
        )
    ]

    # Add email tools if Gmail service is available
    if gmail_service:
        tools.extend([
            StructuredTool.from_function(
                func=send_deletion_email,
                name="send_deletion_email",
                description="Send a data deletion request email to a broker."),
            StructuredTool.from_function(
                func=check_email_confirmation,
                name="check_email_confirmation",
                description=
                "Check for confirmation email from a broker after form submission or email request."
            )
        ])

    return tools


def create_form_agent(page: Page,
                      user_data: Dict[str, str],
                      system_prompt: str,
                      model: str = "gpt-3.5-turbo",
                      temperature: float = 0,
                      gmail_service: Dict = None) -> AgentExecutor:
    """Create a LangChain agent for form automation.

    Args:
        page: Playwright page instance
        user_data: Dictionary containing user information
        system_prompt: System prompt for the agent
        model: OpenAI model to use
        temperature: Temperature for model generation
        gmail_service: Optional Gmail service for email functionality

    Returns:
        AgentExecutor instance
    """
    llm = ChatOpenAI(temperature=temperature, model=model)
    tools = create_browser_tools(page, user_data, llm, gmail_service)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def get_default_form_prompt() -> str:
    """Get the default system prompt for form automation.

    Returns:
        Default system prompt string
    """
    return """You are an AI assistant helping to request deletion of personal information from data brokers.
    Your goal is to help the user submit data deletion requests either through web forms or email.

    IMPORTANT: The user will provide a broker_name in the input. Always use this exact broker_name when calling email-related tools like check_email_confirmation.

    CRITICAL FIRST STEP: You MUST always start by calling get_page_content to analyze what's on the current page before deciding which workflow to use.

    IMPORTANT WORKFLOW DECISION: 
    - If you are on a web form page (like Acxiom's privacy portal), use the WEB FORM workflow
    - Only use the EMAIL workflow if there is no web form available or if specifically instructed
    - For Acxiom, you should use the WEB FORM workflow since there is a working web form
    - NEVER send an email if you are on a web form page

    You have access to the following tools:
    - get_page_content: Get the current page content and form structure (ALWAYS CALL THIS FIRST)
    - fill_user_data: Fill in the user's personal information in the form
    - solve_captcha: Solve the CAPTCHA on the current page using anti-captcha service
    - monitor_network_for_jwt: Set up network monitoring to capture JWT tokens from API responses
    - get_captured_jwt_tokens: Get any JWT tokens captured during network monitoring
    - submit_form_with_captcha: Submit the form via POST request with CAPTCHA response
    - send_deletion_email: Send a data deletion request email to a broker (if available)
    - check_email_confirmation: Check for confirmation email from a broker (if available)

    REQUIRED WORKFLOW:
    1. ALWAYS start with get_page_content to analyze the current page
    2. Based on the page content, determine if you're on a web form or need to send an email
    3. If you see form fields, use the WEB FORM workflow
    4. If you don't see any form fields and are instructed to send an email, use the EMAIL workflow

    WEB FORM WORKFLOW (Use this for Acxiom and other web forms):
    1. Use monitor_network_for_jwt to set up network monitoring for JWT tokens
    2. Use fill_user_data to fill in the user's information (this may trigger API calls that generate JWT tokens)
    3. Use get_captured_jwt_tokens to check for any JWT tokens captured during form filling
    4. Use solve_captcha to solve the CAPTCHA and get the response
    5. Use submit_form_with_captcha with the CAPTCHA response to submit the form (this will automatically use any captured JWT tokens)
    6. Use check_email_confirmation with the broker_name from the input to verify the submission
    7. Wait for confirmation

    EMAIL WORKFLOW (Only use if no web form is available):
    1. Use send_deletion_email with the broker_name from the input
    2. Use check_email_confirmation with the broker_name from the input to verify the request
    3. Wait for confirmation

    After submission:
    - Track the request status
    - Note any follow-up actions needed
    - Report the result to the user

    The fill_user_data tool will automatically:
    1. Analyze the form fields
    2. Map them to the appropriate user data
    3. Fill in the values
    4. Return information about what was filled

    For JWT token handling:
    1. Always set up network monitoring before filling the form
    2. Check for captured JWT tokens after form interaction
    3. The submit_form_with_captcha tool will automatically use any captured JWT tokens
    4. If no JWT tokens are found, the tool will still attempt submission with other authentication methods

    For CAPTCHA handling:
    1. Always solve the CAPTCHA before attempting form submission
    2. Use the CAPTCHA response in the submit_form_with_captcha tool
    3. If CAPTCHA solving fails, report the error and suggest manual completion

    For email confirmation:
    1. Always check for confirmation after form submission or email request
    2. Use the broker_name from the input when calling check_email_confirmation
    3. Wait for the specified time period
    4. Report whether confirmation was received
    5. If no confirmation is received, note that manual follow-up may be needed

    BROKER NAME USAGE:
    - When the user provides a broker_name in the input, use that exact name for all email-related operations
    - For example, if broker_name is "Acxiom", use "Acxiom" when calling check_email_confirmation
    - Do not modify or change the broker_name - use it exactly as provided

    WORKFLOW SELECTION RULES:
    - ALWAYS call get_page_content first to see what's on the page
    - If you see form fields in the page content, use the WEB FORM workflow
    - If you are on a privacy portal or data deletion form page, use the WEB FORM workflow
    - Only use the EMAIL workflow if explicitly told there is no web form or if you cannot find any form fields on the page
    - For Acxiom, always use the WEB FORM workflow
    - NEVER send an email if you are on a web form page"""
