"""Authentication token extraction utilities."""
from typing import Dict


def extract_auth_tokens(page) -> Dict:
    """Extract authentication tokens from the page.
    
    Args:
        page: Playwright page instance
        
    Returns:
        Dictionary containing found authentication tokens
    """
    return page.evaluate('''() => {
        const auth = {};
        
        // 1. Look for JWT tokens in hidden inputs
        const hiddenInputs = document.querySelectorAll('input[type="hidden"]');
        hiddenInputs.forEach(input => {
            if (input.name && input.value) {
                auth[input.name] = input.value;
                // Check if it looks like a JWT token
                if (input.value.startsWith('eyJ') && input.value.split('.').length === 3) {
                    auth.jwtToken = input.value;
                    auth.jwtTokenSource = `input.${input.name}`;
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
                    auth.jwtTokenSource = `meta.${name}`;
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
        
        // 5. Look for JWT tokens in script tags (THIS IS THE KEY PART!)
        const scripts = document.querySelectorAll('script');
        scripts.forEach(script => {
            const content = script.textContent || script.innerHTML;
            if (content) {
                // Look for JWT patterns in script content
                const jwtMatches = content.match(/eyJ[a-zA-Z0-9_-]+\\.[a-zA-Z0-9_-]+\\.[a-zA-Z0-9_-]+/g);
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