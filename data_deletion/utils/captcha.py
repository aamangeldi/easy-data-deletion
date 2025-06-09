import os
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
# recaptchaV2Proxyless

from dotenv import load_dotenv

load_dotenv()
# How to get the website key: https://anti-captcha.com/apidoc/articles/how-to-find-the-sitekey

# /recaptcha/api2/reload?k=6LfiqCUUAAAAAGzo0BG2sKBIF-oZVi1_rXgUm5xn
ACXIOM_WEBSITE_KEY = "6LfiqCUUAAAAAGzo0BG2sKBIF-oZVi1_rXgUm5xn"
ACXIOM_WEBSITE_KEY = "6LfiqCUUAAAAAGzo0BG2sKBIF-oZVi1_rXgUm5xn"


def get_api_key():
    key = os.getenv("ANTICAPTCHA_API_KEY")
    if not key:
        raise ValueError("Please set ANTICAPTCHA_API_KEY environment variable")
    return key


def get_solver(website_url: str, website_key: str = ACXIOM_WEBSITE_KEY):
    solver = recaptchaV2Proxyless()
    solver.set_verbose(1)
    solver.set_key(get_api_key())
    solver.set_website_url(website_url)
    solver.set_website_key(website_key)
    return solver


def solve_captcha(solver: recaptchaV2Proxyless):
    #set optional custom parameter which Google made for their search page Recaptcha v2
    #solver.set_data_s('"data-s" token from Google Search results "protection"')

    g_response = solver.solve_and_return_solution()
    if g_response != 0:
        print("g-response: " + g_response)
    else:
        print("task finished with error " + solver.error_code)
    return g_response
