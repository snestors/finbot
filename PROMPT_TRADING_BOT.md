# Prompt v2: Self-Evolving Crypto Trading Bot — Sentinel + Darwin + Shared Context

> Bot de trading de futuros crypto con dos agentes LLM (Darwin + Sentinel) que comparten contexto, monitor inteligente de posiciones, filtro pre-trade, detección de régimen, y trailing consciente de fees.

---

## ARQUITECTURA v2

```
trading/
├── bot.py          # Orquestador (run_with_sentinel cada minuto)
├── config.py       # Parámetros configurables
├── exchange.py     # Wrapper ccxt Bitget
├── signals.py      # Estrategias de señales + detect_regime()
├── brain.py        # Motor de aprendizaje — pesos por régimen
├── journal.py      # Historial de trades inmutable
├── state.py        # Estado: posición, cooldowns
├── darwin.py       # Motor evolutivo (Opus, cada hora)
├── sentinel.py     # Monitor inteligente de posiciones (Opus, cada 5min con posición)
├── context.py      # Memoria compartida Darwin ↔ Sentinel
└── data/
    ├── brain.json      # Pesos y parámetros
    ├── journal.json    # Historial de trades
    ├── state.json      # Estado del bot
    └── context.json    # Contexto compartido
```

### Flujo de ejecución v2 (cada minuto):

```
scheduler → bot.run_with_sentinel(llm) →
  1. ¿Posición abierta?
     a. Monitor mecánico (SL/TP/trailing con fee-awareness)
     b. Si no cerró → ¿Es hora del Sentinel? → sentinel_check()
        → HOLD (nada) | TIGHTEN (mover SL) | CLOSE (cerrar) | LET_RUN (relajar trailing)
  2. ¿Sin posición?
     a. detect_regime() desde BTC candles
     b. get_weights_for_regime() para scoring
     c. Scan señales → mejor candidato
     d. Pre-trade filter (Opus) → ¿Permitir o bloquear?
     e. Si permitido → abrir posición
```

---

## AGENTE 1: DARWIN (Estratégico, cada hora)

**Modelo**: `claude-opus-4-6`
**Frecuencia**: Cada hora
**Rol**: Analista estratégico que evoluciona el bot

### Qué hace:
- Kill/boost estrategias y pares basado en performance
- Ajustar parámetros (SL, TP, leverage, min_score, trailing)
- Escribir **directivas** estratégicas para Sentinel
- Establecer **biases** por par (bullish/neutral/bearish)
- Detectar **régimen de mercado** y volatilidad
- Ajustar parámetros de Sentinel (agresividad, frecuencia)

### Output JSON:
```json
{
  "strategies": [{"name": "...", "action": "kill|boost|hold", "reason": "..."}],
  "pairs": [{"name": "...", "action": "kill|resurrect|hold", "reason": "..."}],
  "params": {"sl_atr_mult": null, "tp_atr_mult": null, ...},
  "directives": ["directiva para Sentinel"],
  "biases": {"SOL/USDT:USDT": {"direction": "bullish", "confidence": 0.7, "reason": "..."}},
  "market": {"regime": "ranging", "btc_trend": "...", "volatility": "medium"},
  "sentinel_adjustments": {"aggression": null, "check_interval_min": null, ...},
  "summary": "estado general"
}
```

---

## AGENTE 2: SENTINEL (Táctico, cada 5 min con posición)

**Modelo**: `claude-opus-4-6`
**Frecuencia**: Cada `check_interval_min` (default 5) minutos, SOLO cuando hay posición
**Rol**: Monitor inteligente que complementa el trailing mecánico

### Input:
- Posición actual (par, lado, entrada, PnL, peak, trailing status, tiempo)
- Últimas 6 velas de 5m y 15m
- Indicadores (RSI, VWAP dev, ADX, vol_delta, ATR, ROC)
- Directivas y biases de Darwin
- PnL estimado neto después de fees
- Trades recientes del journal

### Acciones:
| Acción | Cuándo | Efecto |
|--------|--------|--------|
| HOLD | Default, sin señal clara | Nada, trailing/SL/TP siguen |
| TIGHTEN | Señales de reversión, proteger ganancia | Mover SL más cerca (validado: nunca más lejos) |
| CLOSE | Peligro inminente que trailing no capta | Cerrar posición inmediatamente |
| LET_RUN | Winner con momentum fuerte a favor | Relajar trailing trigger ×1.5 |

### Validación:
- TIGHTEN: `old_sl < new_sl < price` (long) o `price < new_sl < old_sl` (short)
- Acciones inválidas → fallback a HOLD
- Máximo `max_interventions` (default 3) por posición

---

## FILTRO PRE-TRADE (antes de abrir)

**Modelo**: `claude-opus-4-6`
**Cuándo**: Antes de cada apertura de posición
**Fail-open**: Si LLM falla → permite el trade

### Qué evalúa:
- Bias de Darwin para el par
- Régimen de mercado
- Directivas estratégicas
- Calidad de la señal

