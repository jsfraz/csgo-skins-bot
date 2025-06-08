import time
import logging
from selenium import webdriver
from selenium.webdriver import ChromeOptions

def getDriver():
    # Inicializace WebDriver
    logging.info("Inicializuju web driver")
    # https://github.com/infologistix/docker-selenium-python/blob/main/examples/main.py
    options = ChromeOptions()
    options.add_argument("--window-size=1280,720")
    # options.add_argument("--headless")
    return webdriver.Chrome(options=options)

def loginSkins():
    logging.info("Přihlašuji se na https://csgo-skins.com/")
    driver = getDriver()
    driver.get("https://skins.com/login")

    logging.info("Přihlášení dokončeno")
    driver.quit()

if __name__ == "__main__":
    logging.info("Starting")
    logging.basicConfig(
    level=logging.INFO,  # Nastavení úrovně logování
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formát zprávy
    datefmt='%Y-%m-%d %H:%M:%S'  # Formát času
    )

    loginSkins()
    time.sleep(10)