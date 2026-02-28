import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { get, post, del } from '../api/client';
import { Card } from '../components/ui/Card';
import { useChatStore } from '../store/chatStore';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';

const now = new Date();
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
const todayStr = now.toISOString().slice(0, 10);

const TABS = [
  { key: 'luz', label: 'Luz', icon: '⚡' },
  { key: 'agua', label: 'Agua', icon: '💧' },
  { key: 'gas', label: 'Gas', icon: '🔥' },
] as const;

const LUZ_SUBTABS = ['En Vivo', 'Grafico', 'Pagos', 'Config'] as const;
type LuzSubTab = typeof LUZ_SUBTABS[number];

export default function Consumos() {
  const [tab, setTab] = useState<string>('luz');
  const [mes, setMes] = useState(currentMonth);
  const [luzSub, setLuzSub] = useState<LuzSubTab>('En Vivo');
  const queryClient = useQueryClient();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-bold">Consumos</h2>
        {(tab !== 'luz' || luzSub === 'En Vivo') && (
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary"
          />
        )}
      </div>

      {/* Main Tabs */}
      <div className="flex gap-1 bg-surface border border-surface-light rounded-lg p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t.key ? 'bg-primary/20 text-primary' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Luz sub-tabs */}
      {tab === 'luz' && (
        <div className="flex gap-1 bg-surface/50 border border-surface-light rounded-lg p-1">
          {LUZ_SUBTABS.map((st) => (
            <button
              key={st}
              onClick={() => setLuzSub(st)}
              className={`flex-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                luzSub === st ? 'bg-yellow-500/20 text-yellow-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      {tab === 'luz' && luzSub === 'En Vivo' && <LuzEnVivo mes={mes} queryClient={queryClient} />}
      {tab === 'luz' && luzSub === 'Grafico' && <LuzGrafico />}
      {tab === 'luz' && luzSub === 'Pagos' && <LuzPagos />}
      {tab === 'luz' && luzSub === 'Config' && <LuzConfig />}
      {tab !== 'luz' && <ManualTab tipo={tab} unidad="m3" mes={mes} queryClient={queryClient} />}
    </div>
  );
}

/* ─── En Vivo ─── */
const MAX_LIVE_POINTS = 120; // 2 min of data at ~1s intervals

function LuzEnVivo({ mes: _mes, queryClient: _qc }: { mes: string; queryClient: any }) {
  const stats = useChatStore((s) => s.systemStats);
  const bufferRef = useRef<Array<{ time: string; power_w: number; current_a: number; voltage_v: number }>>([]);
  const [liveData, setLiveData] = useState<typeof bufferRef.current>([]);

  useEffect(() => {
    if (!stats || stats.power_w == null) return;
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    const point = {
      time,
      power_w: Math.round(stats.power_w),
      current_a: Math.round((stats.current_a ?? 0) * 100) / 100,
      voltage_v: Math.round((stats.voltage_v ?? 0) * 10) / 10,
    };
    bufferRef.current = [...bufferRef.current.slice(-(MAX_LIVE_POINTS - 1)), point];
    setLiveData([...bufferRef.current]);
  }, [stats]);

  return (
    <>
      {/* Live cards */}
      {stats && stats.power_w != null && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <LiveCard label="Potencia" value={`${stats.power_w.toFixed(0)} W`} color="text-yellow-400" />
          <LiveCard label="Voltaje" value={`${(stats.voltage_v ?? 0).toFixed(1)} V`} />
          <LiveCard label="Corriente" value={`${(stats.current_a ?? 0).toFixed(2)} A`} color="text-blue-400" />
          <LiveCard label="Hoy" value={`${(stats.day_kwh ?? 0).toFixed(2)} kWh`} color="text-green-400" />
          <LiveCard label="Mes" value={`${(stats.month_kwh ?? 0).toFixed(2)} kWh`} />
        </div>
      )}

      {/* Live chart */}
      <Card>
        <h3 className="text-sm font-semibold mb-3">Consumo en Tiempo Real</h3>
        {liveData.length === 0 && (
          <p className="text-sm text-slate-500">Esperando datos del sensor...</p>
        )}
        {liveData.length > 0 && (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={liveData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#eab308' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#3b82f6' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line yAxisId="left" type="monotone" dataKey="power_w" stroke="#eab308" name="Potencia (W)" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line yAxisId="right" type="monotone" dataKey="current_a" stroke="#3b82f6" name="Corriente (A)" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line yAxisId="left" type="monotone" dataKey="voltage_v" stroke="#22c55e" name="Voltaje (V)" dot={false} strokeWidth={1.5} isAnimationActive={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    </>
  );
}

/* ─── Grafico ─── */
function LuzGrafico() {
  const [desde, setDesde] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().slice(0, 10);
  });
  const [hasta, setHasta] = useState(todayStr);
  const [slice, setSlice] = useState(1);

  const { data: chartData, isLoading } = useQuery({
    queryKey: ['consumos-chart', desde, hasta, slice],
    queryFn: () => get<any[]>(
      `/api/consumos/chart?tipo=luz&desde=${desde}T00:00:00&hasta=${hasta}T23:59:59&slice=${slice}`
    ),
  });

  const formatted = useMemo(() => {
    if (!chartData) return [];
    return chartData.map((d: any) => ({
      ...d,
      label: d.fecha?.slice(5, 16)?.replace('T', ' ') ?? '',
      power_w: d.power_w != null ? Math.round(d.power_w * 10) / 10 : null,
      current_a: d.current_a != null ? Math.round(d.current_a * 100) / 100 : null,
    }));
  }, [chartData]);

  const exportCSV = useCallback(() => {
    if (!formatted.length) return;
    const header = 'Fecha,Potencia (W),Corriente (A),Voltaje (V),kWh dia\n';
    const rows = formatted.map((d: any) =>
      `${d.fecha ?? ''},${d.power_w ?? ''},${d.current_a ?? ''},${d.voltage_v ?? ''},${d.day_kwh ?? ''}`
    ).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `consumo_luz_${desde}_${hasta}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [formatted, desde, hasta]);

  return (
    <div className="space-y-3">
      <Card>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Desde</label>
            <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)}
              className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Hasta</label>
            <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)}
              className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Agrupar</label>
            <div className="flex gap-1">
              {[{ v: 1, l: '1h' }, { v: 2, l: '2h' }, { v: 4, l: '4h' }, { v: 8, l: '8h' }, { v: 24, l: '24h' }].map(({ v, l }) => (
                <button key={v} onClick={() => setSlice(v)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    slice === v ? 'bg-primary/20 text-primary' : 'bg-surface border border-surface-light text-slate-400 hover:text-slate-200'
                  }`}
                >{l}</button>
              ))}
            </div>
          </div>
          <button
            onClick={exportCSV}
            disabled={formatted.length === 0}
            className="px-3 py-1.5 rounded-lg text-sm font-medium bg-surface border border-surface-light text-slate-300 hover:text-white hover:border-primary disabled:opacity-40 transition-colors"
          >
            Exportar CSV
          </button>
        </div>
      </Card>

      <Card>
        {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {!isLoading && formatted.length === 0 && <p className="text-sm text-slate-500">Sin datos para este periodo</p>}
        {formatted.length > 0 && (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={formatted} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#94a3b8' }} interval="preserveStartEnd" />
              <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#eab308' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#3b82f6' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line yAxisId="left" type="monotone" dataKey="power_w" stroke="#eab308" name="Potencia (W)" dot={false} strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="current_a" stroke="#3b82f6" name="Corriente (A)" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  );
}

/* ─── Pagos ─── */
function LuzPagos() {
  const queryClient = useQueryClient();
  const [monto, setMonto] = useState('');
  const [fechaPago, setFechaPago] = useState(todayStr);
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [notas, setNotas] = useState('');

  const { data: pagos, isLoading } = useQuery({
    queryKey: ['consumos-pagos', 'luz'],
    queryFn: () => get<any[]>('/api/consumos/pagos?tipo=luz'),
  });

  const mutation = useMutation({
    mutationFn: (data: any) => post('/api/consumos/pagos', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consumos-pagos'] });
      setMonto(''); setNotas(''); setFechaDesde(''); setFechaHasta('');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!monto) return;
    mutation.mutate({
      tipo: 'luz',
      monto: parseFloat(monto),
      fecha_pago: fechaPago,
      fecha_desde: fechaDesde,
      fecha_hasta: fechaHasta,
      notas,
    });
  };

  return (
    <div className="space-y-3">
      <Card>
        <h3 className="text-sm font-semibold mb-3">Registrar Pago de Luz</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Monto (S/)</label>
              <input type="number" step="0.01" value={monto} onChange={(e) => setMonto(e.target.value)}
                placeholder="0.00" className="w-full bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Fecha pago</label>
              <input type="date" value={fechaPago} onChange={(e) => setFechaPago(e.target.value)}
                className="w-full bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Periodo desde</label>
              <input type="date" value={fechaDesde} onChange={(e) => setFechaDesde(e.target.value)}
                className="w-full bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Periodo hasta</label>
              <input type="date" value={fechaHasta} onChange={(e) => setFechaHasta(e.target.value)}
                className="w-full bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
            </div>
          </div>
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="block text-xs text-slate-400 mb-1">Notas</label>
              <input type="text" value={notas} onChange={(e) => setNotas(e.target.value)}
                placeholder="Opcional" className="w-full bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
            </div>
            <button type="submit" disabled={mutation.isPending}
              className="bg-primary text-black px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
              {mutation.isPending ? 'Guardando...' : 'Registrar Pago'}
            </button>
          </div>
          {mutation.isSuccess && mutation.data && (
            <p className="text-xs text-green-400">
              Pago registrado — {(mutation.data as any).kwh_periodo?.toFixed(1) ?? '?'} kWh,
              S/{(mutation.data as any).costo_kwh?.toFixed(4) ?? '?'}/kWh
            </p>
          )}
        </form>
      </Card>

      <Card>
        <h3 className="text-sm font-semibold mb-3">Historial de Pagos</h3>
        {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {!isLoading && (pagos || []).length === 0 && <p className="text-sm text-slate-500">Sin pagos registrados</p>}
        {(pagos || []).length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs border-b border-surface-light">
                  <th className="pb-2 pr-3">Fecha</th>
                  <th className="pb-2 pr-3 text-right">Monto</th>
                  <th className="pb-2 pr-3">Periodo</th>
                  <th className="pb-2 pr-3 text-right">kWh</th>
                  <th className="pb-2 pr-3 text-right">S//kWh</th>
                  <th className="pb-2 pr-3">Notas</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {(pagos || []).map((p: any) => (
                  <tr key={p.id} className="border-b border-surface-light/50 hover:bg-surface-light/30">
                    <td className="py-2 pr-3 text-slate-400 whitespace-nowrap">{p.fecha_pago}</td>
                    <td className="py-2 pr-3 text-right font-mono font-medium">S/{p.monto.toFixed(2)}</td>
                    <td className="py-2 pr-3 text-slate-400 text-xs">{p.fecha_desde} a {p.fecha_hasta}</td>
                    <td className="py-2 pr-3 text-right font-mono">{p.kwh_periodo?.toFixed(1) ?? '-'}</td>
                    <td className="py-2 pr-3 text-right font-mono">{p.costo_kwh?.toFixed(4) ?? '-'}</td>
                    <td className="py-2 pr-3 text-slate-400 text-xs">{p.notas}</td>
                    <td className="py-2">
                      <DeleteBtn onDelete={() => del(`/api/consumos/pagos/${p.id}`).then(() => {
                        queryClient.invalidateQueries({ queryKey: ['consumos-pagos'] });
                      })} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

/* ─── Config ─── */
function LuzConfig() {
  const queryClient = useQueryClient();
  const stats = useChatStore((s) => s.systemStats);

  const { data: config } = useQuery({
    queryKey: ['consumos-config'],
    queryFn: () => get<Record<string, string>>('/api/consumos/config'),
  });

  const [costoKwh, setCostoKwh] = useState('');
  const loaded = config?.costo_kwh_luz;

  const saveMut = useMutation({
    mutationFn: (data: any) => post('/api/consumos/config', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['consumos-config'] }),
  });

  const currentCosto = costoKwh || loaded || '0.75';
  const monthKwh = stats?.month_kwh ?? 0;
  const estimado = monthKwh * parseFloat(currentCosto || '0');

  return (
    <div className="space-y-3">
      <Card>
        <h3 className="text-sm font-semibold mb-3">Configuracion de Luz</h3>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Costo por kWh (S/)</label>
            <input
              type="number" step="0.0001"
              value={costoKwh || loaded || ''}
              onChange={(e) => setCostoKwh(e.target.value)}
              placeholder="0.75"
              className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm w-32 focus:outline-none focus:border-primary"
            />
          </div>
          <button
            onClick={() => saveMut.mutate({ costo_kwh_luz: costoKwh || loaded || '0.75' })}
            disabled={saveMut.isPending}
            className="bg-primary text-black px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {saveMut.isPending ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-semibold mb-3">Estimado del Mes</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div>
            <p className="text-xs text-slate-400">kWh acumulado (mes)</p>
            <p className="text-lg font-bold font-mono">{monthKwh.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Costo por kWh</p>
            <p className="text-lg font-bold font-mono">S/{parseFloat(currentCosto).toFixed(4)}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Costo estimado</p>
            <p className="text-lg font-bold font-mono text-yellow-400">S/{estimado.toFixed(2)}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ─── Manual Tab (Agua/Gas) ─── */
function ManualTab({ tipo, unidad, mes, queryClient }: { tipo: string; unidad: string; mes: string; queryClient: any }) {
  const { data: consumos, isLoading } = useQuery({
    queryKey: ['consumos', tipo, mes],
    queryFn: () => get<any[]>(`/api/consumos?tipo=${tipo}&mes=${mes}`),
  });

  const { data: resumen } = useQuery({
    queryKey: ['consumos-resumen', mes],
    queryFn: () => get<any[]>(`/api/consumos/resumen?mes=${mes}`),
  });

  return (
    <>
      <ResumenCards resumen={resumen} />
      <ManualForm tipo={tipo} unidad={unidad} queryClient={queryClient} mes={mes} />
      <Card>
        <h3 className="text-sm font-semibold mb-3">
          Historial — {tipo.charAt(0).toUpperCase() + tipo.slice(1)} ({mes})
        </h3>
        {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {!isLoading && (consumos || []).length === 0 && <p className="text-sm text-slate-500">Sin registros</p>}
        {(consumos || []).length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs border-b border-surface-light">
                  <th className="pb-2 pr-3">Fecha</th>
                  <th className="pb-2 pr-3 text-right">Valor</th>
                  <th className="pb-2 pr-3">Unidad</th>
                  <th className="pb-2 pr-3 text-right">Costo</th>
                  <th className="pb-2 pr-3">Fuente</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {(consumos || []).map((c: any) => (
                  <tr key={c.id} className="border-b border-surface-light/50 hover:bg-surface-light/30">
                    <td className="py-2 pr-3 text-slate-400 whitespace-nowrap">{c.fecha?.slice(0, 16)}</td>
                    <td className="py-2 pr-3 text-right font-mono">{c.valor.toFixed(2)}</td>
                    <td className="py-2 pr-3 text-slate-400">{c.unidad}</td>
                    <td className="py-2 pr-3 text-right font-mono">{c.costo ? `S/${c.costo.toFixed(2)}` : '-'}</td>
                    <td className="py-2 pr-3 text-slate-400">{c.source}</td>
                    <td className="py-2">
                      {c.source === 'manual' && (
                        <DeleteBtn onDelete={() => del(`/api/consumos/${c.id}`).then(() => {
                          queryClient.invalidateQueries({ queryKey: ['consumos', tipo, mes] });
                          queryClient.invalidateQueries({ queryKey: ['consumos-resumen', mes] });
                        })} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/* ─── Shared components ─── */

function LiveCard({ label, value, color = '' }: { label: string; value: string; color?: string }) {
  return (
    <Card>
      <p className="text-xs text-slate-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 font-mono ${color}`}>{value}</p>
    </Card>
  );
}

function ResumenCards({ resumen }: { resumen: any[] | undefined }) {
  if (!resumen || resumen.length === 0) return null;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {resumen.map((r: any) => {
        const icon = r.tipo === 'luz' ? '⚡' : r.tipo === 'agua' ? '💧' : '🔥';
        return (
          <Card key={r.tipo}>
            <div className="flex items-center gap-2 mb-1">
              <span>{icon}</span>
              <span className="text-xs text-slate-400 uppercase">{r.tipo}</span>
            </div>
            <p className="text-lg font-bold font-mono">{r.total.toFixed(2)}</p>
            <p className="text-xs text-slate-400">{r.lecturas} lecturas</p>
            {r.costo_total > 0 && (
              <p className="text-xs text-slate-400">Costo: S/{r.costo_total.toFixed(2)}</p>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function ManualForm({ tipo, unidad, queryClient, mes }: { tipo: string; unidad: string; queryClient: any; mes: string }) {
  const [valor, setValor] = useState('');
  const [fecha, setFecha] = useState(todayStr);
  const [costo, setCosto] = useState('');

  const mutation = useMutation({
    mutationFn: (data: any) => post('/api/consumos', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consumos', tipo, mes] });
      queryClient.invalidateQueries({ queryKey: ['consumos-resumen', mes] });
      setValor(''); setCosto('');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valor) return;
    mutation.mutate({ tipo, valor: parseFloat(valor), unidad, fecha, costo: costo ? parseFloat(costo) : null });
  };

  return (
    <Card>
      <h3 className="text-sm font-semibold mb-3">Registrar lectura</h3>
      <form onSubmit={handleSubmit} className="flex flex-wrap gap-2 items-end">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Fecha</label>
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)}
            className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Valor ({unidad})</label>
          <input type="number" step="0.01" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="0.00"
            className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm w-28 focus:outline-none focus:border-primary" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Costo (S/)</label>
          <input type="number" step="0.01" value={costo} onChange={(e) => setCosto(e.target.value)} placeholder="Opcional"
            className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm w-28 focus:outline-none focus:border-primary" />
        </div>
        <button type="submit" disabled={mutation.isPending}
          className="bg-primary text-black px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
          {mutation.isPending ? 'Guardando...' : 'Guardar'}
        </button>
      </form>
    </Card>
  );
}

function DeleteBtn({ onDelete }: { onDelete: () => void }) {
  return (
    <button onClick={onDelete} className="text-red-400 hover:text-red-300 text-xs" title="Eliminar">
      ✕
    </button>
  );
}
