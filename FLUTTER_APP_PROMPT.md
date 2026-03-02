# FinBot Flutter App — Implementation Prompt

> Use this prompt with Claude Code on a machine with Flutter SDK installed.
> The backend runs on a Raspberry Pi at the URL defined in .env (Cloudflare Tunnel).

---

## Overview

Build a Flutter mobile app for FinBot — a personal finance + trading bot running on a Raspberry Pi. The app replaces WhatsApp as the primary interface. It connects to the existing FastAPI backend via REST + WebSocket.

**3 main screens**: Chat, Trading, Consumos (energy monitoring)
**State management**: Riverpod (code generation)
**Auth**: Bearer token (PIN login)
**Notifications**: Firebase FCM
**Theme**: Dark mode, Material 3

---

## Project Setup

```bash
cd finbot/
flutter create --org com.finbot --project-name finbot_app flutter
cd flutter
```

### pubspec.yaml dependencies

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0
  go_router: ^14.0.0
  dio: ^5.4.0
  web_socket_channel: ^3.0.0
  flutter_secure_storage: ^9.0.0
  fl_chart: ^0.68.0
  image_picker: ^1.0.0
  firebase_messaging: ^15.0.0
  firebase_core: ^3.0.0
  flutter_local_notifications: ^17.0.0
  intl: ^0.19.0
  freezed_annotation: ^2.4.0
  json_annotation: ^4.9.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
  riverpod_generator: ^2.4.0
  freezed: ^2.5.0
  json_serializable: ^6.8.0
  flutter_lints: ^5.0.0
```

---

## Project Structure

```
lib/
├── main.dart                      # ProviderScope + runApp
├── app.dart                       # GoRouter config + MaterialApp.router
│
├── core/
│   ├── constants.dart             # API_BASE_URL, WS_URL (from .env or hardcoded)
│   ├── theme.dart                 # Dark Material 3 theme
│   └── extensions.dart            # DateTime formatting, currency formatting
│
├── models/                        # Freezed data classes
│   ├── message.dart               # id, role, content, timestamp, source, model
│   ├── system_stats.dart          # temp, mem, cpu, disk, power_w, voltage_v, current_a, day_kwh, month_kwh
│   ├── activity_step.dart         # step, detail, timestamp
│   ├── trading_status.dart        # TradingStatus (state, brain, journal_stats, recent_trades, balance, config, context)
│   ├── trade.dart                 # id, pair, side, entry_price, exit_price, pnl, reason, strategy, score, leverage, hold_seconds, paper, timestamp, fees, gross_pnl
│   ├── position.dart              # pair, side, entry_price, sl, tp, leverage, strategy, trailing_active, peak_pnl, timestamp
│   └── consumo.dart               # Consumo, PagoConsumo, ChartPoint, ConsumoConfig
│
├── services/
│   ├── api_client.dart            # Dio with Bearer auth interceptor
│   ├── auth_service.dart          # login(pin), logout(), isLoggedIn()
│   ├── websocket_service.dart     # Connect, reconnect, dispatch by message type
│   ├── notification_service.dart  # FCM init, register token, handle taps
│   └── secure_storage.dart        # flutter_secure_storage wrapper
│
├── providers/
│   ├── auth_provider.dart         # AuthState (loggedIn, loading, error)
│   ├── websocket_provider.dart    # WS connection state, auto-connect after auth
│   ├── chat_provider.dart         # Messages list, send, loadMore, activity steps
│   ├── system_stats_provider.dart # Live stats from WS (updated every 1s)
│   ├── trading_provider.dart      # TradingStatus with 5s polling
│   └── consumos_provider.dart     # Tab state, chart data, pagos, config
│
├── screens/
│   ├── login_screen.dart
│   ├── chat/
│   │   ├── chat_screen.dart       # Main layout: message list + input bar
│   │   ├── message_bubble.dart    # User/bot bubble with badges
│   │   ├── activity_panel.dart    # Agent processing steps indicator
│   │   └── chat_input_bar.dart    # Text field + send + attach
│   ├── trading/
│   │   ├── trading_screen.dart    # Main layout with all cards
│   │   ├── position_card.dart     # Open position details
│   │   ├── trade_row.dart         # Single trade in list
│   │   ├── brain_card.dart        # Brain parameters
│   │   └── stats_row.dart         # 4 stat cards row
│   └── consumos/
│       ├── consumos_screen.dart   # Top tabs (Luz/Agua/Gas) + sub-tabs
│       ├── luz_en_vivo.dart       # Live metrics + real-time chart
│       ├── luz_grafico.dart       # Historical chart with date picker
│       ├── luz_pagos.dart         # Payment history + form
│       ├── manual_tab.dart        # Agua/Gas manual entry
│       └── live_card.dart         # Reusable metric card
│
└── widgets/
    ├── stat_card.dart             # Reusable card with icon, label, value
    ├── badge.dart                 # Side, PnL, reason, model, source badges
    └── bottom_nav.dart            # Bottom navigation (Chat, Trading, Consumos)
