import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';
import ProgressBar from '../components/ui/ProgressBar';

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Presupuestos() {
  const { data: presupuestos } = useQuery({ queryKey: ['presupuestos'], queryFn: () => get('/api/presupuestos') });
  const { data: categorias } = useQuery({ queryKey: ['categorias'], queryFn: () => get('/api/resumen/categorias') });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Presupuestos</h2>

      {(!presupuestos || presupuestos.length === 0) && (
        <p className="text-sm text-slate-500">Sin presupuestos configurados. Usa el chat para crear uno.</p>
      )}

      <div className="space-y-3">
        {(presupuestos || []).map((p: any) => {
          const gastado = categorias?.[p.categoria] || 0;
          const pct = p.limite_mensual > 0 ? (gastado / p.limite_mensual * 100) : 0;
          const restante = p.limite_mensual - gastado;
          return (
            <Card key={p.id}>
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="font-medium capitalize">{p.categoria}</p>
                  <p className="text-xs text-slate-400">Alerta al {p.alerta_porcentaje}%</p>
                </div>
                <div className="text-right">
                  <p className={`text-lg font-bold font-mono ${pct > 100 ? 'text-danger' : pct > 80 ? 'text-accent' : ''}`}>
                    {pct.toFixed(0)}%
                  </p>
                </div>
              </div>
              <ProgressBar value={gastado} max={p.limite_mensual} />
              <div className="flex justify-between text-xs text-slate-400 mt-1.5">
                <span>Gastado: {fmt(gastado)}</span>
                <span>Límite: {fmt(p.limite_mensual)}</span>
                <span className={restante < 0 ? 'text-danger' : 'text-success'}>
                  {restante >= 0 ? `Queda: ${fmt(restante)}` : `Exceso: ${fmt(-restante)}`}
                </span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
