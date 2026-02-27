import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
        credentials: 'include',
      });
      if (res.ok) {
        navigate('/');
      } else {
        setError('PIN incorrecto');
      }
    } catch {
      setError('Error de conexión');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-surface border border-surface-light rounded-2xl p-8 w-full max-w-xs">
        <h1 className="text-2xl font-bold text-primary text-center mb-6">FinBot</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="PIN"
            autoFocus
            className="w-full bg-bg border border-surface-light rounded-lg px-4 py-2.5 text-center text-lg tracking-[0.3em] focus:outline-none focus:border-primary"
          />
          {error && <p className="text-danger text-sm text-center">{error}</p>}
          <button type="submit" className="w-full bg-primary hover:bg-primary-dark text-white py-2.5 rounded-lg font-medium transition-colors">
            Entrar
          </button>
        </form>
      </div>
    </div>
  );
}
