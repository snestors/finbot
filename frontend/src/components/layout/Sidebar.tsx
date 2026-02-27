import { NavLink } from 'react-router-dom';
import { useChatStore } from '../../store/chatStore';

const links = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/chat', label: 'Chat', icon: '💬' },
  { to: '/gastos', label: 'Gastos', icon: '💸' },
  { to: '/cuentas', label: 'Cuentas', icon: '🏦' },
  { to: '/tarjetas', label: 'Tarjetas', icon: '💳' },
  { to: '/deudas', label: 'Deudas', icon: '📋' },
  { to: '/cobros', label: 'Cobros', icon: '🤝' },
  { to: '/consumos', label: 'Consumos', icon: '⚡' },
  { to: '/presupuestos', label: 'Presupuestos', icon: '🎯' },
  { to: '/tipo-cambio', label: 'Tipo Cambio', icon: '💱' },
  { to: '/config', label: 'Config', icon: '⚙️' },
];

function tempColor(t: number | null) {
  if (t == null) return 'text-slate-400';
  if (t < 50) return 'text-green-400';
  if (t < 65) return 'text-yellow-400';
  return 'text-red-400';
}

function MiniBar({ pct, color = 'bg-primary' }: { pct: number; color?: string }) {
  return (
    <div className="h-1.5 w-full bg-surface-light rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const stats = useChatStore((s) => s.systemStats);

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={onClose} />}
      <aside className={`fixed lg:static inset-y-0 left-0 z-40 w-56 bg-surface border-r border-surface-light flex flex-col transition-transform lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-4 border-b border-surface-light">
          <h1 className="text-xl font-bold text-primary">FinBot</h1>
        </div>
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {links.map(l => (
            <NavLink
              key={l.to}
              to={l.to}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive ? 'bg-primary/15 text-primary font-medium' : 'text-slate-300 hover:bg-surface-light'
                }`
              }
            >
              <span className="text-base">{l.icon}</span>
              {l.label}
            </NavLink>
          ))}
        </nav>
        {stats && stats.power_w != null && (
          <div className="p-3 border-t border-surface-light space-y-1 text-[11px]">
            <div className="flex items-center justify-between text-yellow-400">
              <span className="font-medium">Consumo</span>
              <span className="font-mono font-bold">{stats.power_w.toFixed(0)} W</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Corriente</span>
              <span className="font-mono">{(stats.current_a ?? 0).toFixed(2)} A</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Hoy</span>
              <span className="font-mono">{(stats.day_kwh ?? 0).toFixed(2)} kWh</span>
            </div>
          </div>
        )}
        {stats && (
          <div className="p-3 border-t border-surface-light space-y-2 text-[11px] text-slate-400">
            <div className="flex justify-between">
              <span>Temp</span>
              <span className={tempColor(stats.temp)}>{stats.temp != null ? `${stats.temp.toFixed(1)}°C` : '--'}</span>
            </div>
            <div>
              <div className="flex justify-between mb-0.5">
                <span>RAM</span>
                <span>{stats.mem_pct != null ? `${stats.mem_pct}%` : '--'}</span>
              </div>
              <MiniBar pct={stats.mem_pct ?? 0} color={(stats.mem_pct ?? 0) > 85 ? 'bg-red-500' : 'bg-primary'} />
            </div>
            <div>
              <div className="flex justify-between mb-0.5">
                <span>CPU</span>
                <span>{stats.cpu_pct != null ? `${stats.cpu_pct}%` : '--'}</span>
              </div>
              <MiniBar pct={stats.cpu_pct ?? 0} color={(stats.cpu_pct ?? 0) > 85 ? 'bg-red-500' : 'bg-primary'} />
            </div>
            <div>
              <div className="flex justify-between mb-0.5">
                <span>Disco</span>
                <span>{stats.disk_pct != null ? `${stats.disk_pct}%` : '--'}</span>
              </div>
              <MiniBar pct={stats.disk_pct ?? 0} color={(stats.disk_pct ?? 0) > 90 ? 'bg-red-500' : 'bg-primary'} />
            </div>
            {stats.uptime && (
              <div className="flex justify-between">
                <span>Uptime</span>
                <span>{stats.uptime}</span>
              </div>
            )}
          </div>
        )}
      </aside>
    </>
  );
}
