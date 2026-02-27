import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card, StatCard } from '../components/ui/Card';

export default function TipoCambio() {
  const { data: tc } = useQuery({ queryKey: ['tipo-cambio'], queryFn: () => get('/api/tipo-cambio') });
  const { data: historico } = useQuery({ queryKey: ['tc-historico'], queryFn: () => get('/api/tipo-cambio/historico?dias=30') });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Tipo de Cambio</h2>

      {tc?.sunat && (
        <div className="grid grid-cols-2 gap-3 max-w-lg">
          <StatCard label="Compra (USD→PEN)" value={`S/${tc.sunat.compra}`} icon="🔽" />
          <StatCard label="Venta (PEN→USD)" value={`S/${tc.sunat.venta}`} icon="🔼" />
        </div>
      )}

      <Card>
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Histórico (últimos 30 días)</h3>
        {(!historico || historico.length === 0) && <p className="text-sm text-slate-500">Sin datos históricos aún</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm max-w-lg">
            <thead>
              <tr className="text-left text-slate-400 text-xs border-b border-surface-light">
                <th className="pb-2">Fecha</th>
                <th className="pb-2 text-right">Compra</th>
                <th className="pb-2 text-right">Venta</th>
              </tr>
            </thead>
            <tbody>
              {(historico || []).map((r: any) => (
                <tr key={r.fecha} className="border-b border-surface-light/30">
                  <td className="py-1.5 text-slate-400">{r.fecha}</td>
                  <td className="py-1.5 text-right font-mono">S/{r.compra}</td>
                  <td className="py-1.5 text-right font-mono">S/{r.venta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
