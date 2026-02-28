import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '../api/client';
import { Card } from '../components/ui/Card';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';

const now = new Date();
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function Analytics() {
  const [mes, setMes] = useState(currentMonth);

  const { data: summary } = useQuery({
    queryKey: ['llm-usage-summary', mes],
    queryFn: () => get(`/api/llm-usage/summary?mes=${mes}`),
    refetchInterval: 30_000,
  });

  const { data: daily } = useQuery({
    queryKey: ['llm-usage-daily', mes],
    queryFn: () => get(`/api/llm-usage/daily?mes=${mes}`),
  });

  const { data: byCaller } = useQuery({
    queryKey: ['llm-usage-by-caller', mes],
    queryFn: () => get(`/api/llm-usage/by-caller?mes=${mes}`),
  });

  const { data: recent } = useQuery({
    queryKey: ['llm-usage-recent'],
    queryFn: () => get('/api/llm-usage/recent?limit=30'),
    refetchInterval: 30_000,
  });

  // Stat cards
  const todayCalls = (summary?.today || []).reduce((s: number, r: any) => s + r.calls, 0);
  const todayTokens = (summary?.today || []).reduce(
    (s: number, r: any) => s + r.total_input + r.total_output, 0
  );
  const monthSonnet = (summary?.month || []).find((r: any) => r.model === 'sonnet');
  const monthGemini = (summary?.month || []).find((r: any) => r.model === 'gemini');
  const geminiCost = summary?.gemini_cost ?? 0;

  // Chart data: pivot daily rows into {fecha, sonnet_tokens, gemini_tokens}
  const chartData = useMemo(() => {
    if (!daily) return [];
    const map: Record<string, any> = {};
    for (const row of daily) {
      const day = row.fecha.slice(5); // "MM-DD"
      if (!map[day]) map[day] = { day, sonnet: 0, gemini: 0 };
      const total = (row.total_input || 0) + (row.total_output || 0);
      if (row.model === 'sonnet') map[day].sonnet += total;
      else if (row.model === 'gemini') map[day].gemini += total;
    }
    return Object.values(map);
  }, [daily]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-bold">Analytics LLM</h2>
        <input
          type="month"
          value={mes}
          onChange={(e) => setMes(e.target.value)}
          className="bg-surface border border-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-primary"
        />
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="text-xs text-slate-400">Llamadas hoy</div>
          <div className="text-2xl font-bold text-primary">{todayCalls}</div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-slate-400">Tokens hoy</div>
          <div className="text-2xl font-bold text-blue-400">{fmtTokens(todayTokens)}</div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-slate-400">Costo Gemini ({mes})</div>
          <div className="text-2xl font-bold text-green-400">${geminiCost.toFixed(4)}</div>
          <div className="text-[10px] text-slate-500">
            {monthGemini ? `${monthGemini.calls} calls` : 'sin uso'}
          </div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-slate-400">Sonnet ({mes})</div>
          <div className="text-2xl font-bold text-indigo-400">
            {monthSonnet ? fmtTokens(monthSonnet.total_input + monthSonnet.total_output) : '0'}
          </div>
          <div className="text-[10px] text-slate-500">
            {monthSonnet ? `${monthSonnet.calls} calls` : 'sin uso'}
          </div>
        </Card>
      </div>

      {/* Daily Chart */}
      {chartData.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-3">Tokens por dia</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={fmtTokens} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                formatter={(v: any, name: any) => [fmtTokens(v ?? 0), name ?? '']}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="sonnet" stackId="a" fill="#818cf8" radius={[0, 0, 0, 0]} />
              <Bar dataKey="gemini" stackId="a" fill="#34d399" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* By Caller Table */}
      {byCaller && byCaller.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-3">Por agente</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs border-b border-surface-light">
                  <th className="pb-2 pr-4">Caller</th>
                  <th className="pb-2 pr-4">Modelo</th>
                  <th className="pb-2 pr-4 text-right">Calls</th>
                  <th className="pb-2 pr-4 text-right">Input</th>
                  <th className="pb-2 text-right">Output</th>
                </tr>
              </thead>
              <tbody>
                {byCaller.map((row: any, i: number) => (
                  <tr key={i} className="border-b border-surface-light/50">
                    <td className="py-1.5 pr-4 font-medium">{row.caller || '(unknown)'}</td>
                    <td className="py-1.5 pr-4">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        row.model === 'sonnet' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-green-500/20 text-green-400'
                      }`}>
                        {row.model}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 text-right font-mono text-xs">{row.calls}</td>
                    <td className="py-1.5 pr-4 text-right font-mono text-xs">{fmtTokens(row.total_input)}</td>
                    <td className="py-1.5 text-right font-mono text-xs">{fmtTokens(row.total_output)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Recent Calls Table */}
      {recent && recent.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-3">Llamadas recientes</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-xs border-b border-surface-light">
                  <th className="pb-2 pr-4">Hora</th>
                  <th className="pb-2 pr-4">Modelo</th>
                  <th className="pb-2 pr-4">Caller</th>
                  <th className="pb-2 pr-4 text-right">Input</th>
                  <th className="pb-2 text-right">Output</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((row: any) => (
                  <tr key={row.id} className="border-b border-surface-light/50">
                    <td className="py-1.5 pr-4 text-xs text-slate-400 font-mono">
                      {row.created_at?.slice(11, 19) || '--'}
                    </td>
                    <td className="py-1.5 pr-4">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        row.model === 'sonnet' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-green-500/20 text-green-400'
                      }`}>
                        {row.model}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 text-xs">{row.caller || '--'}</td>
                    <td className="py-1.5 pr-4 text-right font-mono text-xs">{fmtTokens(row.input_tokens)}</td>
                    <td className="py-1.5 text-right font-mono text-xs">{fmtTokens(row.output_tokens)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
