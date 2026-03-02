"""Sentinel — Opus-powered intelligent position monitor.

Only runs when there's an open position. Analyzes candles + indicators
+ Darwin context to decide: HOLD, TIGHTEN, CLOSE, or LET_RUN.
"""
import json
import logging
import time

from trading.signals import _rsi, _vwap, _adx, _atr, _volume_delta, _roc

logger = logging.getLogger(__name__)

SENTINEL_MODEL = "claude-opus-4-6"

SENTINEL_SYSTEM = """Eres Sentinel, el monitor inteligente de posiciones de un bot de trading de futuros crypto.

Tu trabajo: evaluar la posición abierta con datos en tiempo real y decidir la mejor acción táctica.

ACCIONES DISPONIBLES:
- HOLD (default): Dejar que trailing/SL/TP manejen normalmente. Usa esto si no hay razón clara para intervenir.
- TIGHTEN: Mover el SL más cerca del precio actual para proteger ganancia. Solo cuando hay señales de reversión.
- CLOSE: Cerrar inmediatamente. Solo para peligro inminente que trailing/SL no captaría (cambio de estructura, volume spike contra la posición, etc).
- LET_RUN: Relajar el trailing trigger para dejar correr un winner. Solo cuando el momentum es fuerte a favor y no hay señales de agotamiento.

REGLAS:
- Por defecto, HOLD. Solo interviene cuando hay evidencia clara.
- TIGHTEN: el new_sl DEBE estar entre el SL actual y el precio actual (más protectivo, NUNCA más lejos).
- CLOSE: usa con extrema precaución. Cada cierre tiene fees (~$0.095). No cierres por ruido.
- LET_RUN: solo si PnL es positivo Y momentum fuerte a favor.
- Considera los fees: un trade necesita >0.95% de ganancia para ser rentable.
- Respeta las directivas de Darwin (estratégicas).

Responde SOLO con JSON válido (sin markdown, sin explicaciones fuera del JSON):
{"action": "HOLD|TIGHTEN|CLOSE|LET_RUN", "reason": "breve explicación", "new_sl": null, "observation": "nota para el contexto compartido"}

Para TIGHTEN: new_sl debe ser un número (el nuevo stop loss).
Para HOLD/CLOSE/LET_RUN: new_sl debe ser null."""


def _build_sentinel_prompt(pos: dict, candles_5m: list, candles_15m: list,
                           context, journal_recent: list,
                           current_price: float, net_pnl: float) -> str:
    """Build the user prompt with position + market data for Opus."""
    entry = pos["entry_price"]
    side = pos["side"]
    leverage = pos.get("leverage", 8)
    margin = pos.get("margin", 0)

    # PnL calculations
    if side == "long":
        pnl_pct = (current_price - entry) / entry * 100
    else:
        pnl_pct = (entry - current_price) / entry * 100
    pnl_pct_lev = pnl_pct * leverage

    hold_seconds = time.time() - pos.get("open_time", time.time())
    hold_min = hold_seconds / 60

    # Indicators from 5m candles
    ind = {}
    if candles_5m and len(candles_5m) >= 15:
        closes = [c[4] for c in candles_5m]
        highs = [c[2] for c in candles_5m]
        lows = [c[3] for c in candles_5m]
        ind["rsi_5m"] = round(_rsi(closes, 14), 1)
        ind["adx_5m"] = round(_adx(highs, lows, closes, 14), 1)
        ind["atr_5m"] = round(_atr(highs, lows, closes, 14), 6)
        ind["vol_delta_5m"] = round(_volume_delta(candles_5m), 3)
        ind["roc_5m"] = round(_roc(closes, 10), 3)
        vwap = _vwap(candles_5m)
        if vwap:
            ind["vwap_dev_5m"] = round((current_price - vwap) / vwap * 100, 3)

    # Indicators from 15m candles
    if candles_15m and len(candles_15m) >= 15:
        closes = [c[4] for c in candles_15m]
        highs = [c[2] for c in candles_15m]
        lows = [c[3] for c in candles_15m]
        ind["rsi_15m"] = round(_rsi(closes, 14), 1)
        ind["adx_15m"] = round(_adx(highs, lows, closes, 14), 1)
        ind["vol_delta_15m"] = round(_volume_delta(candles_15m), 3)

    # Format last 6 candles of each timeframe
    def fmt_candles(clist, label):
        if not clist:
            return f"  {label}: sin datos"
        lines = []
        for c in clist[-6:]:
            o, h, l, cl, v = c[1], c[2], c[3], c[4], c[5]
            chg = ((cl - o) / o * 100) if o else 0
            lines.append(f"    O={o:.4f} H={h:.4f} L={l:.4f} C={cl:.4f} "
                         f"V={v:.0f} chg={chg:+.2f}%")
        return f"  {label}:\n" + "\n".join(lines)

    candles_text = fmt_candles(candles_5m, "5m") + "\n" + fmt_candles(candles_15m, "15m")

    # Darwin context
    ctx_lines = []
    if context:
        m = context.market
        ctx_lines.append(f"Régimen: {m.get('regime', '?')}, "
                         f"Volatilidad: {m.get('volatility', '?')}, "
                         f"BTC trend: {m.get('btc_trend', 'N/A')}")
        if context.directives:
            ctx_lines.append(f"Directivas Darwin: {'; '.join(context.directives)}")
        bias = context.get_bias(pos["pair"])
        if bias:
            ctx_lines.append(f"Bias para {pos['pair']}: {bias['direction']} "
                             f"(confianza={bias['confidence']}, {bias['reason']})")

    ctx_text = "\n".join(ctx_lines) if ctx_lines else "Sin contexto Darwin"

    # Recent trades summary
    recent_lines = []
    for t in (journal_recent or [])[-5:]:
        recent_lines.append(
            f"  {t.get('pair')} {t.get('side')} PnL=${t.get('pnl', 0):.4f} "
            f"reason={t.get('reason')} hold={t.get('hold_seconds', 0) / 60:.1f}min"
        )
    recent_text = "\n".join(recent_lines) if recent_lines else "  Sin trades recientes"

    return f"""POSICIÓN ACTUAL:
  Par: {pos['pair']}
  Lado: {side}
  Entrada: {entry:.6f}
  Precio actual: {current_price:.6f}
  SL actual: {pos['sl']:.6f}
  TP: {pos['tp']:.6f}
  PnL: {pnl_pct_lev:+.2f}% (${net_pnl:+.4f} neto después de fees)
  Peak PnL: {pos.get('peak_pnl_pct', 0):.2f}%
  Trailing activo: {pos.get('trailing_active', False)}
  Hold time: {hold_min:.1f} min
  Leverage: {leverage}x, Margin: ${margin:.2f}
  Strategy: {pos.get('strategy', '?')}, Score: {pos.get('score', 0)}

VELAS RECIENTES:
{candles_text}

INDICADORES:
{json.dumps(ind, indent=2)}

CONTEXTO DARWIN:
{ctx_text}

TRADES RECIENTES:
{recent_text}

Analiza la posición y decide: HOLD, TIGHTEN, CLOSE o LET_RUN."""


