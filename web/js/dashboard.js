/* ═══════════════════════════════════════════
   FINBOT v5 — Dashboard
   ═══════════════════════════════════════════ */

const statHoy = document.getElementById('stat-hoy');
const statSemana = document.getElementById('stat-semana');
const statMes = document.getElementById('stat-mes');
const statIngresos = document.getElementById('stat-ingresos');
const budgetBarsEl = document.getElementById('budget-bars');
const txListEl = document.getElementById('tx-list');

let catChart = null;

// ── Category colors ───────────────────────
const CAT_COLORS = {
  comida: '#00f0ff',
  transporte: '#ff2a6d',
  delivery: '#f5e642',
  entretenimiento: '#39ff14',
  servicios: '#9b59b6',
  salud: '#e67e22',
  compras: '#3498db',
  deuda_pago: '#e74c3c',
  otros: '#95a5a6',
};

function getCatColor(cat) {
  return CAT_COLORS[cat] || '#666680';
}

// ── Stat cards ────────────────────────────
async function refreshStats() {
  try {
    const [hoyGastos, mesGastos, ingresos] = await Promise.all([
      apiFetch('/api/gastos/hoy'),
      apiFetch('/api/gastos'),
      apiFetch('/api/ingresos'),
    ]);

    const totalHoy = hoyGastos.reduce((s, g) => s + g.monto, 0);
    const totalMes = mesGastos.reduce((s, g) => s + g.monto, 0);
    const totalIngresos = ingresos.reduce((s, i) => s + i.monto, 0);

    // Semana: filter from gastos del mes
    const now = new Date();
    const startOfWeek = new Date(now);
    startOfWeek.setDate(now.getDate() - now.getDay());
    startOfWeek.setHours(0, 0, 0, 0);
    const totalSemana = mesGastos
      .filter(g => new Date(g.fecha) >= startOfWeek)
      .reduce((s, g) => s + g.monto, 0);

    statHoy.textContent = formatCurrency(totalHoy);
    statSemana.textContent = formatCurrency(totalSemana);
    statMes.textContent = formatCurrency(totalMes);
    statIngresos.textContent = formatCurrency(totalIngresos);

    return mesGastos;
  } catch (e) {
    console.error('Error refreshing stats:', e);
    return [];
  }
}

// ── Category chart ────────────────────────
async function refreshCatChart() {
  try {
    const cats = await apiFetch('/api/resumen/categorias');
    const labels = Object.keys(cats);
    const data = Object.values(cats);
    const colors = labels.map(getCatColor);

    const ctx = document.getElementById('chart-categorias');
    if (!ctx) return;

    if (catChart) catChart.destroy();

    catChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
        datasets: [{
          data,
          backgroundColor: colors,
          borderWidth: 0,
          hoverBorderWidth: 2,
          hoverBorderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: '#666680',
              font: { family: "'Share Tech Mono', monospace", size: 11 },
              padding: 12,
              usePointStyle: true,
              pointStyleWidth: 8,
            },
          },
          tooltip: {
            backgroundColor: '#12121a',
            borderColor: '#1a1a2e',
            borderWidth: 1,
            titleFont: { family: "'Orbitron', sans-serif", size: 11 },
            bodyFont: { family: "'Share Tech Mono', monospace", size: 12 },
            callbacks: {
              label: (ctx) => ` S/${ctx.parsed.toFixed(2)}`,
            },
          },
        },
      },
    });
  } catch (e) {
    console.error('Error refreshing chart:', e);
  }
}

// ── Budget progress bars ──────────────────
async function refreshBudgetBars() {
  try {
    const [presupuestos, categorias] = await Promise.all([
      apiFetch('/api/presupuestos'),
      apiFetch('/api/resumen/categorias'),
    ]);

    if (!presupuestos.length) {
      budgetBarsEl.innerHTML = '<div class="empty-state">Sin presupuestos configurados</div>';
      return;
    }

    budgetBarsEl.innerHTML = presupuestos.map(p => {
      const spent = categorias[p.categoria] || 0;
      const pct = p.limite_mensual > 0 ? Math.min((spent / p.limite_mensual) * 100, 100) : 0;
      const level = pct >= 100 ? 'danger' : pct >= 80 ? 'warn' : 'ok';
      return `
        <div class="budget-item">
          <div class="budget-header">
            <span class="budget-cat">${p.categoria}</span>
            <span class="budget-nums">${formatCurrency(spent)} / ${formatCurrency(p.limite_mensual)}</span>
          </div>
          <div class="budget-bar">
            <div class="budget-bar-fill ${level}" style="width:${pct}%"></div>
          </div>
        </div>`;
    }).join('');
  } catch (e) {
    console.error('Error refreshing budget bars:', e);
  }
}

// ── Recent transactions ───────────────────
async function refreshTransactions() {
  try {
    const gastos = await apiFetch('/api/gastos/hoy');
    if (!gastos.length) {
      txListEl.innerHTML = '<div class="empty-state">Sin gastos hoy</div>';
      return;
    }
    txListEl.innerHTML = gastos.slice(0, 15).map(g => `
      <div class="tx-item">
        <span class="tx-desc">${g.descripcion || 'Gasto'}</span>
        <span class="tx-cat">${g.categoria}</span>
        <span class="tx-amount">${formatCurrency(g.monto)}</span>
      </div>
    `).join('');
  } catch (e) {
    console.error('Error refreshing transactions:', e);
  }
}

// ── Refresh all ───────────────────────────
async function refreshDashboard() {
  await Promise.all([
    refreshStats(),
    refreshCatChart(),
    refreshBudgetBars(),
    refreshTransactions(),
  ]);
}

// ── Listen for new messages → refresh ─────
wsListeners.push((data) => {
  if (data.type === 'new_messages') {
    refreshDashboard();
  }
});

// ── Initial load ──────────────────────────
refreshDashboard();
setInterval(refreshDashboard, 60000);
