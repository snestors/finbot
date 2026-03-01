import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';

export default function Config() {
  const { data: perfil } = useQuery({ queryKey: ['perfil'], queryFn: () => get('/api/perfil') });
  const { data: waStatus } = useQuery({ queryKey: ['wa-status'], queryFn: () => get('/api/whatsapp/status'), refetchInterval: 10000 });
  const { data: memoria } = useQuery({ queryKey: ['memoria'], queryFn: () => get('/api/memoria') });
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Configuración</h2>

      <Card>
        <h3 className="text-sm font-semibold text-slate-300 mb-2">Perfil</h3>
        <div className="text-sm space-y-1">
          <p><span className="text-slate-400">Nombre:</span> {perfil?.nombre || 'No configurado'}</p>
          <p><span className="text-slate-400">Moneda:</span> {perfil?.moneda_default || 'PEN'}</p>
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-semibold text-slate-300 mb-2">WhatsApp</h3>
        <p className="text-sm">
          Estado: <span className={(waStatus?.connected || waStatus?.ready) ? 'text-success' : 'text-danger'}>
            {(waStatus?.connected || waStatus?.ready) ? 'Conectado' : 'Desconectado'}
          </span>
        </p>
        {waStatus?.phone && <p className="text-sm text-slate-400">{waStatus.phone}</p>}
      </Card>

      {memoria && memoria.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-2">Memoria del Bot ({memoria.length})</h3>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {memoria.map((m: any) => (
              <div key={m.id} className="flex justify-between text-xs py-1 border-b border-surface-light/30">
                <span className="text-slate-400">[{m.categoria}] {m.clave}</span>
                <span>{m.valor}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

    </div>
  );
}
