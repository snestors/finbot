/* ═══════════════════════════════════════════
   FINBOT v6 — Debts Management
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

    debtsListEl.innerHTML = deudas.map(d => {
      const entidad = d.entidad ? `<span class="debt-entidad">${d.entidad}</span>` : '';
      let cuotasHtml = '';
      if (d.cuotas_total && d.cuotas_total > 0) {
        const pagadas = d.cuotas_pagadas || 0;
        const pct = Math.min((pagadas / d.cuotas_total) * 100, 100);
        cuotasHtml = `
          <div class="debt-cuotas">
            <span class="cuotas-label">Cuotas: ${pagadas}/${d.cuotas_total}</span>
            ${d.cuota_monto ? `<span class="cuota-monto">${formatCurrency(d.cuota_monto)}/cuota</span>` : ''}
            <div class="budget-bar" style="margin-top:4px">
              <div class="budget-bar-fill ${pct >= 100 ? 'ok' : pct >= 60 ? 'warn' : 'danger'}" style="width:${pct}%"></div>
            </div>
          </div>`;
      }

      return `
        <div class="debt-card">
          <div class="debt-header">
            <div>
              <span class="debt-name">${d.nombre}</span>
              ${entidad}
            </div>
            <span class="debt-balance">${formatCurrency(d.saldo_actual)}</span>
          </div>
          <div class="debt-details">
            <span>Tasa: ${d.tasa_interes_mensual}%</span>
            <span>Pago min: ${formatCurrency(d.pago_minimo)}</span>
            ${d.pagos && d.pagos.length ? `<span>Pagos: ${d.pagos.length}</span>` : ''}
          </div>
          ${cuotasHtml}
          <div class="debt-actions">
            <input type="number" class="debt-pago-input" id="pago-${d.id}" placeholder="Monto" step="0.01" min="0">
            <button class="btn-sm" onclick="registrarPago(${d.id})">Registrar pago</button>
          </div>
        </div>`;
    }).join('');
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
  const entidad = document.getElementById('debt-entidad').value.trim();
  const cuotasTotal = parseInt(document.getElementById('debt-cuotas-total').value) || 0;
  const cuotaMonto = parseFloat(document.getElementById('debt-cuota-monto').value) || 0;

  if (!nombre || !saldo) return;

  try {
    await apiPost('/api/deudas', {
      nombre,
      saldo_actual: saldo,
      tasa_interes_mensual: tasa,
      pago_minimo: pagoMin,
      entidad: entidad || null,
      cuotas_total: cuotasTotal,
      cuota_monto: cuotaMonto,
    });
    document.getElementById('debt-name').value = '';
    document.getElementById('debt-balance').value = '';
    document.getElementById('debt-rate').value = '0';
    document.getElementById('debt-min').value = '0';
    document.getElementById('debt-entidad').value = '';
    document.getElementById('debt-cuotas-total').value = '0';
    document.getElementById('debt-cuota-monto').value = '0';
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
