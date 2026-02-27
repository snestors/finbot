import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';
import ProgressBar from '../components/ui/ProgressBar';

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Cobros() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: cobros } = useQuery({ queryKey: ['cobros'], queryFn: () => get('/api/cobros?include_pagos=true') });

  const { data: pagos } = useQuery({
    queryKey: ['cobro-pagos', selectedId],
    queryFn: () => get(`/api/cobros/${selectedId}/pagos`),
    enabled: !!selectedId,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Cuentas por Cobrar</h2>

      {(!cobros || cobros.length === 0) && <p className="text-sm text-slate-500">Sin cobros pendientes</p>}

      <div className="space-y-3">
        {(cobros || []).map((c: any) => {
          const pagado = c.monto_total - c.saldo_pendiente;
          return (
            <Card
              key={c.id}
              className={`cursor-pointer transition-all hover:border-primary ${selectedId === c.id ? 'border-primary ring-1 ring-primary/30' : ''}`}
            >
              <div onClick={() => setSelectedId(selectedId === c.id ? null : c.id)}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="font-medium">{c.deudor}</p>
                    {c.concepto && <p className="text-xs text-slate-400">{c.concepto}</p>}
                  </div>
                  <div className="text-right">
                    <p className="font-bold font-mono">{fmt(c.saldo_pendiente)}</p>
                    <p className="text-xs text-slate-400">de {fmt(c.monto_total)}</p>
                  </div>
                </div>
                <ProgressBar value={pagado} max={c.monto_total} color="bg-success" />
                <p className="text-xs text-slate-400 mt-1">Pagado: {fmt(pagado)}</p>
              </div>
            </Card>
          );
        })}
      </div>

      {selectedId && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Historial de Pagos</h3>
          {(!pagos || pagos.length === 0) && <p className="text-sm text-slate-500">Sin pagos registrados</p>}
          {pagos && pagos.length > 0 && (
            <div className="space-y-1">
              {pagos.map((p: any) => (
                <div key={p.id} className="flex justify-between text-sm py-1.5 border-b border-surface-light/30">
                  <div className="flex gap-2">
                    <span className="text-slate-400">{p.fecha?.slice(0, 16)}</span>
                    {p.cuenta_nombre && <span className="text-slate-500 text-xs">a {p.cuenta_nombre}</span>}
                  </div>
                  <span className="font-mono text-success">{fmt(p.monto)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
