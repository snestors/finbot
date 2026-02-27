import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const now = new Date();
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

export default function Gastos() {
  const [mes, setMes] = useState(currentMonth);
  const [cuentaId, setCuentaId] = useState('');
  const [tarjetaId, setTarjetaId] = useState('');

  const params = new URLSearchParams();
  if (mes) params.set('mes', mes);
  if (cuentaId) params.set('cuenta_id', cuentaId);
  if (tarjetaId) params.set('tarjeta_id', tarjetaId);

  const { data: gastos, isLoading } = useQuery({
    queryKey: ['gastos', mes, cuentaId, tarjetaId],
    queryFn: () => get(`/api/gastos?${params}`),
  });
  const { data: cuentas } = useQuery({ queryKey: ['cuentas'], queryFn: () => get('/api/cuentas') });
  const { data: tarjetas } = useQuery({ queryKey: ['tarjetas'], queryFn: () => get('/api/tarjetas') });

  const total = (gastos || []).reduce((s: number, g: any) => s + g.monto, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-bold">Gastos</h2>
        <span className="text-sm text-slate-400">{(gastos || []).length} gastos — Total: {fmt(total)}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <input type="month" value={mes} onChange={e => setMes(e.target.value)}
          className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary" />
        <select value={cuentaId} onChange={e => { setCuentaId(e.target.value); setTarjetaId(''); }}
          className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm">
          <option value="">Todas las cuentas</option>
          {(cuentas || []).map((c: any) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <select value={tarjetaId} onChange={e => { setTarjetaId(e.target.value); setCuentaId(''); }}
          className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm">
          <option value="">Todas las tarjetas</option>
          {(tarjetas || []).map((t: any) => <option key={t.id} value={t.id}>{t.nombre} *{t.ultimos_4}</option>)}
        </select>
      </div>

      <Card>
        {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {!isLoading && (gastos || []).length === 0 && <p className="text-sm text-slate-500">Sin gastos</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 text-xs border-b border-surface-light">
                <th className="pb-2 pr-3">Fecha</th>
                <th className="pb-2 pr-3">Categoría</th>
                <th className="pb-2 pr-3 text-right">Monto</th>
                <th className="pb-2 pr-3">Descripción</th>
                <th className="pb-2 pr-3">Método</th>
                <th className="pb-2">Cuotas</th>
              </tr>
            </thead>
            <tbody>
              {(gastos || []).map((g: any) => (
                <tr key={g.id} className="border-b border-surface-light/50 hover:bg-surface-light/30">
                  <td className="py-2 pr-3 text-slate-400 whitespace-nowrap">{g.fecha?.slice(0, 10)}</td>
                  <td className="py-2 pr-3 capitalize">{g.categoria}</td>
                  <td className="py-2 pr-3 text-right font-mono">{fmt(g.monto)}</td>
                  <td className="py-2 pr-3 truncate max-w-48">{g.descripcion}{g.comercio ? ` (${g.comercio})` : ''}</td>
                  <td className="py-2 pr-3 text-slate-400">{g.metodo_pago || '-'}</td>
                  <td className="py-2">{g.cuotas > 1 ? `${g.cuotas}x` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
