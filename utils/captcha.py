"""CAPTCHA solving utilities for data deletion automation."""
import os
from typing import Optional
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless

# Reference: https://github.com/anti-captcha/anticaptcha-python/tree/master/anticaptchaofficial
# How to get the website key: https://anti-captcha.com/apidoc/articles/how-to-find-the-sitekey


def get_api_key() -> str:
    key = os.getenv("ANTICAPTCHA_API_KEY")
    if not key:
        raise ValueError("Please set ANTICAPTCHA_API_KEY environment variable")
    return key


def solve_captcha(website_url: str = None,
                  website_key: str = None) -> Optional[str]:
    """Solve reCAPTCHA v2 using anti-captcha service.
    
    Args:
        website_url: URL of the website with CAPTCHA
        website_key: reCAPTCHA site key
        
    Returns:
        CAPTCHA response token or None if failed
    """
    if not website_url or not website_key:
        raise ValueError("Both website_url and website_key are required")

    print("Setting up CAPTCHA solver...")

    try:
        solver = recaptchaV2Proxyless()
        solver.set_verbose(1)
        solver.set_key(get_api_key())
        solver.set_website_url(website_url)
        solver.set_website_key(website_key)
        # Optional: set custom parameter for Google Search results protection
        # solver.set_data_s('"data-s" token from Google Search results "protection"')

        print(f"Starting CAPTCHA solving for: {website_url}")

        g_response = solver.solve_and_return_solution()

        if g_response != 0:
            print(f"✓ CAPTCHA solved successfully (length: {len(g_response)})")
        else:
            print(f"❌ CAPTCHA solving failed: {solver.error_code}")

        return g_response

    except Exception as e:
        print(f"❌ CAPTCHA solving exception: {str(e)}")
        return None
