import { create } from 'zustand';

interface Message {
  id?: number;
  role: string;
  content: string;
  timestamp?: string;
  source?: string;
  model?: string;
}

export interface SystemStats {
  temp: number | null;
  mem_total_mb: number | null;
  mem_used_mb: number | null;
  mem_pct: number | null;
  cpu_pct: number | null;
  disk_total_gb: number | null;
  disk_used_gb: number | null;
  disk_pct: number | null;
  uptime: string | null;
  power_w?: number | null;
  voltage_v?: number | null;
  current_a?: number | null;
  day_kwh?: number | null;
  month_kwh?: number | null;
  wifi_dbm?: number | null;
  printer?: {
    status: string;
    progress: number;
    current_layer: number;
    total_layers: number;
    filename: string;
    eta_min: number;
    [key: string]: any;
  } | null;
}

export interface ActivityStep {
  step: string;
  detail: string;
  timestamp: string;
}

interface ChatState {
  messages: Message[];
  connected: boolean;
  waiting: boolean;
  systemStats: SystemStats | null;
  activitySteps: ActivityStep[];
  setMessages: (msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  setConnected: (v: boolean) => void;
  setWaiting: (v: boolean) => void;
  setSystemStats: (stats: SystemStats) => void;
  addActivity: (step: ActivityStep) => void;
  clearActivity: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  connected: false,
  waiting: false,
  systemStats: null,
  activitySteps: [],
  setMessages: (messages) => set({ messages }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setConnected: (connected) => set({ connected }),
  setWaiting: (waiting) => set({ waiting }),
  setSystemStats: (systemStats) => set({ systemStats }),
  addActivity: (step) => set((s) => ({ activitySteps: [...s.activitySteps, step] })),
  clearActivity: () => set({ activitySteps: [] }),
}));
