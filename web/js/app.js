/* ═══════════════════════════════════════════
   FINBOT v5 — SPA Router & Global State
   ═══════════════════════════════════════════ */

let ws = null;
const wsListeners = [];  // modules register callbacks here

// ── SPA Router ────────────────────────────
function navigateTo(page) {
  document.querySelectorAll('.page-section').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.sidebar-nav a').forEach(el => el.classList.remove('active'));

  const target = document.getElementById(`page-${page}`);
  const link = document.querySelector(`[data-page="${page}"]`);
  if (target) target.classList.add('active');
  if (link) link.classList.add('active');

  // Notify page modules
  if (page === 'dashboard' && typeof refreshDashboard === 'function') refreshDashboard();
  if (page === 'chat' && typeof scrollChatBottom === 'function') scrollChatBottom();
  if (page === 'budgets' && typeof loadBudgets === 'function') loadBudgets();
  if (page === 'debts' && typeof loadDebts === 'function') loadDebts();
}

// Nav click handling
document.querySelectorAll('.sidebar-nav a').forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const page = link.dataset.page;
    window.location.hash = page;
    navigateTo(page);
  });
});

// Handle initial hash
function initRouter() {
  const hash = window.location.hash.replace('#', '') || 'dashboard';
  navigateTo(hash);
}
window.addEventListener('hashchange', () => {
  const hash = window.location.hash.replace('#', '') || 'dashboard';
  navigateTo(hash);
});

// ── WebSocket ─────────────────────────────
function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => console.log('[ws] connected');

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      wsListeners.forEach(fn => fn(data));
    } catch (e) {
      console.error('[ws] parse error:', e);
    }
  };

  ws.onclose = () => {
    console.log('[ws] disconnected, reconnecting...');
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => ws.close();
}

function wsSend(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

// ── WhatsApp QR Polling ───────────────────
const waStatusEl = document.getElementById('wa-status');
const qrBox = document.getElementById('sidebar-qr-box');

async function pollWhatsApp() {
  try {
    const st = await apiFetch('/api/whatsapp/status');
    if (st.ready) {
      waStatusEl.textContent = 'Conectado';
      waStatusEl.className = 'qr-status connected';
      qrBox.innerHTML = '';
      return;
    }
    waStatusEl.textContent = 'Desconectado';
    waStatusEl.className = 'qr-status disconnected';

    const r = await apiFetch('/api/whatsapp/qr');
    if (r.qr) {
      qrBox.innerHTML = '';
      const canvas = document.createElement('canvas');
      qrBox.appendChild(canvas);
      QRCode.toCanvas(canvas, r.qr, { width: 160, margin: 2, color: { dark: '#00f0ff', light: '#12121a' } });
    }
  } catch {
    waStatusEl.textContent = 'Sin bridge';
    waStatusEl.className = 'qr-status disconnected';
  }
}

// ── Boot ──────────────────────────────────
connectWebSocket();
pollWhatsApp();
setInterval(pollWhatsApp, 15000);
initRouter();
