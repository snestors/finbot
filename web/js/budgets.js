/* ═══════════════════════════════════════════
   FINBOT v6 — Budgets CRUD
   ═══════════════════════════════════════════ */

const budgetForm = document.getElementById('budget-form');
const budgetsListEl = document.getElementById('budgets-list');

async function loadBudgets() {
  try {
    const [presupuestos, categorias] = await Promise.all([
      apiFetch('/api/presupuestos'),
      apiFetch('/api/resumen/categorias'),
    ]);

    if (!presupuestos.length) {
      budgetsListEl.innerHTML = '<div class="empty-state">Crea tu primer presupuesto</div>';
      return;
    }

    budgetsListEl.innerHTML = presupuestos.map(p => {
      const spent = categorias[p.categoria] || 0;
      const pct = p.limite_mensual > 0 ? (spent / p.limite_mensual) * 100 : 0;
      const displayPct = Math.min(pct, 100);
      const level = pct >= 100 ? 'danger' : pct >= 80 ? 'warn' : 'ok';
      return `
        <div class="budget-item">
          <div class="budget-header">
            <span class="budget-cat">${p.categoria}</span>
            <span class="budget-nums">
              ${formatCurrency(spent)} / ${formatCurrency(p.limite_mensual)}
              (${pct.toFixed(0)}%)
              <button class="btn-danger" onclick="deleteBudget(${p.id})">Eliminar</button>
            </span>
          </div>
          <div class="budget-bar">
            <div class="budget-bar-fill ${level}" style="width:${displayPct}%"></div>
          </div>
        </div>`;
    }).join('');
  } catch (e) {
    console.error('Error loading budgets:', e);
  }
}

budgetForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const cat = document.getElementById('budget-cat').value;
  const limit = parseFloat(document.getElementById('budget-limit').value);
  const alert = parseInt(document.getElementById('budget-alert').value) || 80;

  if (!cat || !limit) return;

  try {
    await apiPost('/api/presupuestos', {
      categoria: cat,
      limite_mensual: limit,
      alerta_porcentaje: alert,
    });
    document.getElementById('budget-limit').value = '';
    await loadBudgets();
  } catch (e) {
    console.error('Error saving budget:', e);
  }
});

async function deleteBudget(id) {
  try {
    await apiDelete(`/api/presupuestos/${id}`);
    await loadBudgets();
  } catch (e) {
    console.error('Error deleting budget:', e);
  }
}

// Initial load
loadBudgets();
