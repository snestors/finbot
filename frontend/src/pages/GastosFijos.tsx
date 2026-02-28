import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { get, post, del } from '../api/client';
import { Card } from '../components/ui/Card';

const FREQ_LABELS: Record<string, string> = {
  mensual: 'Mensual',
  semanal: 'Semanal',
  quincenal: 'Quincenal',
  anual: 'Anual',
};

const DIAS_SEMANA = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function diaLabel(gf: any) {
  if (gf.frecuencia === 'semanal') return DIAS_SEMANA[gf.dia] || `dia ${gf.dia}`;
  if (gf.frecuencia === 'anual') return `${gf.dia}/${gf.mes || '?'}`;
  return `dia ${gf.dia}`;
}

export default function GastosFijos() {
  const qc = useQueryClient();
  const { data: gastosFijos, isLoading } = useQuery({
    queryKey: ['gastos-fijos'],
    queryFn: () => get('/api/gastos-fijos?solo_activos=false'),
  });

  const toggleMut = useMutation({
    mutationFn: (id: number) => post(`/api/gastos-fijos/${id}/toggle`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gastos-fijos'] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => del(`/api/gastos-fijos/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gastos-fijos'] }),
  });

  const activos = (gastosFijos || []).filter((gf: any) => gf.activo);
  const totalMensual = activos.reduce((sum: number, gf: any) => {
    if (gf.frecuencia === 'mensual') return sum + gf.monto;
    if (gf.frecuencia === 'quincenal') return sum + gf.monto * 2;
    if (gf.frecuencia === 'semanal') return sum + gf.monto * 4.33;
    if (gf.frecuencia === 'anual') return sum + gf.monto / 12;
    return sum;
  }, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Gastos Fijos</h2>
        {activos.length > 0 && (
          <span className="text-sm text-slate-400">
            Est. mensual: <span className="font-mono text-primary font-medium">{fmt(totalMensual)}</span>
          </span>
        )}
      </div>

      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {!isLoading && (!gastosFijos || gastosFijos.length === 0) && (
        <p className="text-sm text-slate-500">
          No hay gastos fijos. Dile al chat: "agrega alquiler 1500 como gasto fijo mensual dia 1"
        </p>
      )}

      <div className="space-y-3">
        {(gastosFijos || []).map((gf: any) => (
          <Card key={gf.id} className={!gf.activo ? 'opacity-50' : ''}>
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium truncate">{gf.nombre}</p>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-surface-light text-slate-400">
                    {FREQ_LABELS[gf.frecuencia] || gf.frecuencia}
                  </span>
                  <span className="text-xs text-slate-500">{diaLabel(gf)}</span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                  <span>{gf.categoria}</span>
                  {gf.comercio && <span>{gf.comercio}</span>}
                  {gf.metodo_pago && <span>{gf.metodo_pago}</span>}
                  {gf.ultimo_registro && (
                    <span>ultimo: {gf.ultimo_registro.slice(0, 10)}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 ml-3 shrink-0">
                <span className="font-mono font-bold text-right">{fmt(gf.monto)}</span>
                <button
                  onClick={() => toggleMut.mutate(gf.id)}
                  className={`w-10 h-5 rounded-full relative transition-colors ${gf.activo ? 'bg-primary' : 'bg-surface-light'}`}
                  title={gf.activo ? 'Pausar' : 'Activar'}
                >
                  <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${gf.activo ? 'left-5' : 'left-0.5'}`} />
                </button>
                <button
                  onClick={() => { if (confirm('Eliminar este gasto fijo?')) deleteMut.mutate(gf.id); }}
                  className="text-red-400 hover:text-red-300 text-sm px-1"
                  title="Eliminar"
                >
                  x
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
