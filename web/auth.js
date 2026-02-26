const loginForm = document.getElementById('login-form');
const pinInput = document.getElementById('pin');
const loginBtn = document.getElementById('login-btn');
const errorMsg = document.getElementById('error-msg');

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const pin = pinInput.value.trim();
  if (!pin) return;

  loginBtn.disabled = true;
  errorMsg.textContent = '';
  pinInput.classList.remove('error');

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });

    if (res.ok) {
      window.location.href = '/';
    } else {
      pinInput.classList.add('error');
      errorMsg.textContent = 'PIN incorrecto';
      pinInput.value = '';
      pinInput.focus();
    }
  } catch {
    errorMsg.textContent = 'Error de conexion';
  } finally {
    loginBtn.disabled = false;
  }
});