```

---

## Backend API Reference

All endpoints require auth except POST /api/login and GET /api/health.

### Authentication
```
POST /api/login
  Body: { "pin": "1234" }
  Response: { "ok": true, "token": "abc123..." }
  Note: Store the token in flutter_secure_storage, send as "Authorization: Bearer <token>"
```

### Chat
```
GET /api/mensajes?limit=50&before=<id>
  → Array of { id, role, content, timestamp, source, model }

POST /api/upload-receipt
  → Multipart form: file=<File>, text=<optional caption>
  → { "ok": true }
```

### WebSocket Protocol
```
Endpoint: wss://<host>/ws

Server → Client:
  { "type": "system_stats", "temp": 45.2, "mem_pct": 60, "cpu_pct": 15,
    "power_w": 120.5, "voltage_v": 220.1, "current_a": 0.55,
    "day_kwh": 3.2, "month_kwh": 85.6, "uptime": "5d 3h", ... }

  { "type": "new_messages",
    "user_message": { "id": 1, "role": "user", "content": "hola", "timestamp": "...", "source": "web" },
    "bot_response": { "id": 2, "role": "bot", "content": "Hola!", "timestamp": "...", "model": "sonnet" } }

  { "type": "agent_activity", "step": "thinking", "detail": "Analizando...", "timestamp": "..." }
  { "type": "agent_activity", "step": "done" }  ← clears activity

Client → Server:
  { "type": "message", "text": "hola" }
```

### Trading
```
GET /api/trading/status
  → {
      state: { has_position, position, paused, paper_mode, last_run, consecutive_losses, globally_cooled_down },
      brain: { total_trades, wins, losses, win_rate, total_pnl, streak, evolve_count, killed_pairs, killed_strategies, params },
      journal_stats: { total, wins, losses, win_rate, total_pnl, avg_pnl, best, worst, gross_pnl, total_fees },
      recent_trades: Trade[],
      balance: number,
      config: { pairs, strategies, candle_tf, margin_pct, cooldown_candles, max_consecutive_losses },
      context: { regime, volatility, btc_trend, directives, active_biases, last_sentinel }
    }

POST /api/trading/pause → { "ok": true }
POST /api/trading/resume → { "ok": true }
POST /api/trading/darwin → { changes: [...], brain: {...} }
```

### Consumos (Energy)
```
GET /api/consumos?tipo=luz|agua|gas&mes=YYYY-MM → Array of consumos
GET /api/consumos/actual → { power_w, voltage_v, current_a, day_kwh, month_kwh }
GET /api/consumos/chart?tipo=luz&desde=ISO&hasta=ISO&slice=1 → Array of chart points
GET /api/consumos/periodo?tipo=luz&desde=ISO&hasta=ISO → { kwh_total, costo_total, ... }
GET /api/consumos/resumen?mes=YYYY-MM → Summary per type
GET /api/consumos/pagos?tipo=luz → Array of { id, tipo, monto, fecha_pago, fecha_desde, fecha_hasta, kwh_periodo, costo_kwh, notas }
GET /api/consumos/config → { costo_kwh_luz: "0.75", ... }

