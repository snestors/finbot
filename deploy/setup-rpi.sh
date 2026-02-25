#!/bin/bash
# deploy/setup-rpi.sh
# Ejecutar como: sudo bash setup-rpi.sh
set -e

echo "=== FinBot RPi Setup ==="

echo "[1/8] Actualizando sistema..."
apt update && apt upgrade -y

echo "[2/8] Instalando Python y dependencias..."
apt install -y python3 python3-pip python3-venv git curl wget

echo "[3/8] Instalando Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

echo "[4/8] Instalando Chromium para whatsapp-web.js..."
apt install -y chromium-browser

echo "[5/8] Instalando cloudflared..."
ARCH=$(dpkg --print-architecture)
if [ "$ARCH" = "arm64" ]; then
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
    dpkg -i cloudflared-linux-arm64.deb
    rm cloudflared-linux-arm64.deb
elif [ "$ARCH" = "armhf" ]; then
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm.deb
    dpkg -i cloudflared-linux-arm.deb
    rm cloudflared-linux-arm.deb
fi

echo "[6/8] Creando usuario y directorio..."
useradd -m -s /bin/bash finbot 2>/dev/null || true
mkdir -p /opt/finbot
chown finbot:finbot /opt/finbot

echo "[7/8] Preparando proyecto..."
cd /opt/finbot
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cd whatsapp-bridge
npm install
cd ..

echo "[8/8] Creando directorios de datos..."
mkdir -p data/knowledge data/receipts
chown -R finbot:finbot /opt/finbot

# Swap (para RPi con poca RAM)
echo ""
read -p "Aumentar swap a 1GB? (recomendado para RPi 3) [y/N] " SWAP
if [ "$SWAP" = "y" ] || [ "$SWAP" = "Y" ]; then
    dphys-swapfile swapoff
    sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
    dphys-swapfile setup
    dphys-swapfile swapon
    echo "Swap aumentado a 1GB"
fi

echo ""
echo "=== Setup completo ==="
echo "Siguiente paso:"
echo "  1. Copia .env.example a .env y configura las variables"
echo "     (solo necesitas GOOGLE_AI_API_KEY y WHATSAPP_MY_NUMBER)"
echo "  3. Configura Cloudflare Tunnel (ver deploy/cloudflared.yml)"
echo "  4. Instala servicios systemd:"
echo "     sudo cp deploy/finbot.service /etc/systemd/system/"
echo "     sudo cp deploy/finbot-bridge.service /etc/systemd/system/"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable finbot-bridge finbot"
echo "     sudo systemctl start finbot-bridge finbot"
