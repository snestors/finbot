import { useEffect, useRef, useState, useCallback } from 'react';

const LEVEL_COLORS: Record<string, string> = {
  ERROR: 'text-red-400',
  WARNING: 'text-yellow-400',
  INFO: 'text-green-400',
};

function getLineColor(line: string): string {
  for (const [level, color] of Object.entries(LEVEL_COLORS)) {
    if (line.includes(level)) return color;
  }
  return 'text-slate-400';
}

function formatElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}m${s.toString().padStart(2, '0')}s`;
}

const MAX_LINES = 1000;

export default function Logs() {
  const [lines, setLines] = useState<string[]>([]);
  const [filter, setFilter] = useState('');
  const [debouncedFilter, setDebouncedFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [connected, setConnected] = useState(false);
  const [lastActivity, setLastActivity] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [lps, setLps] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const lineCountRef = useRef(0);
  const lpsIntervalRef = useRef<number | null>(null);
  const lpsCountRef = useRef(0);

  // Debounce filter
  useEffect(() => {
    const t = setTimeout(() => setDebouncedFilter(filter), 300);
    return () => clearTimeout(t);
  }, [filter]);

  // SSE connection
  useEffect(() => {
    setLines([]);
    lineCountRef.current = 0;
    const params = debouncedFilter ? `?filter=${encodeURIComponent(debouncedFilter)}` : '';
    const es = new EventSource(`/api/logs/stream${params}`);
    es.onopen = () => {
      setConnected(true);
      setLastActivity(Date.now());
    };
    es.onmessage = (e) => {
      setLastActivity(Date.now());
      lpsCountRef.current++;
      setLines((prev) => {
        const next = [...prev, e.data];
        lineCountRef.current = next.length;
        return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
      });
    };
    es.onerror = () => setConnected(false);
    return () => es.close();
  }, [debouncedFilter]);

  // Elapsed timer — ticks every second
  useEffect(() => {
    const t = setInterval(() => {
      if (lastActivity) {
        setElapsed(Math.floor((Date.now() - lastActivity) / 1000));
      }
    }, 1000);
    return () => clearInterval(t);
  }, [lastActivity]);

  // Lines-per-second counter
  useEffect(() => {
    lpsCountRef.current = 0;
    lpsIntervalRef.current = window.setInterval(() => {
      setLps(lpsCountRef.current);
      lpsCountRef.current = 0;
    }, 1000);
    return () => {
      if (lpsIntervalRef.current) clearInterval(lpsIntervalRef.current);
    };
  }, [debouncedFilter]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, [lines, autoScroll]);

  // Detect manual scroll up → pause auto-scroll
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    setAutoScroll(atBottom);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 p-3 border-b border-surface-light flex-wrap">
        <h2 className="text-lg font-semibold text-slate-200">Logs</h2>
        <input
          type="text"
          placeholder="Filtrar..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 max-w-xs px-3 py-1.5 bg-surface-light border border-surface-light rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-primary"
        />
        <div className="flex items-center gap-1.5">
          {connected ? (
            <>
              <span className="relative flex h-2 w-2">
                {lps > 0 && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />}
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400" />
              </span>
              <span className="text-xs text-green-400">live</span>
            </>
          ) : (
            <>
              <span className="inline-flex rounded-full h-2 w-2 bg-red-400" />
              <span className="text-xs text-red-400">disconnected</span>
            </>
          )}
        </div>
        <span className="text-[10px] text-slate-500 font-mono tabular-nums">
          {connected && elapsed > 3
            ? `esperando... ${formatElapsed(elapsed)}`
            : connected && lps > 0
              ? `${lps} lineas/s`
              : ''}
          {' '}{lineCountRef.current > 0 && `| ${lineCountRef.current} lineas`}
        </span>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`text-xs px-2 py-1 rounded ${autoScroll ? 'bg-primary/20 text-primary' : 'bg-surface-light text-slate-400'}`}
        >
          {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
        </button>
        <button
          onClick={() => { setLines([]); lineCountRef.current = 0; }}
          className="text-xs px-2 py-1 rounded bg-surface-light text-slate-400 hover:text-slate-200"
        >
          Clear
        </button>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto bg-[#0d1117] p-3"
      >
        <pre className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">
          {lines.map((line, i) => (
            <div key={i} className={getLineColor(line)}>{line}</div>
          ))}
        </pre>
        {connected && elapsed > 3 && (
          <div className="text-slate-600 text-xs font-mono mt-1 animate-pulse">
            _ esperando nuevos logs...
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
