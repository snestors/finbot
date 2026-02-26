/* ═══════════════════════════════════════════
   FINBOT v6 — Utilities
   ═══════════════════════════════════════════ */

let _userCurrency = 'PEN';

const CURRENCY_SYMBOLS = {
  PEN: 'S/',
  USD: '$',
  EUR: '€',
};

function getCurrencySymbol(moneda) {
  return CURRENCY_SYMBOLS[(moneda || _userCurrency).toUpperCase()] || 'S/';
}

function formatCurrency(amount, moneda) {
  const symbol = getCurrencySymbol(moneda);
  return `${symbol}${(amount || 0).toFixed(2)}`;
}

function formatTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
}

function formatDate(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleDateString('es-PE', { day: '2-digit', month: 'short' });
}

async function apiFetch(path, options) {
  const res = await fetch(path, options);
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('unauthorized');
  }
  return res.json();
}

async function apiPost(path, body) {
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function apiDelete(path) {
  return apiFetch(path, { method: 'DELETE' });
}

// Load user profile and set currency
async function loadUserProfile() {
  try {
    const perfil = await apiFetch('/api/perfil');
    if (perfil && perfil.moneda_default) {
      _userCurrency = perfil.moneda_default;
    }
    return perfil;
  } catch {
    return null;
  }
}
