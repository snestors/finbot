import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';
import ProgressBar from '../components/ui/ProgressBar';

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Tarjetas() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: tarjetas } = useQuery({ queryKey: ['tarjetas'], queryFn: () => get('/api/tarjetas') });

  const { data: estado } = useQuery({
    queryKey: ['estado-cuenta', selectedId],
    queryFn: () => get(`/api/tarjetas/${selectedId}/estado-cuenta`),
    enabled: !!selectedId,
  });

  const { data: cuotas } = useQuery({
    queryKey: ['cuotas-tarjeta', selectedId],
    queryFn: () => get(`/api/tarjetas/${selectedId}/cuotas`),
    enabled: !!selectedId,
  });

  const { data: pagosTarjeta } = useQuery({
    queryKey: ['pagos-tarjeta', selectedId],
    queryFn: () => get(`/api/tarjetas/${selectedId}/pagos`),
    enabled: !!selectedId,
  });

  const { data: periodos } = useQuery({
    queryKey: ['periodos-tarjeta', selectedId],
    queryFn: () => get(`/api/tarjetas/${selectedId}/periodos`),
    enabled: !!selectedId,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Tarjetas de Crédito</h2>

      <div className="grid sm:grid-cols-2 gap-3">
        {(tarjetas || []).map((t: any) => {
          const usado = t.saldo_usado || 0;
          const limite = t.limite_credito || 0;
          const disponible = limite - usado;
          return (
            <Card
              key={t.id}
              className={`cursor-pointer transition-all hover:border-primary ${selectedId === t.id ? 'border-primary ring-1 ring-primary/30' : ''}`}
            >
              <div onClick={() => setSelectedId(selectedId === t.id ? null : t.id)}>
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="font-medium">{t.nombre}</p>
                    <p className="text-xs text-slate-400">{t.banco} *{t.ultimos_4}</p>
                  </div>
                  <span className="text-xs bg-primary/15 text-primary px-2 py-0.5 rounded-full">{t.tipo}</span>
                </div>
                <ProgressBar value={usado} max={limite} />
                <div className="flex justify-between text-xs text-slate-400 mt-1.5">
                  <span>Usado: {fmt(usado)}</span>
                  <span>Disponible: {fmt(disponible)}</span>
                </div>
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>Corte: día {t.fecha_corte}</span>
                  <span>Pago: día {t.fecha_pago}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {selectedId && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-1">Estado de Cuenta</h3>
          {estado ? (
            <>
              <p className="text-xs text-slate-400 mb-3">
                Periodo: {estado.periodo?.inicio} al {estado.periodo?.fin} — Pago: {estado.periodo?.fecha_pago}
              </p>

              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="text-center">
                  <p className="text-xs text-slate-400">Consumos</p>
                  <p className="font-bold font-mono">{fmt(estado.total_gastos || 0)}</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-slate-400">Cuotas</p>
                  <p className="font-bold font-mono">{fmt(estado.total_cuotas || 0)}</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-slate-400">Total a Pagar</p>
                  <p className="font-bold font-mono text-accent">{fmt(estado.total || 0)}</p>
                </div>
              </div>

              {estado.gastos?.length > 0 ? (
                <>
                  <h4 className="text-xs font-semibold text-slate-400 mb-2">Consumos del periodo</h4>
                  <div className="space-y-1 mb-4">
                    {estado.gastos.map((g: any) => (
                      <div key={g.id} className="flex justify-between text-sm py-1 border-b border-surface-light/30">
                        <div className="flex gap-2">
                          <span className="text-slate-400 text-xs">{g.fecha?.slice(0, 10)}</span>
                          <span>{g.descripcion || g.categoria}</span>
                        </div>
                        <span className="font-mono">{fmt(g.monto)}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Sin consumos en este periodo</p>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500 mt-2">Cargando...</p>
          )}
        </Card>
      )}

      {selectedId && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Cuotas Pendientes</h3>
          {(!cuotas || cuotas.length === 0) && <p className="text-sm text-slate-500">Sin cuotas pendientes</p>}
          {cuotas && cuotas.length > 0 && (
            <div className="space-y-1">
              {cuotas.map((c: any) => (
                <div key={c.id} className="flex justify-between items-center text-sm py-1.5 border-b border-surface-light/30">
                  <div>
                    <span className="text-slate-400 text-xs mr-2">{c.fecha_cargo?.slice(0, 10)}</span>
                    <span>{c.descripcion || c.categoria}</span>
                    <span className="text-xs text-slate-500 ml-2">({c.numero_cuota}/{c.cuotas_total})</span>
                  </div>
                  <span className="font-mono">{fmt(c.monto_cuota)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {selectedId && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Pagos Realizados</h3>
          {(!pagosTarjeta || pagosTarjeta.length === 0) && <p className="text-sm text-slate-500">Sin pagos registrados</p>}
          {pagosTarjeta && pagosTarjeta.length > 0 && (
            <div className="space-y-1">
              {pagosTarjeta.map((p: any) => (
                <div key={p.id} className="flex justify-between items-center text-sm py-1.5 border-b border-surface-light/30">
                  <div className="flex gap-2">
                    <span className="text-slate-400 text-xs">{p.fecha?.slice(0, 10)}</span>
                    <span className="text-slate-300">{p.cuenta_nombre || 'Cuenta'}</span>
                    {p.descripcion && <span className="text-slate-500 text-xs">{p.descripcion}</span>}
                  </div>
                  <span className="font-mono text-green-400">{fmt(p.monto)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {selectedId && periodos && periodos.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Periodos de Facturación</h3>
          <div className="space-y-1">
            {periodos.map((p: any) => {
              const estadoColor = p.estado === 'pagado' ? 'text-green-400 bg-green-500/20'
                : p.estado === 'facturado' ? 'text-orange-400 bg-orange-500/20'
                : 'text-blue-400 bg-blue-500/20';
              return (
                <div key={p.id} className="flex justify-between items-center text-sm py-1.5 border-b border-surface-light/30">
                  <div className="flex gap-2 items-center">
                    <span className="text-slate-400 text-xs">{p.periodo}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${estadoColor}`}>{p.estado}</span>
                    <span className="text-slate-500 text-xs">{p.fecha_inicio?.slice(0, 10)} — {p.fecha_fin?.slice(0, 10)}</span>
                  </div>
                  <div className="flex gap-3 font-mono text-xs">
                    <span className="text-red-400">{fmt(p.total_facturado || 0)}</span>
                    <span className="text-green-400">{fmt(p.total_pagado || 0)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
