/* ═══════════════════════════════════════════
   FINBOT v5 — Debts Management
   ═══════════════════════════════════════════ */

const debtForm = document.getElementById('debt-form');
const debtsListEl = document.getElementById('debts-list');

async function loadDebts() {
  try {
    const deudas = await apiFetch('/api/deudas');

    if (!deudas.length) {
      debtsListEl.innerHTML = '<div class="empty-state">Sin deudas registradas</div>';
      return;
    }

    debtsListEl.innerHTML = deudas.map(d => `
      <div class="debt-card">
        <div class="debt-header">
          <span class="debt-name">${d.nombre}</span>
          <span class="debt-balance">${formatCurrency(d.saldo_actual)}</span>
        </div>
        <div class="debt-details">
          <span>Tasa: ${d.tasa_interes_mensual}%</span>
          <span>Pago min: ${formatCurrency(d.pago_minimo)}</span>
          ${d.pagos && d.pagos.length ? `<span>Pagos: ${d.pagos.length}</span>` : ''}
        </div>
        <div class="debt-actions">
          <input type="number" class="debt-pago-input" id="pago-${d.id}" placeholder="Monto" step="0.01" min="0">
          <button class="btn-sm" onclick="registrarPago(${d.id})">Registrar pago</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Error loading debts:', e);
  }
}

debtForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const nombre = document.getElementById('debt-name').value.trim();
  const saldo = parseFloat(document.getElementById('debt-balance').value);
  const tasa = parseFloat(document.getElementById('debt-rate').value) || 0;
  const pagoMin = parseFloat(document.getElementById('debt-min').value) || 0;

  if (!nombre || !saldo) return;

  try {
    await apiPost('/api/deudas', {
      nombre,
      saldo_actual: saldo,
      tasa_interes_mensual: tasa,
      pago_minimo: pagoMin,
    });
    document.getElementById('debt-name').value = '';
    document.getElementById('debt-balance').value = '';
    document.getElementById('debt-rate').value = '0';
    document.getElementById('debt-min').value = '0';
    await loadDebts();
  } catch (e) {
    console.error('Error saving debt:', e);
  }
});

async function registrarPago(deudaId) {
  const input = document.getElementById(`pago-${deudaId}`);
  const monto = parseFloat(input.value);
  if (!monto || monto <= 0) return;

  try {
    await apiPost(`/api/deudas/${deudaId}/pago`, { monto });
    input.value = '';
    await loadDebts();
  } catch (e) {
    console.error('Error registering payment:', e);
  }
}

// Initial load
loadDebts();
