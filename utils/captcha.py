import os
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
from .broker import ACXIOM_DELETE_FORM_URL
# recaptchaV2Proxyless

from dotenv import load_dotenv

load_dotenv()
# How to get the website key: https://anti-captcha.com/apidoc/articles/how-to-find-the-sitekey

# /recaptcha/api2/reload?k=6LfiqCUUAAAAAGzo0BG2sKBIF-oZVi1_rXgUm5xn
ACXIOM_WEBSITE_KEY = "6LfiqCUUAAAAAGzo0BG2sKBIF-oZVi1_rXgUm5xn"
# reference: https://github.com/anti-captcha/anticaptcha-python/tree/master/anticaptchaofficial


def get_api_key():
    key = os.getenv("ANTICAPTCHA_API_KEY")
    if not key:
        raise ValueError("Please set ANTICAPTCHA_API_KEY environment variable")
    return key


def solve_captcha():
    print("=== solve_captcha function called ===")
    print("Setting up CAPTCHA solver...")

    try:
        solver = recaptchaV2Proxyless()
        solver.set_verbose(1)
        solver.set_key(get_api_key())
        solver.set_website_url(ACXIOM_DELETE_FORM_URL)
        solver.set_website_key(ACXIOM_WEBSITE_KEY)
        #set optional custom parameter which Google made for their search page Recaptcha v2
        #solver.set_data_s('"data-s" token from Google Search results "protection"')

        print("Starting CAPTCHA solving process...")
        print(f"Website URL: {ACXIOM_DELETE_FORM_URL}")
        print(f"Website key: {ACXIOM_WEBSITE_KEY}")

        g_response = solver.solve_and_return_solution()

        if g_response != 0:
            print("g-response: " + g_response)
            print("=== CAPTCHA solved successfully ===")
            print(f"Response length: {len(g_response)}")
            print(f"Response preview: {g_response[:50]}...")
        else:
            print("task finished with error " + solver.error_code)
            print("=== CAPTCHA solving failed ===")
            print(f"Error code: {solver.error_code}")
            print(f"Error description: {solver.error_code}")

        return g_response

    except Exception as e:
        print(f"Exception in solve_captcha: {str(e)}")
        print("=== CAPTCHA solving failed with exception ===")
        return None
