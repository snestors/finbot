/* ═══════════════════════════════════════════
   FINBOT v6 — Settings / Profile
   ═══════════════════════════════════════════ */

const settingsForm = document.getElementById('settings-form');

async function loadSettings() {
  try {
    const perfil = await apiFetch('/api/perfil');
    if (perfil && perfil.nombre) {
      document.getElementById('settings-name').value = perfil.nombre || '';
      document.getElementById('settings-currency').value = perfil.moneda_default || 'PEN';
    }
  } catch (e) {
    console.error('Error loading settings:', e);
  }
}

if (settingsForm) {
  settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nombre = document.getElementById('settings-name').value.trim();
    const moneda = document.getElementById('settings-currency').value;

    try {
      await apiPost('/api/perfil', {
        nombre,
        moneda_default: moneda,
        onboarding_completo: 1,
      });
      // Update global currency
      _userCurrency = moneda;
      // Show confirmation
      const btn = settingsForm.querySelector('button[type="submit"]');
      const original = btn.textContent;
      btn.textContent = 'Guardado!';
      btn.style.background = 'var(--green)';
      setTimeout(() => {
        btn.textContent = original;
        btn.style.background = '';
      }, 2000);
    } catch (e) {
      console.error('Error saving settings:', e);
    }
  });
}

loadSettings();
