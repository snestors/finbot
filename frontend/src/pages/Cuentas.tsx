import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';

const currencySymbol: Record<string, string> = { PEN: 'S/', USD: '$', EUR: '€' };

function fmt(n: number, moneda = 'PEN') {
  const sym = currencySymbol[moneda] || moneda + ' ';
  return `${sym}${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const tipoLabels: Record<string, string> = {
  gasto: 'Gasto',
  ingreso: 'Ingreso',
  transferencia: 'Transferencia',
  pago_tarjeta: 'Pago TDC',
  pago_deuda: 'Pago Deuda',
  pago_cobro: 'Cobro Recibido',
};

const tipoColors: Record<string, string> = {
  gasto: 'text-red-400',
  ingreso: 'text-green-400',
  transferencia: 'text-blue-400',
  pago_tarjeta: 'text-orange-400',
  pago_deuda: 'text-orange-400',
  pago_cobro: 'text-green-400',
};

function movDesc(m: any, cuentaId: number) {
  const tipo = m.tipo;
  if (tipo === 'gasto') return m.descripcion || m.categoria || 'Gasto';
  if (tipo === 'ingreso') return m.descripcion || m.fuente || 'Ingreso';
  if (tipo === 'transferencia') {
    if (m.cuenta_id === cuentaId) return `→ ${m.cuenta_destino || 'Otra cuenta'}`;
    return `← ${m.cuenta_origen || 'Otra cuenta'}`;
  }
  if (tipo === 'pago_tarjeta') return m.tarjeta_nombre || 'Pago tarjeta';
  if (tipo === 'pago_deuda') return 'Pago deuda';
  if (tipo === 'pago_cobro') return 'Cobro recibido';
  return tipo;
}

function movMonto(m: any, cuentaId: number) {
  const tipo = m.tipo;
  const monto = m.monto_cuenta || m.monto || 0;
  if (tipo === 'ingreso' || tipo === 'pago_cobro') return monto;
  if (tipo === 'transferencia') {
    if (m.cuenta_destino_id === cuentaId) return m.monto_destino || monto;
    return -monto;
  }
  return -monto;
}

export default function Cuentas() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: cuentas } = useQuery({ queryKey: ['cuentas'], queryFn: () => get('/api/cuentas') });
  const { data: movimientos } = useQuery({
    queryKey: ['cuenta-movimientos', selectedId],
    queryFn: () => get(`/api/cuentas/${selectedId}/movimientos`),
    enabled: !!selectedId,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Cuentas</h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {(cuentas || []).map((c: any) => {
          const metodos: string[] = c.metodos_pago || [];
          return (
            <Card
              key={c.id}
              className={`cursor-pointer transition-all hover:border-primary ${selectedId === c.id ? 'border-primary ring-1 ring-primary/30' : ''}`}
            >
              <div onClick={() => setSelectedId(selectedId === c.id ? null : c.id)}>
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium">{c.nombre}</p>
                    <p className="text-xs text-slate-400 capitalize">{c.tipo} · {c.moneda || 'PEN'}</p>
                  </div>
                  <p className="text-lg font-bold font-mono">{fmt(c.saldo, c.moneda)}</p>
                </div>
                {metodos.length > 0 && (
                  <div className="flex gap-1.5 mt-2 flex-wrap">
                    {metodos.map((m: string) => (
                      <span key={m} className="text-[10px] bg-primary/15 text-primary px-1.5 py-0.5 rounded-full capitalize">{m}</span>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {selectedId && (() => {
        const cuenta = (cuentas || []).find((c: any) => c.id === selectedId);
        if (!cuenta) return null;
        const movs = movimientos || [];
        return (
          <Card>
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-sm font-semibold text-slate-300">
                Movimientos — {cuenta.nombre}
              </h3>
              <span className="text-xs text-slate-400">
                {movs.length} movimientos
              </span>
            </div>
            {movs.length === 0 && <p className="text-sm text-slate-500">Sin movimientos registrados</p>}
            {movs.length > 0 && (
              <div className="space-y-1">
                {movs.slice(0, 50).map((m: any, i: number) => {
                  const monto = movMonto(m, selectedId);
                  const isPositive = monto >= 0;
                  return (
                    <div key={`${m.tipo}-${m.id || i}`} className="flex justify-between text-sm py-1.5 border-b border-surface-light/30">
                      <div className="flex gap-2 min-w-0 items-center">
                        <span className="text-slate-400 text-xs w-20 shrink-0">{m.fecha?.slice(0, 10)}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${tipoColors[m.tipo] || 'text-slate-400'} bg-surface-light/50`}>
                          {tipoLabels[m.tipo] || m.tipo}
                        </span>
                        <span className="text-slate-300 truncate">{movDesc(m, selectedId)}</span>
                      </div>
                      <span className={`font-mono shrink-0 ml-2 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                        {isPositive ? '+' : ''}{fmt(Math.abs(monto), cuenta.moneda)}
                      </span>
                    </div>
                  );
                })}
                {movs.length > 50 && <p className="text-xs text-slate-500 pt-1">...y {movs.length - 50} más</p>}
              </div>
            )}
          </Card>
        );
      })()}
    </div>
  );
}
