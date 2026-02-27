import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';
import ProgressBar from '../components/ui/ProgressBar';

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Deudas() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: deudas } = useQuery({ queryKey: ['deudas'], queryFn: () => get('/api/deudas') });

  const { data: pagos } = useQuery({
    queryKey: ['deuda-pagos', selectedId],
    queryFn: () => get(`/api/deudas/${selectedId}/pagos`),
    enabled: !!selectedId,
  });

  const activas = (deudas || []).filter((d: any) => d.activa);

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Deudas</h2>

      {activas.length === 0 && <p className="text-sm text-slate-500">Sin deudas activas</p>}

      <div className="space-y-3">
        {activas.map((d: any) => {
          const pagadas = d.cuotas_pagadas || 0;
          const total = d.cuotas_total || 0;
          return (
            <Card
              key={d.id}
              className={`cursor-pointer transition-all hover:border-primary ${selectedId === d.id ? 'border-primary ring-1 ring-primary/30' : ''}`}
            >
              <div onClick={() => setSelectedId(selectedId === d.id ? null : d.id)}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="font-medium">{d.nombre}</p>
                    <p className="text-xs text-slate-400">{d.entidad || 'Sin entidad'}</p>
                  </div>
                  <p className="text-lg font-bold font-mono">{fmt(d.saldo_actual)}</p>
                </div>
                {total > 0 && (
                  <>
                    <ProgressBar value={pagadas} max={total} color="bg-success" />
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
                      <span>{pagadas}/{total} cuotas</span>
                      {d.cuota_monto > 0 && <span>Cuota: {fmt(d.cuota_monto)}</span>}
                    </div>
                  </>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {selectedId && (() => {
        const deuda = activas.find((d: any) => d.id === selectedId);
        if (!deuda) return null;
        const pagado = (deuda.cuotas_total > 0 && deuda.cuota_monto > 0)
          ? deuda.cuotas_pagadas * deuda.cuota_monto : 0;
        return (
          <Card>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Detalle</h3>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mb-4">
              {deuda.entidad && <div><span className="text-slate-400">Entidad:</span> {deuda.entidad}</div>}
              <div><span className="text-slate-400">Saldo actual:</span> <span className="font-mono">{fmt(deuda.saldo_actual)}</span></div>
              {deuda.cuotas_total > 0 && (
                <div><span className="text-slate-400">Cuotas:</span> {deuda.cuotas_pagadas}/{deuda.cuotas_total}</div>
              )}
              {deuda.cuota_monto > 0 && (
                <div><span className="text-slate-400">Cuota mensual:</span> <span className="font-mono">{fmt(deuda.cuota_monto)}</span></div>
              )}
              {deuda.tasa_interes_mensual > 0 && (
                <div><span className="text-slate-400">Tasa:</span> {deuda.tasa_interes_mensual}% mensual</div>
              )}
              {deuda.fecha_pago && (
                <div><span className="text-slate-400">Día de pago:</span> {deuda.fecha_pago}</div>
              )}
              {pagado > 0 && (
                <div><span className="text-slate-400">Total pagado:</span> <span className="font-mono text-success">{fmt(pagado)}</span></div>
              )}
            </div>

            <h4 className="text-xs font-semibold text-slate-400 mb-2">Historial de Pagos</h4>
            {(!pagos || pagos.length === 0) && <p className="text-sm text-slate-500">Sin pagos registrados</p>}
            {pagos && pagos.length > 0 && (
              <div className="space-y-1">
                {pagos.map((p: any) => (
                  <div key={p.id} className="flex justify-between text-sm py-1.5 border-b border-surface-light/30">
                    <div className="flex gap-2">
                      <span className="text-slate-400">{p.fecha?.slice(0, 10)}</span>
                      {p.cuenta_nombre && <span className="text-slate-500 text-xs">desde {p.cuenta_nombre}</span>}
                    </div>
                    <span className="font-mono text-success">{fmt(p.monto)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        );
      })()}
    </div>
  );
}
