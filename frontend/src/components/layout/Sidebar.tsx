import { useEffect, useRef, useState } from 'react';
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
  { to: '/analytics', label: 'Analytics', icon: '📈' },
  { to: '/gastos-fijos', label: 'Gastos Fijos', icon: '📌' },
  { to: '/logs', label: 'Logs', icon: '📝' },
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

const SPARK_POINTS = 60; // ~60 seconds of data

function PowerSparkline({ power }: { power: number }) {
  const bufRef = useRef<number[]>([]);
  const [points, setPoints] = useState<number[]>([]);

  useEffect(() => {
    bufRef.current = [...bufRef.current.slice(-(SPARK_POINTS - 1)), power];
    setPoints([...bufRef.current]);
  }, [power]);

  if (points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 200;
  const h = 32;
  const pad = 1;

  const d = points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = pad + (1 - (v - min) / range) * (h - pad * 2);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  // area fill path
  const lastX = ((points.length - 1) / (points.length - 1)) * w;
  const areaD = `${d} L${lastX.toFixed(1)},${h} L0,${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8 mt-1" preserveAspectRatio="none">
      <defs>
        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#eab308" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#eab308" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill="url(#sparkGrad)" />
      <path d={d} fill="none" stroke="#eab308" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
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
        {stats && stats.printer && stats.printer.status !== 'idle' && (
          <div className="p-3 border-t border-surface-light space-y-1.5 text-[11px]">
            <div className="flex items-center justify-between text-cyan-400">
              <span className="font-medium flex items-center gap-1">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 6 2 18 2 18 9" />
                  <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                  <rect x="6" y="14" width="12" height="8" />
                </svg>
                3D Printer
              </span>
              <span className="font-mono font-bold">{stats.printer.progress}%</span>
            </div>
            <MiniBar pct={stats.printer.progress} color="bg-cyan-500" />
            {stats.printer.filename && (
              <div className="text-slate-400 truncate" title={stats.printer.filename}>
                {stats.printer.filename}
              </div>
            )}
            <div className="flex justify-between text-slate-400">
              <span>Capa</span>
              <span className="font-mono">{stats.printer.current_layer}/{stats.printer.total_layers}</span>
            </div>
            {stats.printer.eta_min > 0 && (
              <div className="flex justify-between text-slate-400">
                <span>ETA</span>
                <span className="font-mono">
                  {stats.printer.eta_min >= 60
                    ? `${Math.floor(stats.printer.eta_min / 60)}h ${stats.printer.eta_min % 60}m`
                    : `${stats.printer.eta_min}m`}
                </span>
              </div>
            )}
          </div>
        )}
        {stats && stats.power_w != null && (
          <div className="p-3 border-t border-surface-light space-y-1 text-[11px]">
            <div className="flex items-center justify-between text-yellow-400">
              <span className="font-medium">Consumo</span>
              <span className="font-mono font-bold">{stats.power_w.toFixed(0)} W</span>
            </div>
            <PowerSparkline power={stats.power_w} />
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
            {stats.wifi_dbm != null && (
              <div className="flex justify-between items-center">
                <span>WiFi</span>
                <span className="flex items-end gap-[2px]" title={`${stats.wifi_dbm} dBm`}>
                  {[1, 2, 3, 4].map(bar => {
                    const active = stats.wifi_dbm! > [-90, -70, -55, -40][bar - 1];
                    return (
                      <span
                        key={bar}
                        className={`inline-block w-[3px] rounded-sm ${active ? (stats.wifi_dbm! > -50 ? 'bg-green-400' : stats.wifi_dbm! > -70 ? 'bg-yellow-400' : 'bg-red-400') : 'bg-slate-600'}`}
                        style={{ height: `${bar * 3 + 2}px` }}
                      />
                    );
                  })}
                </span>
              </div>
            )}
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
