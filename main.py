import os
import time
import logging
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from seleniumbase import undetected
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio
import threading

# Logování
logging.basicConfig(
    level=logging.INFO,  # Nastavení úrovně logování
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formát zprávy
    datefmt='%Y-%m-%d %H:%M:%S'  # Formát času
)
# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# WSL2: https://superuser.com/questions/806637/xauth-not-creating-xauthority-file
def getDriver(url: str) -> undetected.Chrome:
    """ Inicializace WebDriveru """
    logging.info("Inicializuju web driver")
    driver = Driver(uc=True)
    driver.uc_open_with_reconnect(url, 10)
    driver.uc_gui_click_captcha()
    return driver

async def send_screenshot_to_user(user_id: int, image_path: str):
    """Odešle screenshot konkrétnímu uživateli"""
    try:
        with open(image_path, 'rb') as photo:
            await telegram.bot.send_photo(chat_id=user_id, photo=photo)
        logging.info(f"Screenshot odeslán uživateli {user_id}")
    except Exception as e:
        logging.error(f"Chyba při odesílání screenshotu: {e}")

def loginSkins():
    """ Přihlášení na csgo-skins.com """
    logging.info("Přihlašuji se na https://csgo-skins.com/")
    driver = getDriver("https://csgo-skins.com/")
    driver.find_element(By.TAG_NAME, "html").screenshot("screenshot.png")
    
    # Odeslání screenshotu konkrétnímu uživateli
    user_id = int(os.getenv("TELEGRAM_USER_ID"))  # Zadejte ID uživatele, kterému chcete poslat screenshot
    
    # Spuštění v novém vlákně aby neblokoval hlavní program
    def send_in_thread():
        try:
            asyncio.run(send_screenshot_to_user(user_id, "screenshot.png"))
        except Exception as e:
            logging.error(f"Chyba při odesílání: {e}")
    
    threading.Thread(target=send_in_thread, daemon=True).start()

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
        time.sleep(10)
        logging.info("Program běží...")

if __name__ == "__main__":
    main()
