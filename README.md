# csgo-skins-bot

## Debugging

```bash
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install google-chrome-stable

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Spuštění

```bash
sudo docker compose up -d --build
```

### Proměnné prostředí

- `TELEGRAM_TOKEN` - Token pro přístup k Telegram Bot API
- `TELEGRAM_USER_ID` - ID uživatele, kterému bude bot posílat zprávy
- `PROXY_IP_PORT` - IP adresa a port proxy serveru

#### Vytvoření bota

<https://t.me/botfather>

#### Získání svého ID

<https://t.me/getmyid_bot>