POST /api/consumos → { tipo, valor, unidad, fecha, costo } → { "id": N }
POST /api/consumos/pagos → { tipo, monto, fecha_pago, fecha_desde, fecha_hasta, notas } → { id, kwh_periodo, costo_kwh }
POST /api/consumos/config → { key: value } → { "ok": true }
DELETE /api/consumos/{id}
DELETE /api/consumos/pagos/{id}
```

### FCM Registration
```
POST /api/fcm/register → { "token": "<fcm_device_token>" } → { "ok": true }
POST /api/fcm/unregister → { "token": "<fcm_device_token>" } → { "ok": true }
```

---

## Screen Details

### Login Screen
- Dark background, centered card
- PIN input field (obscured, 4-6 digits)
- "Ingresar" button
- On success: store token via secure_storage, navigate to /chat
- On error: show "PIN incorrecto"

### Chat Screen
- **Message list**: ListView.builder, reversed (newest at bottom), auto-scroll on new message
- **Pagination**: ScrollController — when scrolled to top, call GET /api/mensajes?before=<oldest_id>
- **Message bubble**:
  - User: aligned right, primary color bg
  - Bot: aligned left, surface color bg with border
  - Bot messages show model badge: "sonnet" (orange) or "gemini" (blue)
  - Messages from WhatsApp show green "WA" badge
  - Content text may contain `_via sonnet_` suffix — strip it before displaying
- **Activity panel**: shown when waiting for response
  - Collapsible list showing agent processing steps
  - Icons per step: routing=⚙, routed=🤖, thinking=💭, tool=🔧, action=⚡, media=📎
  - Disappears when step="done" received
- **Input bar**: fixed at bottom
  - TextField + send button (enabled when text non-empty)
  - Attach button → bottom sheet: Camera / Gallery
  - File sends via POST /api/upload-receipt (multipart)
  - Text sends via WebSocket: { type: "message", text: "..." }
  - Show optimistic user bubble immediately

### Trading Screen
- **Header row**:
  - "Trading Bot" title
  - Mode badge: PAPER (yellow) or REAL (green) based on `state.paper_mode`
  - Status badge: ACTIVO (green) / PAUSADO (red) / COOLDOWN (orange)
  - Pause/Resume toggle button
- **Stats row** (2x2 grid of StatCard):
  - Balance: `$XX.XX` from `balance`
  - PnL Total: `$XX.XX` from `journal_stats.total_pnl` (colored green/red), subtitle "N trades"
  - Win Rate: `XX%` from `journal_stats.win_rate`, subtitle "XW / XL"
  - Streak: `+N` or `-N` from `brain.streak`, subtitle "N evoluciones"
- **Position card** (shown when `state.has_position`):
  - Pair (e.g. "SOL"), Side (LONG green / SHORT red)
  - Entry price, SL (red), TP (green)
  - Leverage, Strategy, Trailing active badge
- **Recent trades** (ListView):
  - Each row: pair, side badge, entry→exit, PnL badge (green/red), reason badge, strategy, hold duration, date
  - Reason colors: take_profit=green, stop_loss=red, trailing_stop=yellow, sentinel_close=purple
  - Newest first (reverse the array from API)
- **Brain card**: key-value pairs of brain.params (leverage, sl_atr_mult, tp_atr_mult, min_score, trailing_trigger_pct)
  - Show killed pairs/strategies in red text
- **Darwin button**: FAB or card button → POST /api/trading/darwin
- **Auto-refresh**: Poll GET /api/trading/status every 5 seconds

### Consumos Screen
- **Top tabs**: Luz (⚡) / Agua (💧) / Gas (🔥)
- **Luz sub-tabs**: En Vivo / Grafico / Pagos

**Luz - En Vivo**:
- 5 LiveCard widgets (2-column grid + 1):
  - Potencia: power_w (W) — yellow accent
  - Voltaje: voltage_v (V) — green accent
  - Corriente: current_a (A) — blue accent
  - Hoy: day_kwh (kWh) — green accent
  - Mes: month_kwh (kWh) — default accent
- Values come from system_stats WebSocket (updated every ~1s)
- Real-time line chart (fl_chart):
  - Rolling buffer of ~120 data points (2 min)
  - Left Y-axis: power_w (yellow line)
  - Right Y-axis: current_a (blue line)
  - Optional: voltage_v as dashed green line on left axis

**Luz - Grafico**:
- Date range: desde/hasta date pickers
  - Default: current billing cycle (7th to 7th of month)
- Grouping buttons: 1h, 2h, 4h, 8h, 24h (maps to `slice` query param)
- Line chart from GET /api/consumos/chart?tipo=luz&desde=...&hasta=...&slice=N
- Lines: power_w (yellow), current_a (blue), optional cost accumulation (green)

**Luz - Pagos**:
- Register payment form:
  - Monto (S/), Fecha pago, Periodo desde, Periodo hasta, Notas
  - Submit → POST /api/consumos/pagos
- Payment history list from GET /api/consumos/pagos?tipo=luz
  - Columns: Fecha, Monto, Periodo, kWh, S//kWh, Notas
  - Swipe-to-delete or delete icon

**Agua / Gas tabs**:
- Month picker (YYYY-MM)
- Summary cards (total consumption, readings count, estimated cost)
- Manual entry form: Fecha, Valor (m³), Costo (optional)
  - Submit → POST /api/consumos
- Monthly entries list with delete option

---

## Core Implementation Details

### API Client (Dio)

```dart
class ApiClient {
  late final Dio dio;