def validate_sentinel_action(decision: dict, pos: dict,
                             current_price: float) -> dict | None:
    """Validate sentinel decision. Returns sanitized dict or None if invalid."""
    action = decision.get("action", "").upper()
    if action not in ("HOLD", "TIGHTEN", "CLOSE", "LET_RUN"):
        logger.warning(f"Sentinel invalid action: {action}, falling back to HOLD")
        return {"action": "HOLD", "reason": "invalid action from LLM",
                "new_sl": None, "observation": None}

    if action == "TIGHTEN":
        new_sl = decision.get("new_sl")
        if new_sl is None:
            logger.warning("Sentinel TIGHTEN without new_sl, falling back to HOLD")
            return {"action": "HOLD", "reason": "TIGHTEN missing new_sl",
                    "new_sl": None, "observation": decision.get("observation")}
        try:
            new_sl = float(new_sl)
        except (ValueError, TypeError):
            logger.warning(f"Sentinel TIGHTEN invalid new_sl={new_sl}")
            return {"action": "HOLD", "reason": "TIGHTEN invalid new_sl",
                    "new_sl": None, "observation": decision.get("observation")}

        old_sl = pos["sl"]
        if pos["side"] == "long":
            # Long: old_sl < new_sl < current_price
            if not (old_sl < new_sl < current_price):
                logger.warning(f"Sentinel TIGHTEN invalid range: "
                               f"old_sl={old_sl} new_sl={new_sl} price={current_price}")
                return {"action": "HOLD", "reason": "TIGHTEN out of valid range",
                        "new_sl": None, "observation": decision.get("observation")}
        else:
            # Short: current_price < new_sl < old_sl
            if not (current_price < new_sl < old_sl):
                logger.warning(f"Sentinel TIGHTEN invalid range: "
                               f"price={current_price} new_sl={new_sl} old_sl={old_sl}")
                return {"action": "HOLD", "reason": "TIGHTEN out of valid range",
                        "new_sl": None, "observation": decision.get("observation")}

        return {"action": "TIGHTEN", "reason": decision.get("reason", ""),
                "new_sl": new_sl, "observation": decision.get("observation")}

    return {"action": action, "reason": decision.get("reason", ""),
            "new_sl": None, "observation": decision.get("observation")}


async def sentinel_check(pos: dict, exchange, context, journal_recent: list,
                         llm) -> dict | None:
    """Run one Sentinel check on the open position.

    Returns validated decision dict or None on failure.
    """
    pair = pos["pair"]

    # Fetch candles for both timeframes
    candles_5m = exchange.fetch_candles(pair, "5m", 30)
    candles_15m = exchange.fetch_candles(pair, "15m", 30)

    if not candles_5m:
        logger.warning("Sentinel: no 5m candles, skipping")
        return None

    current_price = candles_5m[-1][4]

    # Estimate net PnL after fees
    entry = pos["entry_price"]
    leverage = pos.get("leverage", 8)
    margin = pos.get("margin", 0)
    if pos["side"] == "long":
        pnl_pct = (current_price - entry) / entry * 100
    else:
        pnl_pct = (entry - current_price) / entry * 100
    pnl_usd = margin * (pnl_pct * leverage / 100)
    estimated_fees = 0.095 * 2  # open + close fees estimate
    net_pnl = pnl_usd - estimated_fees

    prompt = _build_sentinel_prompt(
        pos, candles_5m, candles_15m, context,
        journal_recent, current_price, net_pnl,
    )

    try:
        response = await llm.generate(
            system=SENTINEL_SYSTEM,
            user_message=prompt,
            model=SENTINEL_MODEL,
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        decision = json.loads(raw)
        validated = validate_sentinel_action(decision, pos, current_price)
        if validated:
            logger.info(f"Sentinel: {validated['action']} — {validated.get('reason', '')}")
        return validated

    except Exception as e:
        logger.warning(f"Sentinel LLM failed: {e}")
        return None
