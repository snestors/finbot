const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json({ limit: '10mb' }));

const PYTHON_WEBHOOK = process.env.PYTHON_WEBHOOK || 'http://localhost:8080/webhook/whatsapp';
const PORT = process.env.BRIDGE_PORT || 3001;
const MY_NUMBER = process.env.MY_NUMBER || '';

// Track messages sent by the bot to prevent infinite loops
const botSentIds = new Set();

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
  return undefined;
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

if (chromePath) {
  puppeteerConfig.executablePath = chromePath;
}

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
  if (MY_NUMBER) console.log(`Filtrando solo numero: ${MY_NUMBER}`);
});

client.on('disconnected', () => {
  isReady = false;
  console.log('WhatsApp desconectado, reiniciando...');
  client.initialize();
});

// --- Handle incoming messages from others ---
client.on('message', async (msg) => {
  if (msg.from === 'status@broadcast') return;
  if (msg.fromMe) return;
  await handleMessage(msg, false);
});

// --- Handle self-sent messages (user typing from their phone) ---
client.on('message_create', async (msg) => {
  if (!msg.fromMe) return; // Incoming already handled by 'message' event
  if (msg.from === 'status@broadcast') return;
  await handleMessage(msg, true);
});

async function handleMessage(msg, isSelfSent) {
  try {
    // Skip group messages
    if (msg.from?.endsWith('@g.us') || msg.to?.endsWith('@g.us')) return;

    // Skip bot's own replies (prevent infinite loop)
    const msgId = msg.id?._serialized || msg.id?.id;
    if (msgId && botSentIds.has(msgId)) {
      botSentIds.delete(msgId);
      console.log('[bridge] Skipped bot-sent reply');
      return;
    }

    // For self-sent: only process self-chat (don't leak to friends)
    if (isSelfSent) {
      if (MY_NUMBER && msg.to !== MY_NUMBER) {
        return;
      }
    }

    // Resolve chatId: prefer @c.us over @lid (WhatsApp sometimes sends LIDs)
    let chatId;
    if (isSelfSent) {
      chatId = MY_NUMBER || msg.to;
    } else {
      chatId = msg.from;
      if (chatId?.endsWith('@lid')) {
        try {
          const contact = await msg.getContact();
          if (contact.number) {
            chatId = contact.number + '@c.us';
          }
        } catch (_) {}
      }
    }

    // MY_NUMBER filter: only process messages involving our number
    if (MY_NUMBER && !isSelfSent) {
      // For incoming: chatId is the sender. We still process it since it's directed at us.
      // But if we only want self-chat, uncomment the next line:
      // return;
    }

    console.log(`[bridge] ${isSelfSent ? 'SELF' : 'IN'} chatId=${chatId} body="${(msg.body || '').substring(0, 80)}"`);

    const payload = {
      from: chatId,
      body: msg.body || '',
      timestamp: msg.timestamp,
      hasMedia: msg.hasMedia,
      type: msg.type,
    };

    if (msg.hasMedia) {
      try {
        const media = await msg.downloadMedia();
        if (media) {
          payload.media = {
            mimetype: media.mimetype,
            data: media.data,
            filename: media.filename,
          };
        }
      } catch (e) {
        console.error('[bridge] Error downloading media:', e.message);
      }
    }

    try {
      const resp = await fetch(PYTHON_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      console.log(`[bridge] Webhook response: ${resp.status}`);
    } catch (e) {
      console.error('[bridge] Error sending to Python:', e.message);
    }
  } catch (err) {
    console.error('[bridge] handleMessage error:', err.message);
  }
}

// --- Send endpoint (called by Python to reply) ---
app.post('/send', async (req, res) => {
  try {
    const { to, message } = req.body;
    const sent = await client.sendMessage(to, message);
    // Track this message ID to skip it in message_create
    const sentId = sent?.id?._serialized || sent?.id?.id;
    if (sentId) {
      botSentIds.add(sentId);
      setTimeout(() => botSentIds.delete(sentId), 60000);
    }
    console.log(`[bridge] Sent reply to ${to}`);
    res.json({ ok: true });
  } catch (e) {
    console.error('[bridge] Error sending:', e.message);
    res.status(500).json({ error: e.message });
  }
});

app.get('/status', (_req, res) => res.json({ ready: isReady }));
app.get('/qr', (_req, res) => res.json({ qr: currentQR }));

app.listen(PORT, () => console.log(`Bridge en :${PORT}`));
client.initialize();
