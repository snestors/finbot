import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get, upload } from '../api/client';
import { useChatStore, type ActivityStep } from '../store/chatStore';
import { useWebSocket } from '../hooks/useWebSocket';

function stripModelSuffix(text: string): { clean: string; model: string | null } {
  const match = text.match(/\n_via ([\w]+)_$/);
  if (match) return { clean: text.slice(0, match.index), model: match[1] };
  return { clean: text, model: null };
}

const modelColors: Record<string, string> = {
  sonnet: 'bg-orange-500/20 text-orange-400',
  gemini: 'bg-blue-500/20 text-blue-400',
};

const stepIcons: Record<string, string> = {
  routing: '\u2699',
  routed: '\u{1F916}',
  thinking: '\u{1F4AD}',
  tool: '\u{1F527}',
  action: '\u26A1',
  media: '\u{1F4CE}',
};

function ActivityPanel({ steps }: { steps: ActivityStep[] }) {
  const [collapsed, setCollapsed] = useState(false);
  const latest = steps[steps.length - 1];
  if (!steps.length) return null;

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] md:max-w-[70%] bg-surface border border-surface-light rounded-xl rounded-bl-sm text-sm">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center gap-2 px-3 py-2 text-left text-slate-300 hover:text-slate-100 transition-colors"
        >
          <span className="animate-spin inline-block w-3 h-3 border border-primary border-t-transparent rounded-full" />
          <span className="flex-1 text-xs">{latest?.detail || 'Procesando...'}</span>
          <span className="text-[10px] text-slate-500">{collapsed ? '\u25B6' : '\u25BC'}</span>
        </button>
        {!collapsed && steps.length > 1 && (
          <div className="px-3 pb-2 space-y-0.5 border-t border-surface-light pt-1.5">
            {steps.slice(0, -1).map((s, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[11px] text-slate-500">
                <span>{stepIcons[s.step] || '\u2714'}</span>
                <span>{s.detail}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Chat() {
  const { messages, setMessages, connected, waiting, activitySteps } = useChatStore();
  const { send } = useWebSocket();
  const [input, setInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: historial } = useQuery({
    queryKey: ['mensajes'],
    queryFn: () => get('/api/mensajes?limit=50'),
    staleTime: 0,
  });

  useEffect(() => {
    if (historial) setMessages(historial);
  }, [historial, setMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activitySteps]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text && !file) return;
    setInput('');
    if (file) {
      const f = file;
      setFile(null);
      await upload('/api/upload-receipt', f, text || undefined);
    } else {
      send(text);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] lg:h-[calc(100vh-3rem)]">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-lg font-bold">Chat</h2>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-success' : 'bg-danger'}`} />
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pb-2">
        {messages.map((m, i) => {
          const isBot = m.role !== 'user';
          const { clean, model: parsedModel } = isBot ? stripModelSuffix(m.content || '') : { clean: m.content, model: null };
          const model = m.model || parsedModel;
          return (
            <div key={m.id || i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] md:max-w-[70%] rounded-xl text-sm ${
                m.role === 'user'
                  ? 'bg-primary/20 text-primary-dark rounded-br-sm'
                  : 'bg-surface border border-surface-light rounded-bl-sm'
              }`}>
                {m.role === 'user' && m.source && m.source !== 'web' && (
                  <div className="px-3 pt-1.5 pb-0">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">
                      WhatsApp
                    </span>
                  </div>
                )}
                <div className="px-3 py-2 whitespace-pre-wrap">{clean}</div>
                {isBot && model && (
                  <div className="px-3 pb-1.5 pt-0">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${modelColors[model] || 'bg-slate-500/20 text-slate-400'}`}>
                      {model}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {waiting && activitySteps.length > 0 && (
          <ActivityPanel steps={activitySteps} />
        )}
        {waiting && activitySteps.length === 0 && (
          <div className="flex justify-start">
            <div className="bg-surface border border-surface-light rounded-xl rounded-bl-sm px-4 py-2 text-sm text-slate-400">
              <span className="inline-flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="pt-2 border-t border-surface-light">
        <input
          ref={fileRef}
          type="file"
          accept="image/*,.pdf,.xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => { if (e.target.files?.[0]) setFile(e.target.files[0]); e.target.value = ''; }}
        />
        {file && (
          <div className="flex items-center gap-2 mb-2 px-2 py-1.5 bg-surface-light rounded-lg text-xs text-slate-300">
            <span className="truncate flex-1">{file.name}</span>
            <button onClick={() => setFile(null)} className="text-slate-400 hover:text-slate-200 shrink-0">&times;</button>
          </div>
        )}
        <div className="flex gap-2">
          <button
            onClick={() => fileRef.current?.click()}
            title="Adjuntar archivo"
            className="bg-surface border border-surface-light hover:bg-surface-light text-slate-300 px-3 py-2 rounded-lg text-sm transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
            placeholder={file ? "Mensaje opcional..." : "Escribe un mensaje..."}
            className="flex-1 bg-surface border border-surface-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
          />
          <button onClick={handleSend} className="bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}
