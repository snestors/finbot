import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { get, post } from '../api/client';
import { Card, StatCard } from '../components/ui/Card';

interface Trade {
  id: number;
  pair: string;
  side: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  reason: string;
  strategy: string;
  score: number;
  leverage: number;
  hold_seconds: number;
  paper: boolean;
  timestamp: string;
}

interface TradingStatus {
  state: {
    has_position: boolean;
    position: any;
    paused: boolean;
    paper_mode: boolean;
    last_run: number;
    consecutive_losses: number;
    globally_cooled_down: boolean;
  };
  brain: {
    total_trades: number;
    wins: number;
    losses: number;
    win_rate: number;
    total_pnl: number;
    streak: number;
    evolve_count: number;
    killed_pairs: string[];
    killed_strategies: string[];
    params: Record<string, number>;
  };
  journal_stats: {
    total: number;
    wins: number;
    losses: number;
    win_rate: number;
    total_pnl: number;
    avg_pnl: number;
    best: number;
    worst: number;
  };
  recent_trades: Trade[];
  balance: number;
  config: {
    pairs: string[];
    strategies: string[];
    [key: string]: any;
  };
  activity?: {
    time: string;
    event: string;
    detail: string;
    reason?: string;
    score?: number;
    result?: string;
    filter?: string;
    [key: string]: any;
  }[];
  error?: string;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatTime(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString('es-PE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function PnlBadge({ pnl }: { pnl: number }) {
  const color = pnl >= 0 ? 'text-green-400' : 'text-red-400';
  const sign = pnl >= 0 ? '+' : '';
  return <span className={`font-mono font-bold ${color}`}>{sign}${pnl.toFixed(4)}</span>;
}

function ReasonBadge({ reason }: { reason: string }) {
  const colors: Record<string, string> = {
    take_profit: 'bg-green-500/20 text-green-400',
    stop_loss: 'bg-red-500/20 text-red-400',
    trailing_stop: 'bg-yellow-500/20 text-yellow-400',
    sentinel_close: 'bg-purple-500/20 text-purple-400',
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${colors[reason] || 'bg-slate-500/20 text-slate-400'}`}>
      {reason.replace('_', ' ').toUpperCase()}
    </span>
  );
}

function SideBadge({ side }: { side: string }) {
  const color = side === 'long' ? 'text-green-400' : 'text-red-400';
  return <span className={`font-bold uppercase ${color}`}>{side}</span>;
}

export default function Trading() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<TradingStatus>({
    queryKey: ['trading-status'],
    queryFn: () => get('/api/trading/status'),
    refetchInterval: 5000,
  });

  const pauseMut = useMutation({
    mutationFn: () => post('/api/trading/pause', {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['trading-status'] }),
  });

  const resumeMut = useMutation({
    mutationFn: () => post('/api/trading/resume', {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['trading-status'] }),
  });

  if (isLoading) return <div className="p-6 text-slate-400">Cargando...</div>;
  if (!data || data.error) return <div className="p-6 text-red-400">Error: {data?.error || 'No data'}</div>;

  const { state, brain, journal_stats, recent_trades, balance, config } = data;
  const activity = (data as any).activity || [];
  const pos = state.position;

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Trading Bot</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`px-2 py-0.5 rounded text-xs font-bold ${state.paper_mode ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'}`}>
              {state.paper_mode ? 'PAPER' : 'REAL'}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-bold ${state.paused ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
              {state.paused ? 'PAUSADO' : 'ACTIVO'}
            </span>
            {state.globally_cooled_down && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-500/20 text-orange-400">COOLDOWN</span>
            )}
          </div>
        </div>
        <button
          onClick={() => state.paused ? resumeMut.mutate() : pauseMut.mutate()}
          className={`px-4 py-2 rounded-lg font-medium text-sm ${
            state.paused
              ? 'bg-green-600 hover:bg-green-500 text-white'
              : 'bg-red-600 hover:bg-red-500 text-white'
          }`}
        >
          {state.paused ? 'Reanudar' : 'Pausar'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Balance" value={`$${balance.toFixed(2)}`} icon="💰" />
        <StatCard label="PnL Total" value={`$${journal_stats.total_pnl.toFixed(2)}`} sub={`${journal_stats.total} trades`} icon={journal_stats.total_pnl >= 0 ? '📈' : '📉'} />
        <StatCard label="Win Rate" value={`${journal_stats.win_rate.toFixed(0)}%`} sub={`${journal_stats.wins}W / ${journal_stats.losses}L`} icon="🎯" />
        <StatCard label="Streak" value={`${brain.streak > 0 ? '+' : ''}${brain.streak}`} sub={`${brain.evolve_count} evoluciones`} icon={brain.streak >= 0 ? '🔥' : '❄️'} />
      </div>

      {/* Position */}
      {pos && (
        <Card>
          <h2 className="text-sm font-bold text-slate-400 uppercase mb-3">Posicion Abierta</h2>
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <span className="text-lg font-bold">{pos.pair?.split('/')[0]}</span>
              <span className="text-slate-400 text-sm ml-1">/USDT</span>
            </div>
            <SideBadge side={pos.side} />
            <div className="text-sm">
              <span className="text-slate-400">Entry:</span>{' '}
              <span className="font-mono">{pos.entry_price}</span>
            </div>
            <div className="text-sm">
              <span className="text-slate-400">SL:</span>{' '}
              <span className="font-mono text-red-400">{pos.sl}</span>
            </div>
            <div className="text-sm">
              <span className="text-slate-400">TP:</span>{' '}
              <span className="font-mono text-green-400">{pos.tp}</span>
            </div>
            <div className="text-sm">
              <span className="text-slate-400">Leverage:</span>{' '}
              <span className="font-mono">{pos.leverage}x</span>
            </div>
            <div className="text-sm">
              <span className="text-slate-400">Strategy:</span>{' '}
              <span>{pos.strategy}</span>
            </div>
            {pos.trailing_active && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-cyan-500/20 text-cyan-400">TRAILING</span>
            )}
          </div>
        </Card>
      )}

      {!pos && !state.has_position && (
        <Card>
          <p className="text-slate-400 text-sm">Sin posicion abierta — escaneando senales cada minuto</p>
        </Card>
      )}

      {/* Activity Feed */}
      <Card>
        <h2 className="text-sm font-bold text-slate-400 uppercase mb-3">Actividad en Tiempo Real</h2>
        <div className="max-h-64 overflow-y-auto space-y-1 text-xs font-mono">
          {activity.length === 0 ? (
            <p className="text-slate-500">Esperando actividad...</p>
          ) : (
            [...activity].reverse().map((a: any, i: number) => {
              const eventColors: Record<string, string> = {
                scan: 'text-slate-400',
                open: 'text-green-400',
                close: 'text-yellow-400',
                blocked: 'text-orange-400',
                sentinel: 'text-purple-400',
                monitor: 'text-slate-500',
              };
              const eventIcons: Record<string, string> = {
                scan: '🔍',
                open: '🟢',
                close: '🔴',
                blocked: '🚫',
                sentinel: '🛡️',
                monitor: '📊',
              };
              const color = eventColors[a.event] || 'text-slate-400';
              const icon = eventIcons[a.event] || '•';
              return (
                <div key={i} className={`flex gap-2 ${color} ${a.event === 'monitor' ? 'opacity-50' : ''}`}>
                  <span className="text-slate-600 w-16 shrink-0">{a.time}</span>
                  <span className="w-5 shrink-0">{icon}</span>
                  <span className="truncate">{a.detail}</span>
                  {a.reason && a.event !== 'scan' && a.event !== 'monitor' && (
                    <span className="text-slate-600 truncate ml-auto">— {a.reason}</span>
                  )}
                </div>
              );
            })
          )}
        </div>
      </Card>

      {/* Recent Trades */}
      <Card>
        <h2 className="text-sm font-bold text-slate-400 uppercase mb-3">Ultimos Trades</h2>
        {recent_trades.length === 0 ? (
          <p className="text-slate-500 text-sm">No hay trades aun</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 text-xs uppercase border-b border-surface-light">
                  <th className="text-left py-2 pr-3">Par</th>
                  <th className="text-left py-2 pr-3">Side</th>
                  <th className="text-right py-2 pr-3">Entry</th>
                  <th className="text-right py-2 pr-3">Exit</th>
                  <th className="text-right py-2 pr-3">PnL</th>
                  <th className="text-left py-2 pr-3">Razon</th>
                  <th className="text-left py-2 pr-3">Strategy</th>
                  <th className="text-right py-2 pr-3">Hold</th>
                  <th className="text-right py-2">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {[...recent_trades].reverse().map((t) => (
                  <tr key={t.id} className="border-b border-surface-light/50 hover:bg-surface-light/30">
                    <td className="py-2 pr-3 font-medium">{t.pair.split('/')[0]}</td>
                    <td className="py-2 pr-3"><SideBadge side={t.side} /></td>
                    <td className="py-2 pr-3 text-right font-mono text-xs">{t.entry_price}</td>
                    <td className="py-2 pr-3 text-right font-mono text-xs">{t.exit_price}</td>
                    <td className="py-2 pr-3 text-right"><PnlBadge pnl={t.pnl} /></td>
                    <td className="py-2 pr-3"><ReasonBadge reason={t.reason} /></td>
                    <td className="py-2 pr-3 text-xs text-slate-400">{t.strategy.replace('_', ' ')}</td>
                    <td className="py-2 pr-3 text-right font-mono text-xs">{formatDuration(t.hold_seconds)}</td>
                    <td className="py-2 text-right text-xs text-slate-400">{formatTime(t.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Brain & Config */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <h2 className="text-sm font-bold text-slate-400 uppercase mb-3">Brain</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Leverage</span>
              <span className="font-mono">{brain.params.leverage_default}x</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Stop Loss</span>
              <span className="font-mono">{brain.params.sl_atr_mult}x ATR</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Take Profit</span>
              <span className="font-mono">{brain.params.tp_atr_mult}x ATR</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Min Score</span>
              <span className="font-mono">{brain.params.min_score}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Trailing Trigger</span>
              <span className="font-mono">{brain.params.trailing_trigger_pct}%</span>
            </div>
            {brain.killed_pairs.length > 0 && (
              <div className="mt-2 pt-2 border-t border-surface-light">
                <span className="text-red-400 text-xs">Pares eliminados: {brain.killed_pairs.join(', ')}</span>
              </div>
            )}
            {brain.killed_strategies.length > 0 && (
              <div>
                <span className="text-red-400 text-xs">Estrategias eliminadas: {brain.killed_strategies.join(', ')}</span>
              </div>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="text-sm font-bold text-slate-400 uppercase mb-3">Config</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Pares</span>
              <span className="font-mono text-xs">{config.pairs.map(p => p.split('/')[0]).join(', ')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Estrategias</span>
              <span className="text-xs">{config.strategies.join(', ')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Timeframe</span>
              <span className="font-mono">{config.candle_tf}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Margin</span>
              <span className="font-mono">{(config.margin_pct * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Cooldown</span>
              <span className="font-mono">{config.cooldown_candles} candles</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Perdidas seguidas</span>
              <span className="font-mono">{state.consecutive_losses}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Stats extras */}
      <Card>
        <h2 className="text-sm font-bold text-slate-400 uppercase mb-3">Estadisticas</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-slate-400 block text-xs">Mejor Trade</span>
            <span className="font-mono text-green-400 font-bold">{journal_stats.best > 0 ? `+$${journal_stats.best.toFixed(4)}` : '--'}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-xs">Peor Trade</span>
            <span className="font-mono text-red-400 font-bold">{journal_stats.worst < 0 ? `-$${Math.abs(journal_stats.worst).toFixed(4)}` : '--'}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-xs">PnL Promedio</span>
            <span className={`font-mono font-bold ${journal_stats.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>${journal_stats.avg_pnl.toFixed(4)}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-xs">Evoluciones Darwin</span>
            <span className="font-mono">{brain.evolve_count}</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