### Output:
```json
{"allow": true|false, "reason": "explicación"}
```

---

## CONTEXTO COMPARTIDO (context.json)

Memoria compartida entre Darwin y Sentinel:

```json
{
  "market": {
    "regime": "ranging|trending_up|trending_down",
    "btc_trend": "descripción",
    "volatility": "low|medium|high",
    "updated_by": "darwin|sentinel|signals",
    "updated_at": unix_timestamp
  },
  "directives": ["directivas estratégicas de Darwin"],
  "observations": [
    {"time": "HH:MM", "ts": unix, "agent": "sentinel|darwin", "note": "observación"}
  ],
  "biases": {
    "SOL/USDT:USDT": {"direction": "bullish", "confidence": 0.7, "reason": "..."}
  },
  "sentinel_params": {
    "aggression": "conservative|moderate|aggressive",
    "check_interval_min": 5,
    "confidence_threshold": 0.6,
    "max_interventions": 3
  }
}
```

- Darwin escribe: directives, biases, market, sentinel_params
- Sentinel lee: directives, biases; escribe: observations
- Signals escribe: regime (auto-detectado de BTC candles)
- Últimas 50 observaciones (auto-trim)

---

## DETECCIÓN DE RÉGIMEN

```python
def detect_regime(candles):
    adx = _adx(...)
    roc = _roc(..., 10)
    if adx > 25 and roc > 0.1:  return "trending_up"
    if adx > 25 and roc < -0.1: return "trending_down"
    return "ranging"
```

Se ejecuta en cada scan desde BTC candles. Actualiza context.json.
Los pesos de brain se seleccionan por régimen (`get_weights_for_regime()`).

---

## TRAILING CONSCIENTE DE FEES

Cuando trailing quiere cerrar:
1. Estimar net_pnl = gross_pnl - estimated_fees (~$0.19 total)
2. Si net_pnl < 0 → skip trailing, resetear, dejar que SL/TP manejen
3. Si Sentinel puso `trailing_trigger_override` → usar ese trigger

Esto evita cerrar trades con "ganancia" que después de fees son pérdida.

---

## SISTEMA DE SEÑALES (sin cambios)

### Estrategia 1: Volume Momentum (Contrarian Fade)
- Momentum decelerando → fade the move
- SHORT cuando momentum alcista decelera (roc_5 < roc_20 × 0.8)
- LONG cuando momentum bajista decelera

### Estrategia 2: VWAP Reversion
- Precio lejos del VWAP + 2/3 confirmaciones de agotamiento
- Volume declining, small body (doji), delta a favor

### Scoring
- Base baja (35), bonuses pequeños, penalizaciones fuertes
- Multiplicado por peso del régimen actual
- min_score = 50 para entrar

---

## GESTIÓN DE POSICIONES

- SL/TP basado en ATR (2.2x / 3.3x, clamped 0.5%-1.5%)
- Trailing stop: trigger 0.5%, distance 40% del peak
- Grace period: 2 min antes de cualquier cierre
- Position sizing: 50% del balance, leverage 8x (ajustable por Darwin)

---

## LECCIONES APRENDIDAS

1. **Fees destruyen rentabilidad**: $0.095/trade × 2 = $0.19. Con margen ~$10, necesitas >0.95% por trade.
2. **Contrarian fade funciona**: No seguir momentum, fade la desaceleración.
3. **SL tight = quick losses**: 2.2x ATR mínimo para evitar ruido.
4. **Trailing es el MVP**: Mecanismo de cierre más rentable. Fee-awareness lo mejora.
5. **Winners necesitan tiempo**: 55-290 min hold time. Sentinel LET_RUN ayuda.
6. **Grace period esencial**: 2 min para evitar false closes de la API.

---

## CONFIGURACIÓN

```python
CONFIG = {
    "pairs": ["SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT"],
    "leverage_default": 8, "margin_pct": 0.50,
    "sl_atr_mult": 2.2, "tp_atr_mult": 3.3,
    "sl_min_pct": 0.005, "sl_max_pct": 0.015,
    "min_score": 50, "cooldown_candles": 3,
    "trailing_trigger_pct": 0.5, "trailing_distance_pct": 40,
    "strategies": ["volume_momentum", "vwap_reversion"],
    "candle_tf": "5m", "candle_count": 60,
    "paper_mode": True, "grace_period_min": 2,
    "sentinel_check_interval_min": 5,
    "sentinel_max_interventions": 3,
    "sentinel_aggression": "moderate",
}
```

---

## COSTOS LLM ESTIMADOS

| Agente | Frecuencia | Modelo | Costo estimado |
|--------|-----------|--------|---------------|
| Darwin | 1x/hora | Opus | ~$0.05/ciclo |
| Sentinel | Cada 5min CON posición | Opus | ~$0.03/check |
| Pre-trade | Por señal candidata | Opus | ~$0.02/check |

Sin posición abierta: solo Darwin ($0.05/hora ≈ $1.20/día).
Con posición promedio 2h: +12 Sentinel checks ($0.36) + 1 pre-trade ($0.02).
