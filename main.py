import os
import sys
import time
import queue
import json
import pickle
import asyncio
import logging
import schedule
import threading
from io import BytesIO
from seleniumbase import SB
from telegram import Update
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from seleniumbase import Driver
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from typing import List, Optional, TypedDict
from telegram.ext import Application, CommandHandler, ContextTypes

# Nastavení okamžitého flush pro stdout a stderr
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

class CaseOpenTime(TypedDict):
    url: str
    end_time: Optional[datetime]

# Načtení .env proměnných
if os.path.exists('.env'):
    load_dotenv()
    logging.info(".env file loaded")
else:
    logging.warning(".env file not found, using system environment variables")

# Konfigurace logging s flush
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

# Nastavte flush pro handler
for handler in logging.root.handlers:
    handler.setStream(sys.stdout)
    if hasattr(handler.stream, 'reconfigure'):
        handler.stream.reconfigure(line_buffering=True)

# Pro okamžité zobrazení použijte flush
print("Starting application", flush=True)

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def send_screenshot_to_user(user_id: int, image: bytes, caption: str):
    """Odešle screenshot konkrétnímu uživateli"""
    try:
        # Použití BytesIO pro předání bytes objektu jako souboru
        photo_stream = BytesIO(image)
        photo_stream.name = 'screenshot.png'  # Nastavení jména souboru
        
        await telegram.bot.send_photo(chat_id=user_id, photo=photo_stream, caption=caption)
        logging.info(f"Screenshot sent")
    except Exception as e:
        logging.error(f"Error sending screenshot: {e}")

async def send_telegram_message(user_id: int, message: str):
    """Odešle textovou zprávu konkrétnímu uživateli"""
    try:
        await telegram.bot.send_message(chat_id=user_id, text=message)
        logging.info(f"Message sent: {message}")
    except Exception as e:
        logging.error(f"Error sending message: {e}")

# Globální proměnná pro event loop
telegram_loop = None

# Globální queue
screenshot_queue = queue.Queue()
# Globální queue pro zprávy
message_queue = queue.Queue()

async def process_screenshots():
    """Zpracování screenshotů z queue"""
    while True:
        try:
            if not screenshot_queue.empty():
                user_id, image_bytes, caption = screenshot_queue.get()
                await send_screenshot_to_user(user_id, image_bytes, caption)
                screenshot_queue.task_done()
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Error processing screenshot: {e}")

async def process_messages():
    """Zpracování zpráv z queue"""
    while True:
        try:
            if not message_queue.empty():
                user_id, message = message_queue.get()
                await send_telegram_message(user_id, message)
                message_queue.task_done()
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Error processing message: {e}")

def loginSkins():
    """Přihlášení na csgo-skins.com """
    url = "https://csgo-skins.com/"
    logging.info("Logging in to %s", url)
    
    driver = Driver(uc=True, proxy="socks5://" + os.environ.get("PROXY_HOST_IP"))
    try:
        driver.uc_open_with_reconnect(url, 10)
        driver.uc_gui_click_captcha()
        time.sleep(1)

        # Přihlášení
        driver.find_element(By.CLASS_NAME, "AppHeader_login-button").click()
        # Podmínky
        time.sleep(1)
        checkboxes = driver.find_elements(By.CLASS_NAME, "CheckboxInput_checkmark")
        for checkbox in checkboxes:
            checkbox.click()
            time.sleep(1)
        # Přihlášení přes Steam
        driver.find_element(By.CLASS_NAME, "RulesPopup_button").click()
        time.sleep(5)

        # Zasílání QR kódu do Telegramu dokud se uživatel nepřihlásí
        while driver.current_url.startswith("https://steamcommunity.com/openid/loginform/"):
            # Screenshot Steam QR kódu
            qrBytes = driver.find_element(By.CSS_SELECTOR, 'div[style*="position: relative"]').screenshot_as_png

            # Přidání do queue
            screenshot_queue.put((int(os.getenv("TELEGRAM_USER_ID")), qrBytes, "Steam sign in QR code"))
            logging.info("Screenshot of QR code added to queue")

            # Obnová QR kódu
            time.sleep(15)
            if driver.current_url.startswith("https://steamcommunity.com/openid/loginform/"):
                logging.info("Refreshing page to get new QR code")
                driver.refresh()
            time.sleep(2)

        # Přihlašovací tlačítko
        driver.find_element(By.ID, "imageLogin").click()

        # Odeslání zprávy o úspěšném přihlášení
        message_queue.put((int(os.getenv("TELEGRAM_USER_ID")), "User logged in successfully"))
        logging.info("User logged in")
        time.sleep(5)

        # Po úspěšném přihlášení uložit session
        save_cookies(driver)
        save_local_storage(driver)
        time.sleep(1)
    finally:
        driver.quit()

