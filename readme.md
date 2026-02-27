# FinBot

Personal finance assistant running on a Raspberry Pi. Multi-agent system with WhatsApp + web chat, IoT power monitoring, and self-programming capabilities.

## Stack

- **Backend**: Python 3 — FastAPI + aiosqlite + SQLite
- **Frontend**: React 19 + TypeScript + Vite + Tailwind + Recharts + Zustand
- **LLM**: Claude (primary) + Gemini (fallback)
- **WhatsApp**: Node.js bridge (`whatsapp-web.js`)
- **IoT**: Sonoff POW Elite via mDNS/Zeroconf
- **Deploy**: Raspberry Pi + Cloudflare Tunnels + systemd

## Architecture

```
User ──► WhatsApp Bridge ──► Message Bus ──► Router ──► Agent ──► ActionExecutor ──► DB
         Web Chat (WS)  ──┘                  │
                                              ├─ Finance   (gastos, ingresos, tarjetas, deudas)
                                              ├─ Analysis  (resumenes, presupuestos, consumos)
                                              ├─ Admin     (sistema, plugins, herramientas, git)
                                              └─ Chat      (conversacion general)
```

## Agents

| Agent | Role | Hot-reload |
|-------|------|------------|
| **Finance** | Register expenses, income, payments, transfers, debts | `data/agents/finance.md` |
| **Analysis** | Summaries, budgets, currency, energy consumption | `data/agents/analysis.md` |
| **Admin** | System tools, memory, reminders, plugins, self-edit | `data/agents/admin.md` |
| **Chat** | Conversation, onboarding, fallback | `data/agents/chat.md` |

Agent prompts are hot-reloadable — edit the `.md` file and changes take effect immediately.

## Key Features

- **Unified movimientos table** — replaces 6 legacy tables (gastos, ingresos, transferencias, etc.)
- **Credit card tracking** — billing cycles, statement import, installments (cuotas)
- **Receipt parsing** — send a photo, auto-extracts items via Google AI Vision
- **Budget alerts** — per-category spending limits with threshold notifications
- **IoT power monitoring** — Sonoff smart plug readings every minute
- **Plugin system** — `plugins/*.py` auto-load with hot-reload, no restart needed
- **Self-programming** — admin agent can edit code, create plugins, consult Claude Code (Opus 4.6)
- **Scheduled jobs** — morning greetings, weekly summaries, bill reminders, exchange rates
- **Real-time activity stream** — web chat shows what the bot is doing step-by-step
- **Auto-recovery** — git checkpoints before restarts, preflight checks, auto-rollback on crash

## Setup

```bash
git clone git@github.com:snestors/finbot.git
cd finbot
cp .env.example .env   # fill in API keys
python3 src/main.py     # auto-creates venv, installs deps, starts everything
```

The bootstrap in `main.py` handles everything: venv creation, pip install, Node.js check, npm install, Chromium for WhatsApp, data directories.

### Environment Variables

```env
CLAUDE_API_TOKEN=sk-ant-...     # Claude API key or OAuth token
GOOGLE_AI_API_KEY=AIzaSy...     # Gemini fallback + receipt parsing
WHATSAPP_MY_NUMBER=51XXXXXXXXX@c.us
AUTH_PIN_HASH=                   # bcrypt hash of your PIN
TIMEZONE=America/Lima
PORT=8080
```

Generate PIN hash:
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PIN', bcrypt.gensalt()).decode())"
```

## Project Structure

```
finbot/
├── src/
│   ├── main.py              # Bootstrap + app entry point
│   ├── bot/processor.py     # Message orchestrator + agentic loop
│   ├── bus/message_bus.py   # Routes messages, broadcasts WS events
│   ├── agents/
│   │   ├── router.py        # Regex + Gemini message classification
│   │   ├── base_agent.py    # LLM parsing with retry + plain text fallback
│   │   └── action_executor.py  # Handler registry for all action types
│   ├── agent/
│   │   ├── tools.py         # MCP tools (file ops, commands, git, RPi)
│   │   └── plugin_manager.py   # Dynamic plugin loader with hot-reload
│   ├── channels/web.py      # FastAPI endpoints + WebSocket
│   ├── database/db.py       # SQLite init + migrations (v1→v4)
│   ├── repository/          # Data access (movimiento, cuenta, tarjeta, etc.)
│   ├── services/            # Scheduler, Sonoff, budget, currency, receipt parser
│   ├── llm.py               # Claude + Gemini dual LLM client
│   └── config.py            # Pydantic settings from .env
├── data/
│   ├── agents/*.md          # Agent prompts (hot-reload)
│   ├── alma.md              # Bot personality
│   ├── finbot.db            # SQLite database
│   └── backups/             # Auto-backups before migrations
├── plugins/                 # Custom plugins (hot-reload)
│   ├── web_search.py        # DuckDuckGo search + web fetch
│   └── ask_claude.py        # Consult Claude Code (Opus 4.6)
├── frontend/                # React SPA
│   └── src/pages/           # Chat, Dashboard, Gastos, Consumos, etc.
├── whatsapp-bridge/         # Node.js WhatsApp Web bridge
└── scripts/
    └── auto-recover.sh      # systemd crash recovery (git rollback)
```

## Safety

- **Core file protection**: Edits to core files auto-create git checkpoints + run preflight import tests. If broken, auto-reverts.
- **Preflight on restart**: `restart_service` refuses to restart if core imports fail.
- **Auto-recovery**: systemd ExecStopPost triggers `auto-recover.sh` on crashes — rolls back to last git checkpoint.
- **Plugin isolation**: Plugins can't edit core files. New features go in `plugins/*.py`.
- **Syntax validation**: All `.py` file writes are validated before saving.

## Development

```bash
# Frontend dev
cd frontend && npm run dev

# Frontend build (output to ../web/)
cd frontend && npm run build

# Restart service
sudo systemctl restart finbot

# View logs
journalctl -u finbot -f

# Check status
systemctl status finbot
```

## License

Private project.