  ApiClient(SecureStorageService storage) {
    dio = Dio(BaseOptions(
      baseUrl: Constants.apiBaseUrl,  // e.g. "https://finbot.your-tunnel.com"
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
    ));

    // Auth interceptor
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await storage.getToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) {
        if (error.response?.statusCode == 401) {
          // Trigger logout / redirect to login
        }
        handler.next(error);
      },
    ));
  }
}
```

### WebSocket Service

```dart
class WebSocketService {
  WebSocketChannel? _channel;
  bool _connecting = false;
  Timer? _reconnectTimer;

  final void Function(Map<String, dynamic>) onSystemStats;
  final void Function(Map<String, dynamic>) onNewMessages;
  final void Function(Map<String, dynamic>) onAgentActivity;

  void connect(String token) {
    if (_connecting || (_channel != null)) return;
    _connecting = true;

    final uri = Uri.parse('${Constants.wsUrl}/ws');
    _channel = WebSocketChannel.connect(uri);
    _connecting = false;

    _channel!.stream.listen(
      (data) {
        final msg = jsonDecode(data);
        switch (msg['type']) {
          case 'system_stats': onSystemStats(msg);
          case 'new_messages': onNewMessages(msg);
          case 'agent_activity': onAgentActivity(msg);
        }
      },
      onDone: () { _channel = null; _scheduleReconnect(token); },
      onError: (_) { _channel = null; _scheduleReconnect(token); },
    );
  }

  void send(String text) {
    _channel?.sink.add(jsonEncode({'type': 'message', 'text': text}));
  }

