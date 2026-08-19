"""
Fabrique du driver Selenium.

- En local : Selenium 4.24+ télécharge/gère automatiquement le bon chromedriver
  (Selenium Manager). Aucune installation manuelle n'est nécessaire.
- Sur Streamlit Community Cloud : Chromium et chromium-driver sont installés
  via packages.txt (apt). On pointe alors explicitement vers ces binaires.
"""
import os
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def get_driver(headless: bool = True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,1000")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    # Cas Streamlit Cloud : chromium installé par apt (packages.txt)
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser")
    chromedriver_path = shutil.which("chromedriver")

    if chromium_path and chromedriver_path:
        options.binary_location = chromium_path
        service = Service(executable_path=chromedriver_path)
        return webdriver.Chrome(service=service, options=options)

    # Cas local : Selenium Manager gère tout automatiquement
    return webdriver.Chrome(options=options)
