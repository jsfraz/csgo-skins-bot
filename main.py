import os
import sys
import time
import asyncio
import logging
import threading
import queue
from io import BytesIO
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from seleniumbase import undetected
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Konfigurace logging s flush
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Pro okamžité zobrazení použijte flush
print("Starting application", flush=True)

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# WSL2: https://superuser.com/questions/806637/xauth-not-creating-xauthority-file
def getDriver(url: str) -> undetected.Chrome:
    """ Inicializace WebDriveru """
    logging.info("Initializing web driver")
    driver = Driver(uc=True)
    
    # https://stackoverflow.com/a/75110523/19371130
    driver.options.add_argument("--no-sandbox")
    driver.options.add_argument("--disable-dev-shm-usage")
    driver.options.add_argument("--disable-renderer-backgrounding")
    driver.options.add_argument("--disable-background-timer-throttling")
    driver.options.add_argument("--disable-backgrounding-occluded-windows")
    driver.options.add_argument("--disable-client-side-phishing-detection")
    driver.options.add_argument("--disable-crash-reporter")
    driver.options.add_argument("--disable-oopr-debug-crash-dump")
    driver.options.add_argument("--no-crash-upload")
    driver.options.add_argument("--disable-gpu")
    driver.options.add_argument("--disable-extensions")
    driver.options.add_argument("--disable-low-res-tiling")
    driver.options.add_argument("--log-level=3")
    driver.options.add_argument("--silent")

    driver.uc_open_with_reconnect(url, 10)
    driver.uc_gui_click_captcha()
    
    return driver

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

# Globální proměnná pro event loop
telegram_loop = None

# Globální queue
screenshot_queue = queue.Queue()

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

def loginSkins():
    """Přihlášení na csgo-skins.com """
    logging.info("Logging in to https://csgo-skins.com/")
    driver = getDriver("https://csgo-skins.com/")

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
    logging.info("User logged in")


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    '''
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )
    '''

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)

async def run_telegram_bot_async():
    """Asynchronní spuštění Telegram bota"""
    global telegram
    telegram = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    telegram.add_handler(CommandHandler("start", start))
    telegram.add_handler(CommandHandler("help", help_command))
    telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # Spuštění procesoru screenshotů
    asyncio.create_task(process_screenshots())
    
    async with telegram:
        await telegram.start()
        await telegram.updater.start_polling()
        
        # Nekonečná smyčka pro udržení bota běžícího
        while True:
            await asyncio.sleep(1)

def main():
    """ Hlavní metoda """
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

    # Přihlášení na csgo-skins.com
    loginSkins()
    
    # Hlavní smyčka programu
    while True:
        pass

if __name__ == "__main__":
    main()
