import { useEffect, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';

let ws: WebSocket | null = null;
let connecting = false;

function connect() {
  if (connecting || (ws && ws.readyState === WebSocket.OPEN)) return;
  connecting = true;

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws`;
  const socket = new WebSocket(url);
  ws = socket;

  socket.onopen = () => {
    connecting = false;
    useChatStore.getState().setConnected(true);
  };
  socket.onclose = () => {
    connecting = false;
    ws = null;
    useChatStore.getState().setConnected(false);
    setTimeout(connect, 3000);
  };
  socket.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === 'system_stats') {
        useChatStore.getState().setSystemStats(data);
      } else if (data.type === 'agent_activity') {
        if (data.step === 'done') {
          useChatStore.getState().clearActivity();
        } else {
          useChatStore.getState().addActivity({
            step: data.step,
            detail: data.detail || '',
            timestamp: data.timestamp || new Date().toISOString(),
          });
        }
      } else if (data.type === 'new_messages') {
        useChatStore.getState().clearActivity();
        useChatStore.setState((s) => {
          let msgs = s.messages.filter((m: any) => !m._optimistic);
          const existingIds = new Set(msgs.filter((m) => m.id).map((m) => m.id));
          if (data.user_message && !existingIds.has(data.user_message.id)) {
            msgs.push(data.user_message);
          }
          if (data.bot_response && !existingIds.has(data.bot_response.id)) {
            msgs.push(data.bot_response);
          }
          msgs.sort((a, b) => (a.id || 0) - (b.id || 0));
          return { messages: msgs, waiting: false };
        });
      }
    } catch {}
  };
}

export function useWebSocket() {
  useEffect(() => { connect(); }, []);

  const send = useCallback((text: string) => {
    if (ws?.readyState === WebSocket.OPEN) {
      useChatStore.getState().addMessage({ role: 'user', content: text, _optimistic: true } as any);
      useChatStore.getState().setWaiting(true);
      ws.send(JSON.stringify({ type: 'message', text }));
    }
  }, []);

  return { send };
}
