const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json({ limit: '10mb' }));

const PYTHON_WEBHOOK = process.env.PYTHON_WEBHOOK || 'http://localhost:8080/webhook/whatsapp';
const PORT = process.env.BRIDGE_PORT || 3001;

// Auto-detect Chrome/Chromium path
function findChrome() {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;

  const candidates = process.platform === 'win32'
    ? [
        path.join(process.env['PROGRAMFILES'] || '', 'Google/Chrome/Application/chrome.exe'),
        path.join(process.env['PROGRAMFILES(X86)'] || '', 'Google/Chrome/Application/chrome.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe'),
        path.join(process.env['PROGRAMFILES'] || '', 'BraveSoftware/Brave-Browser/Application/brave.exe'),
        path.join(process.env['PROGRAMFILES'] || '', 'Microsoft/Edge/Application/msedge.exe'),
      ]
    : [
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
      ];

  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return undefined; // Let puppeteer use its bundled version
}

const chromePath = findChrome();
console.log(chromePath ? `Usando browser: ${chromePath}` : 'Usando Chromium bundled de puppeteer');

const puppeteerConfig = {
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--no-first-run',
    '--disable-gpu',
  ]
};

// Only set executablePath if we found a browser (otherwise puppeteer uses its own)
if (chromePath) {
  puppeteerConfig.executablePath = chromePath;
}

// RPi-specific args (low memory)
if (process.platform === 'linux' && process.arch === 'arm64') {
  puppeteerConfig.args.push('--single-process', '--no-zygote');
}

const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: puppeteerConfig
});

let currentQR = null;
let isReady = false;

client.on('qr', (qr) => {
  currentQR = qr;
  qrcode.generate(qr, { small: true });
  console.log('QR generado - escanea con WhatsApp');
});

client.on('ready', () => {
  isReady = true;
  currentQR = null;
  console.log('WhatsApp conectado');
});

client.on('disconnected', () => {
  isReady = false;
  console.log('WhatsApp desconectado, reiniciando...');
  client.initialize();
});

client.on('message_create', async (msg) => {
  // Skip messages from groups
  if (!msg.from.endsWith('@c.us') && !msg.to.endsWith('@c.us')) return;
  // Skip bot's own replies (only process user-sent messages)
  if (msg.fromMe && msg.to.endsWith('@c.us')) {
    // This is a message I sent TO someone, treat as user command
    // Only if sent to the bot's own number (self-chat)
  }
  if (!msg.fromMe && !msg.from.endsWith('@c.us')) return;
  // Determine the actual sender number
  const fromNumber = msg.fromMe ? msg.to : msg.from;
  // Only respond to our own number
  const MY_NUMBER = process.env.MY_NUMBER || '';
  if (MY_NUMBER && fromNumber !== MY_NUMBER && msg.from !== MY_NUMBER) return;

  const payload = {
    from: msg.fromMe ? msg.to : msg.from,
    body: msg.body,
    timestamp: msg.timestamp,
    hasMedia: msg.hasMedia,
    type: msg.type
  };

  if (msg.hasMedia) {
    try {
      const media = await msg.downloadMedia();
      payload.media = {
        mimetype: media.mimetype,
        data: media.data,
        filename: media.filename
      };
    } catch (e) {
      console.error('Error descargando media:', e.message);
    }
  }

  try {
    await fetch(PYTHON_WEBHOOK, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    console.error('Error enviando a Python:', e.message);
  }
});

app.post('/send', async (req, res) => {
  try {
    const { to, message } = req.body;
    await client.sendMessage(to, message);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/status', (_req, res) => res.json({ ready: isReady }));
app.get('/qr', (_req, res) => res.json({ qr: currentQR }));

app.listen(PORT, () => console.log(`Bridge en :${PORT}`));
client.initialize();
