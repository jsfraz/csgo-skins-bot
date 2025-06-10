FROM python:3-slim

# Instalace systémových závislostí pro Chrome a Xvfb
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    python3-tk \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalace Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Nastavení pracovního adresáře
WORKDIR /app

# Kopírování requirements.txt
COPY requirements.txt .

# Instalace Python závislostí
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování aplikace
COPY . .

# Vytvoření adresáře pro Chrome profil
RUN mkdir -p /app/data/chrome_profile && chmod 755 /app/data/chrome_profile

# Nastavení proměnných prostředí
ENV PYTHONUNBUFFERED=1

# Spuštění aplikace přes xvfb-run
CMD ["sh", "-c", "xvfb-run -a --server-args='-screen 0 1920x1080x24' python -u main.py 2>&1"]