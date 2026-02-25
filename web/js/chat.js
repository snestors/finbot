/* ═══════════════════════════════════════════
   FINBOT v5 — Chat
   ═══════════════════════════════════════════ */

const messagesEl = document.getElementById('chat-messages');
const chatText = document.getElementById('chat-text');
const btnSend = document.getElementById('btn-send');
const btnUpload = document.getElementById('btn-upload-receipt');
const receiptFile = document.getElementById('receipt-file');

function scrollChatBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function sourceBadge(source) {
  if (source === 'whatsapp') return '<span class="badge wa">WA</span>';
  if (source === 'web') return '<span class="badge web">Web</span>';
  if (source === 'bot_proactive') return '<span class="badge bot-pro">Auto</span>';
  return '';
}

function addMessage(role, content, source, timestamp) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;

  const textSpan = document.createElement('span');
  textSpan.textContent = content;
  div.appendChild(textSpan);

  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.innerHTML = `${sourceBadge(source || (role === 'bot' ? 'bot' : 'web'))} <span>${formatTime(timestamp)}</span>`;
  div.appendChild(meta);

  messagesEl.appendChild(div);
  scrollChatBottom();
}

// ── Load history ──────────────────────────
async function loadHistory() {
  try {
    const msgs = await apiFetch('/api/mensajes?limit=50');
    messagesEl.innerHTML = '';
    msgs.forEach(m => addMessage(m.role, m.content, m.source, m.timestamp));
  } catch (e) {
    console.error('Error loading history:', e);
  }
}

// ── Send message ──────────────────────────
function sendMessage() {
  const text = chatText.value.trim();
  if (!text) return;
  wsSend({ type: 'message', text });
  chatText.value = '';
  chatText.focus();
}

btnSend.addEventListener('click', sendMessage);
chatText.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── Upload receipt ────────────────────────
btnUpload.addEventListener('click', () => receiptFile.click());
receiptFile.addEventListener('change', async () => {
  const file = receiptFile.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    addMessage('user', `[Subiendo recibo: ${file.name}]`, 'web', new Date().toISOString());
    await fetch('/api/upload-receipt', { method: 'POST', body: formData });
  } catch (e) {
    addMessage('bot', 'Error subiendo recibo', 'bot', new Date().toISOString());
  }
  receiptFile.value = '';
});

// ── WebSocket listener ────────────────────
wsListeners.push((data) => {
  if (data.type === 'new_messages') {
    if (data.user_message) {
      addMessage('user', data.user_message.content, data.user_message.source, data.user_message.timestamp);
    }
    if (data.bot_response) {
      addMessage('bot', data.bot_response.content, data.bot_response.source, data.bot_response.timestamp);
    }
  }
});

// ── Initial load ──────────────────────────
loadHistory();