def openCase(url: str):
    """Otevření case"""
    logging.info(f"Opening case at {url.replace('https://csgo-skins.com/case/', '')}")

    '''
    try:
        with SB(uc=True, proxy="socks5://" + os.environ.get("PROXY_HOST_IP")) as sb:
            # Otevření URL
            sb.activate_cdp_mode(url)
            sb.uc_gui_click_captcha()
            sb.sleep(1)

            # Načtení cookies a local storage
            load_cookies(sb)
            load_local_storage(sb)
            sb.refresh()
            sb.sleep(2)

            # Kliknutí na tlačítko otevřít
            sb.find_element(By.CLASS_NAME, "button--open").click()
            sb.sleep(5)

            # Kliknutí na checkbox pro potvrzení
            # https://seleniumbase.io/examples/cdp_mode/ReadMe/#cdp-mode-usage
            sb.cdp.gui_click_element("#Recaptcha div")
            sb.sleep(5)

            # Screenshot
            screenshotBytes = sb.find_element(By.CLASS_NAME, "section_tapes").screenshot_as_png
            screenshot_queue.put((int(os.getenv("TELEGRAM_USER_ID")), screenshotBytes, f"'{url.replace('https://csgo-skins.com/case/', '')}' opened"))
            logging.info(f"Screenshot of '{url.replace('https://csgo-skins.com/case/', '')}' opened added to queue")

            # Uložení session před ukončením
            sb.sleep(3)
            save_cookies(sb)
            save_local_storage(sb)
            sb.sleep(1)
    except Exception as e:
        logging.error(f"Error opening case: {e}")
    '''
    with SB(uc=True, test=True) as sb:
        url = "www.planetminecraft.com/account/sign_in/"
        sb.activate_cdp_mode(url)
        sb.sleep(2)
        sb.cdp.gui_click_element("#turnstile-widget div")
        sb.sleep(2)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

async def run_telegram_bot_async():
    """Asynchronní spuštění Telegram bota"""
    global telegram
    telegram = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    telegram.add_handler(CommandHandler("help", help_command))
    
    # Spuštění procesoru screenshotů a zpráv
    asyncio.create_task(process_screenshots())
    asyncio.create_task(process_messages())
    
    async with telegram:
        await telegram.start()
        await telegram.updater.start_polling()
        
        # Nekonečná smyčka pro udržení bota běžícího
        while True:
            await asyncio.sleep(1)

def save_cookies(driver, filename="data/cookies.pkl"):
    """Uložení cookies do souboru"""
    try:
        cookies = driver.get_cookies()
        with open(filename, 'wb') as file:
            pickle.dump(cookies, file)
        logging.info(f"Cookies saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving cookies: {e}")

def load_cookies(driver, filename="data/cookies.pkl"):
    """Načtení cookies ze souboru"""
    try:
        if os.path.exists(filename):
            with open(filename, 'rb') as file:
                cookies = pickle.load(file)
            for cookie in cookies:
                driver.add_cookie(cookie)
            logging.info(f"Cookies loaded from {filename}")
            return True
    except Exception as e:
        logging.error(f"Error loading cookies: {e}")
    return False

def save_local_storage(driver, filename="data/localstorage.json"):
    """Uložení local storage"""
    try:
        local_storage = driver.execute_script("return window.localStorage;")
        with open(filename, 'w') as file:
            json.dump(local_storage, file)
        logging.info(f"Local storage saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving local storage: {e}")

