/* ═══════════════════════════════════════════
   FINBOT v6 — Accounts Management
   ═══════════════════════════════════════════ */

const accountForm = document.getElementById('account-form');
const accountsListEl = document.getElementById('accounts-list');

const ACCOUNT_TYPES = {
  efectivo: { label: 'Efectivo', icon: '💵' },
  banco: { label: 'Banco', icon: '🏦' },
  tarjeta_credito: { label: 'Tarjeta Credito', icon: '💳' },
  tarjeta_debito: { label: 'Tarjeta Debito', icon: '💳' },
  digital: { label: 'Digital', icon: '📱' },
};

async function loadAccounts() {
  try {
    const cuentas = await apiFetch('/api/cuentas');

    if (!cuentas.length) {
      accountsListEl.innerHTML = '<div class="empty-state">Sin cuentas registradas</div>';
      return;
    }

    accountsListEl.innerHTML = cuentas.map(c => {
      const typeInfo = ACCOUNT_TYPES[c.tipo] || { label: c.tipo, icon: '💰' };
      return `
        <div class="account-card" style="border-top: 2px solid ${c.color || 'var(--cyan)'}">
          <div class="account-header">
            <span class="account-name">${typeInfo.icon} ${c.nombre}</span>
            <button class="btn-danger" onclick="deleteAccount(${c.id})">X</button>
          </div>
          <div class="account-balance" style="color: ${c.color || 'var(--cyan)'}">${formatCurrency(c.saldo, c.moneda)}</div>
          <div class="account-details">
            <span class="account-type-badge">${typeInfo.label}</span>
            <span>${c.moneda}</span>
          </div>
        </div>`;
    }).join('');
  } catch (e) {
    console.error('Error loading accounts:', e);
  }
}

if (accountForm) {
  accountForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nombre = document.getElementById('account-name').value.trim();
    const tipo = document.getElementById('account-type').value;
    const moneda = document.getElementById('account-currency').value;
    const saldo = parseFloat(document.getElementById('account-balance').value) || 0;

    if (!nombre) return;

    try {
      await apiPost('/api/cuentas', { nombre, tipo, moneda, saldo });
      document.getElementById('account-name').value = '';
      document.getElementById('account-balance').value = '0';
      await loadAccounts();
    } catch (e) {
      console.error('Error saving account:', e);
    }
  });
}

async function deleteAccount(cuentaId) {
  if (!confirm('Eliminar esta cuenta?')) return;
  try {
    await apiDelete(`/api/cuentas/${cuentaId}`);
    await loadAccounts();
  } catch (e) {
    console.error('Error deleting account:', e);
  }
}

loadAccounts();