  void _scheduleReconnect(String token) {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () => connect(token));
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
  }
}
```

### Theme (Dark Material 3)

```dart
ThemeData buildTheme() => ThemeData(
  useMaterial3: true,
  brightness: Brightness.dark,
  colorSchemeSeed: const Color(0xFF6366f1),  // Indigo matching web primary
  scaffoldBackgroundColor: const Color(0xFF0f172a),  // Slate 900
  cardTheme: CardTheme(
    color: const Color(0xFF1e293b),  // Slate 800
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
  ),
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFF0f172a),
    elevation: 0,
  ),
);
```

### GoRouter with Auth Guard

```dart
final routerProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authProvider);
  return GoRouter(
    redirect: (context, state) {
      final loggedIn = auth.isLoggedIn;
      final loggingIn = state.matchedLocation == '/login';
      if (!loggedIn && !loggingIn) return '/login';
      if (loggedIn && loggingIn) return '/chat';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      ShellRoute(
        builder: (_, __, child) => ScaffoldWithNav(child: child),
        routes: [
          GoRoute(path: '/chat', builder: (_, __) => const ChatScreen()),
          GoRoute(path: '/trading', builder: (_, __) => const TradingScreen()),
          GoRoute(path: '/consumos', builder: (_, __) => const ConsumosScreen()),
        ],
      ),
    ],
  );
});
```

---

## Implementation Order

Build in this order, verifying each phase works before moving to the next:

### Phase 1: Foundation
1. Create Flutter project + directory structure
2. Add all dependencies to pubspec.yaml
3. Implement core/constants.dart, core/theme.dart
4. Implement services/secure_storage.dart
5. Implement services/api_client.dart with Bearer auth
6. Implement services/auth_service.dart (login, logout, check)
7. Implement providers/auth_provider.dart
8. Implement login_screen.dart
9. Implement app.dart with GoRouter + auth guard
10. Implement main.dart with ProviderScope
11. Implement bottom_nav.dart (3 tabs: Chat, Trading, Consumos)
→ **Verify**: app launches, login works, navigates to empty screens

### Phase 2: Chat
1. Implement models/message.dart, models/activity_step.dart, models/system_stats.dart
2. Implement services/websocket_service.dart
3. Implement providers/websocket_provider.dart (auto-connect after auth)
4. Implement providers/chat_provider.dart
5. Implement providers/system_stats_provider.dart
6. Implement screens/chat/message_bubble.dart
7. Implement screens/chat/activity_panel.dart
8. Implement screens/chat/chat_input_bar.dart
9. Implement screens/chat/chat_screen.dart
→ **Verify**: messages load, send works, real-time via WS, badges show

### Phase 3: Trading
1. Implement models/trading_status.dart, trade.dart, position.dart
2. Implement providers/trading_provider.dart (5s polling)
3. Implement widgets/stat_card.dart, widgets/badge.dart
4. Implement screens/trading/stats_row.dart
5. Implement screens/trading/position_card.dart
6. Implement screens/trading/trade_row.dart
7. Implement screens/trading/brain_card.dart
8. Implement screens/trading/trading_screen.dart
→ **Verify**: status loads, auto-refresh, pause/resume, Darwin trigger

### Phase 4: Consumos
1. Implement models/consumo.dart
2. Implement providers/consumos_provider.dart
3. Implement screens/consumos/live_card.dart
4. Implement screens/consumos/luz_en_vivo.dart (live metrics from WS + chart)
5. Implement screens/consumos/luz_grafico.dart (historical chart)
6. Implement screens/consumos/luz_pagos.dart (payment form + history)
7. Implement screens/consumos/manual_tab.dart (agua/gas)
8. Implement screens/consumos/consumos_screen.dart (tabs)
→ **Verify**: live data shows, charts render, payments CRUD works

### Phase 5: Push Notifications (requires Firebase project setup first)
1. Set up Firebase project + FlutterFire CLI
2. Implement services/notification_service.dart
3. Register FCM token on app start → POST /api/fcm/register
4. Handle foreground notifications with flutter_local_notifications
5. Handle notification taps → deep-link to relevant screen
→ **Verify**: push arrives when trade opens/closes

### Phase 6: Polish
1. Connection status indicator (green/red dot)
2. Pull-to-refresh on Trading and Consumos
3. Error states (no connection, API errors)
4. Loading skeletons
5. App icon + splash screen
6. Build release APK

---

## Notes

- The backend already has all endpoints. The ONLY backend changes needed are:
  1. Add Bearer token check in `src/auth.py` AuthMiddleware (alongside existing cookie check)
  2. Return token in POST /api/login JSON response body
  3. Add FCM table, repo, service, endpoints (Phase 5 only)
- The .env file should contain: `API_BASE_URL=https://your-tunnel-domain.com`
- WebSocket URL derives from API_BASE_URL: replace https→wss, append /ws
- All timestamps from the API are UTC with Z suffix (ISO 8601)
- The API uses Spanish for some field names (movimientos, gastos, etc.)