def load_local_storage(driver, filename="data/localstorage.json"):
    """Načtení local storage"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as file:
                local_storage = json.load(file)
            for key, value in local_storage.items():
                driver.execute_script(f"window.localStorage.setItem('{key}', '{value}');")
            logging.info(f"Local storage loaded from {filename}")
            return True
    except Exception as e:
        logging.error(f"Error loading local storage: {e}")
    return False

def is_logged_in():
    """Kontrola, zda existují cookies a local storage pro přihlášení"""
    cookies_exist = os.path.exists("data/cookies.pkl")
    localstorage_exist = os.path.exists("data/localstorage.json")
    
    if cookies_exist and localstorage_exist:
        # Kontrola, zda soubory nejsou prázdné
        try:
            with open("data/cookies.pkl", 'rb') as f:
                cookies = pickle.load(f)
            with open("data/localstorage.json", 'r') as f:
                local_storage = json.load(f)
            
            # Kontrola, zda obsahují relevantní data
            has_cookies = len(cookies) > 0
            has_localstorage = len(local_storage) > 0
            
            logging.info(f"Session check - Cookies: {has_cookies}, LocalStorage: {has_localstorage}")
            return has_cookies and has_localstorage
            
        except (pickle.PickleError, json.JSONDecodeError, EOFError) as e:
            logging.warning(f"Error reading session files: {e}")
            return False

    logging.info("Session files do not exist")
    return False

def extract_countdown_time(html_content: str) -> dict:
    """
    Extrahuje zbývající čas z HTML countdown elementu
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        countdown_div = soup.find('span', class_='Countdown')
        
        if not countdown_div:
            logging.warning("Countdown element not found")
            return None
            
        # Najdeme všechny span elementy s čísly
        number_spans = countdown_div.find_all('span', class_='Countdown_numbers')
        
        if len(number_spans) < 3:
            return None
            
        # Extrakce hodnot
        hours = int(number_spans[0].get_text().strip())
        minutes = int(number_spans[1].get_text().strip())
        seconds = int(number_spans[2].get_text().strip())
        
        result = {
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'total_seconds': hours * 3600 + minutes * 60 + seconds
        }
        
        return result
        
    except Exception as e:
        logging.error(f"Error extracting countdown time: {e}")
        return None

def extract_countdown_from_element(driver, selector: str = ".Countdown") -> dict:
    """
    Extrahuje countdown přímo z webového elementu
    """
    try:
        countdown_element = driver.find_element(By.CSS_SELECTOR, selector)
        html_content = countdown_element.get_attribute('outerHTML')
        return extract_countdown_time(html_content)
        
    except Exception as e:
        return None

def format_countdown_time(time_dict: dict) -> datetime:
    """
    Vrací datetime kdy skončí countdown (current time + remaining time)
    """
    if not time_dict:
        return None
        
    hours = time_dict.get('hours', 0)
    minutes = time_dict.get('minutes', 0)
    seconds = time_dict.get('seconds', 0)
    
    # Vytvoření timedelta objektu
    time_remaining = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    
    # Přičtení k aktuálnímu času
    end_time = datetime.now() + time_remaining

    return end_time

def get_case_open_times(urls: List[str]) -> List[CaseOpenTime]:
    """Zjistí kdy bude možné otevřít další case"""
    results = []
    firstUrl = True
    driver = Driver(uc=True, proxy="socks5://" + os.environ.get("PROXY_HOST_IP"))
    try:
        for url in urls:
            # Otevření URL
            if firstUrl:
                firstUrl = False
                driver.uc_open_with_reconnect(url, 10)
                driver.uc_gui_click_captcha()
                time.sleep(1)
            else:
                driver.open(url)

            # Načtení cookies a local storage
            load_cookies(driver)
            load_local_storage(driver)
            driver.refresh()
            time.sleep(2)

            # Zjištění času do otevření case
            countdown_data = extract_countdown_from_element(driver, ".Countdown")

            if countdown_data:
                end_time = format_countdown_time(countdown_data)
                logging.info(f"{url.replace('https://csgo-skins.com/case/', '')} can be opened at {end_time}")
                results.append({
                    'url': url,
                    'end_time': end_time
                })
            else:
                logging.warning(f"Could not extract countdown for {url.replace('https://csgo-skins.com/case/', '')}")
                results.append({
                    'url': url,
                    'end_time': None
                })
            time.sleep(1)
    except Exception as e:
        logging.error(f"Error while getting case open times: {e}")
    finally:
        driver.quit()
    return results

def main():
    """Hlavní metoda"""
    logging.info("Starting")

    # Spuštění Telegram bota v asyncio tasku
    def run_bot_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_telegram_bot_async())
    
    telegram_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
    telegram_thread.start()
    
    # Čekání na inicializaci
    time.sleep(2)

    '''
    # Přihlášení na csgo-skins.com pouze pokud nejsou k dispozici cookies a local storage
    if not is_logged_in():
        logging.info("Valid session not found, logging in")
        loginSkins()
    else:
        logging.info("Valid session found, skipping login")
    
    # Otevření case
    urls = ["https://csgo-skins.com/case/daily-case", "https://csgo-skins.com/case/cs2-case"]
    caseTimes = get_case_open_times(urls)
    '''
    caseTimes = [
        {'url': '', 'end_time': None},]

    for case in caseTimes:
        # Nalezen čas
        if case['end_time']:
            schedule.every().day.at(case['end_time'].strftime("%H:%M")).do(openCase, case['url'])
        else:
            # Čas nenalezen, otevřít a naplánovat
            openCase(case['url'])
            case['end_time'] = datetime.now()
            schedule.every().day.at(case['end_time'].strftime("%H:%M")).do(openCase, case['url'])

    # Hlavní smyčka programu
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
