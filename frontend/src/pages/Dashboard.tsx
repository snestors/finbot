import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { StatCard, Card } from '../components/ui/Card';
import ProgressBar from '../components/ui/ProgressBar';

function fmt(n: number) {
  return `S/${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Dashboard() {
  const { data: cuentas } = useQuery({ queryKey: ['cuentas'], queryFn: () => get('/api/cuentas') });
  const { data: categorias } = useQuery({ queryKey: ['categorias'], queryFn: () => get('/api/resumen/categorias') });
  const { data: deudas } = useQuery({ queryKey: ['deudas'], queryFn: () => get('/api/deudas') });
  const { data: tarjetas } = useQuery({ queryKey: ['tarjetas'], queryFn: () => get('/api/tarjetas') });
  const { data: presupuestos } = useQuery({ queryKey: ['presupuestos'], queryFn: () => get('/api/presupuestos') });
  const { data: tc } = useQuery({ queryKey: ['tipo-cambio'], queryFn: () => get('/api/tipo-cambio') });

  const totalBalance = (cuentas || []).reduce((s: number, c: any) => s + (c.saldo || 0), 0);
  const totalDeuda = (deudas || []).filter((d: any) => d.activa).reduce((s: number, d: any) => s + (d.saldo_actual || 0), 0);
  const totalUsadoTarjetas = (tarjetas || []).reduce((s: number, t: any) => s + (t.saldo_usado || 0), 0);
  const catEntries = categorias ? Object.entries(categorias).sort((a: any, b: any) => b[1] - a[1]) : [];
  const totalMes = catEntries.reduce((s, [, v]) => s + (v as number), 0);

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold">Dashboard</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Balance Total" value={fmt(totalBalance)} icon="🏦" />
        <StatCard label="Gastos del Mes" value={fmt(totalMes)} icon="💸" />
        <StatCard label="Deudas" value={fmt(totalDeuda)} sub={`${(deudas || []).filter((d: any) => d.activa).length} activas`} icon="📋" />
        <StatCard label="TDC Usado" value={fmt(totalUsadoTarjetas)} sub={`${(tarjetas || []).length} tarjetas`} icon="💳" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Gastos por Categoría</h3>
          {catEntries.length === 0 && <p className="text-sm text-slate-500">Sin gastos este mes</p>}
          <div className="space-y-2">
            {catEntries.map(([cat, monto]) => (
              <div key={cat} className="flex items-center justify-between text-sm">
                <span className="capitalize w-28 truncate">{cat}</span>
                <div className="flex-1 mx-3"><ProgressBar value={monto as number} max={totalMes} /></div>
                <span className="text-slate-300 w-24 text-right">{fmt(monto as number)}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Presupuestos</h3>
          {(!presupuestos || presupuestos.length === 0) && <p className="text-sm text-slate-500">Sin presupuestos configurados</p>}
          <div className="space-y-3">
            {(presupuestos || []).map((p: any) => {
              const gastado = categorias?.[p.categoria] || 0;
              const pct = p.limite_mensual > 0 ? (gastado / p.limite_mensual * 100) : 0;
              return (
                <div key={p.id}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="capitalize">{p.categoria}</span>
                    <span className="text-slate-400">{fmt(gastado)} / {fmt(p.limite_mensual)} ({pct.toFixed(0)}%)</span>
                  </div>
                  <ProgressBar value={gastado} max={p.limite_mensual} />
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {tc?.sunat && (
        <Card className="max-w-sm">
          <h3 className="text-sm font-semibold text-slate-300 mb-2">Tipo de Cambio SUNAT</h3>
          <div className="flex gap-6 text-sm">
            <div><span className="text-slate-400">Compra:</span> <span className="font-mono font-bold">S/{tc.sunat.compra}</span></div>
            <div><span className="text-slate-400">Venta:</span> <span className="font-mono font-bold">S/{tc.sunat.venta}</span></div>
          </div>
        </Card>
      )}
    </div>
  );
}
