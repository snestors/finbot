"""Darwinian evolution engine — runs hourly. Kill bad, boost good.

Uses Claude Opus as analyst to make smarter evolutionary decisions.
Falls back to rule-based logic if LLM is unavailable.

v2: Writes directives, biases, market regime, and sentinel params to SharedContext.
"""
import json
import logging

from trading.brain import Brain
from trading.journal import Journal
from trading.config import CONFIG

logger = logging.getLogger(__name__)

DARWIN_MODEL = "claude-opus-4-6"

DARWIN_SYSTEM = """Eres el motor evolutivo (Darwin) de un bot de trading de futuros crypto.
Tu trabajo: analizar los trades recientes y decidir qué sobrevive y qué muere.
También estableces directivas estratégicas para Sentinel (el monitor de posiciones en tiempo real).

REGLAS:
- Lo que funciona se potencia, lo que no se mata.
- Necesitas datos suficientes para decidir (mínimo 5 trades por categoría).
- Sé conservador: no hagas cambios drásticos sin evidencia clara.
- Los winners se cierran por trailing_stop y duran 55-290 min.
- Los losers rápidos (<=2 min) indican SL demasiado tight.
- Win rate > 35% es aceptable si R:R > 1.5 (winners > losers en tamaño).

CONTEXTO COMPARTIDO CON SENTINEL:
- Sentinel monitorea posiciones abiertas cada 5 min con Opus.
- Tus directivas guían las decisiones tácticas de Sentinel.
- Tus biases por par influyen en el filtro pre-trade.
- Puedes ajustar los parámetros de Sentinel (agresividad, frecuencia, etc).

Responde SOLO con JSON válido (sin markdown, sin explicaciones fuera del JSON):
{
  "strategies": [
    {"name": "strategy_name", "action": "kill|boost|hold", "reason": "breve"}
  ],
  "pairs": [
    {"name": "PAIR/USDT:USDT", "action": "kill|resurrect|hold", "reason": "breve"}
  ],
  "params": {
    "sl_atr_mult": null,
    "tp_atr_mult": null,
    "leverage_default": null,
    "min_score": null,
    "trailing_trigger_pct": null,
    "trailing_distance_pct": null
  },
  "directives": ["directiva estratégica para Sentinel"],
  "biases": {
    "PAIR/USDT:USDT": {"direction": "bullish|neutral|bearish", "confidence": 0.7, "reason": "breve"}
  },
  "market": {
    "regime": "ranging|trending_up|trending_down",
    "btc_trend": "descripción breve",
    "volatility": "low|medium|high"
  },
  "sentinel_adjustments": {
    "aggression": null,
    "check_interval_min": null,
    "confidence_threshold": null,
    "max_interventions": null
  },
  "summary": "1-2 oraciones sobre el estado general del bot"
}

Para params y sentinel_adjustments: usa null si no hay que cambiar, o el nuevo valor si hay que ajustar.
Rangos válidos params: sl_atr_mult [1.8-3.0], tp_atr_mult [2.0-5.0], leverage_default [3-10],
min_score [40-70], trailing_trigger_pct [0.3-1.5], trailing_distance_pct [25-60].
Rangos válidos sentinel: aggression ["conservative"|"moderate"|"aggressive"],
check_interval_min [2-15], confidence_threshold [0.3-0.9], max_interventions [1-10].
directives, biases y market son opcionales — inclúyelos solo si tienes observaciones relevantes."""


def _format_param_ages(brain: Brain) -> str:
    """Format how long ago each param was last changed."""
    import time
    changed_at = brain.data.get("param_changed_at", {})
    if not changed_at:
        return "  (sin historial de cambios recientes)"
    now = time.time()
    lines = []
    for key, ts in sorted(changed_at.items()):
        hours = (now - ts) / 3600
        if hours < 24:
            lines.append(f"  {key}: cambiado hace {hours:.1f}h")
        else:
            lines.append(f"  {key}: cambiado hace {hours / 24:.1f}d")
    return "\n".join(lines) if lines else "  (sin cambios recientes)"


def _build_darwin_prompt(brain: Brain, journal: Journal, recent: list,
                         context=None) -> str:
    """Build the user prompt with all trade data for Opus analysis."""
    stats = journal.get_stats()
    brain_summary = brain.summary()
    params = brain.params

    # Per-strategy stats
    strat_lines = []
    for strategy in brain.data.get("strategy_weights", {}):
        s = journal.get_stats_for_strategy(strategy)
        weights = brain.data["strategy_weights"][strategy]
        strat_lines.append(
            f"  {strategy}: {s['total']} trades, WR={s['win_rate']}%, "
            f"PnL=${s['total_pnl']}, weights={weights}"
        )

    # Per-pair stats
    pair_lines = []
    pairs_seen = set(t.get("pair") for t in journal.get_all() if t.get("pair"))
    for pair in sorted(pairs_seen):
        s = journal.get_stats_for_pair(pair)
        killed = " [KILLED]" if pair in brain.killed_pairs else ""
        pair_lines.append(
            f"  {pair}: {s['total']} trades, WR={s['win_rate']}%, "
            f"PnL=${s['total_pnl']}{killed}"
        )

    # Recent trades detail (with fees)
    trade_lines = []
    for t in recent[-15:]:
        hold_min = t.get("hold_seconds", 0) / 60
        fees = t.get("fees", 0)
        gross = t.get("gross_pnl", t.get("pnl", 0))
        sentinel_info = ""
        sd = t.get("sentinel_decisions", [])
        if sd:
            actions = [d.get("action", "?") for d in sd]
            sentinel_info = f" sentinel=[{','.join(actions)}]"
        trade_lines.append(
            f"  #{t.get('id')} {t.get('pair')} {t.get('side')} "
            f"PnL=${t.get('pnl', 0):.4f} (gross=${gross:.4f} fees=${fees:.4f}) "
            f"reason={t.get('reason')} strategy={t.get('strategy')} "
            f"score={t.get('score', 0)} hold={hold_min:.1f}min{sentinel_info}"
        )

    # Quick loss analysis
    losses = [t for t in recent if t.get("pnl", 0) <= 0]
    quick_losses = sum(1 for t in losses if t.get("hold_seconds", 999) <= 120)
    quick_pct = (quick_losses / len(losses) * 100) if losses else 0

    # Shared context section
    ctx_lines = []
    if context:
        m = context.market
        ctx_lines.append(f"  Régimen actual: {m.get('regime', '?')}")
        ctx_lines.append(f"  Volatilidad: {m.get('volatility', '?')}")
        ctx_lines.append(f"  BTC trend: {m.get('btc_trend', 'N/A')}")
        if context.directives:
            ctx_lines.append(f"  Directivas activas: {'; '.join(context.directives)}")
        if context.biases:
            for pair, bias in context.biases.items():
                ctx_lines.append(f"  Bias {pair}: {bias.get('direction')} "
                                 f"(conf={bias.get('confidence')}, {bias.get('reason', '')})")

        # Sentinel effectiveness
        sentinel_trades = [t for t in recent if t.get("sentinel_decisions")]
        if sentinel_trades:
            st_wins = sum(1 for t in sentinel_trades if t.get("pnl", 0) > 0)
            st_wr = st_wins / len(sentinel_trades) * 100
            ctx_lines.append(f"  Sentinel intervino en {len(sentinel_trades)} trades, "
                             f"WR={st_wr:.0f}%")

        # Last 10 sentinel observations
        obs = context.observations[-10:]
        if obs:
            ctx_lines.append("  Últimas observaciones Sentinel:")
            for o in obs:
                ctx_lines.append(f"    [{o.get('time')}] {o.get('note', '')}")

        sp = context.sentinel_params
        ctx_lines.append(f"  Sentinel params: aggression={sp.get('aggression')}, "
                         f"interval={sp.get('check_interval_min')}min, "
                         f"max_interventions={sp.get('max_interventions')}")

    ctx_text = "\n".join(ctx_lines) if ctx_lines else "  Sin contexto compartido"

    return f"""ESTADO ACTUAL DEL BOT:
Total trades: {stats['total']}, Wins: {stats['wins']}, WR: {stats['win_rate']}%
PnL neto: ${stats['total_pnl']}, PnL bruto: ${stats.get('gross_pnl', 'N/A')}, Fees pagados: ${stats.get('total_fees', 'N/A')}
Avg PnL: ${stats['avg_pnl']}, Mejor trade: ${stats['best']}, Peor trade: ${stats['worst']}
Streak actual: {brain_summary['streak']}, Evoluciones: {brain_summary['evolve_count']}
NOTA: Los fees son ~$0.095/trade (Bitget 0.06% taker × 2 lados). Con margen de ~$10, el bot necesita >0.95% por trade solo para cubrir fees.

PARÁMETROS ACTUALES:
  sl_atr_mult: {params.get('sl_atr_mult')}
  tp_atr_mult: {params.get('tp_atr_mult')}
  leverage_default: {params.get('leverage_default')}
  min_score: {params.get('min_score')}
  trailing_trigger_pct: {params.get('trailing_trigger_pct')}
  trailing_distance_pct: {params.get('trailing_distance_pct')}
NOTA: Los cambios de parámetros tienen cooldown de 3 horas. No propongas cambiar un param que se cambió recientemente.
{_format_param_ages(brain)}

ESTRATEGIAS:
{chr(10).join(strat_lines) or '  (sin datos)'}

PARES:
{chr(10).join(pair_lines) or '  (sin datos)'}
Killed pairs: {brain.killed_pairs}
Killed strategies: {brain.killed_strategies}

ANÁLISIS DE PÉRDIDAS RÁPIDAS (<=2min):
  {quick_losses}/{len(losses)} losses = {quick_pct:.0f}% son rápidas

CONTEXTO COMPARTIDO:
{ctx_text}

ÚLTIMOS 15 TRADES:
{chr(10).join(trade_lines) or '  (sin trades)'}

Analiza todo y decide qué cambios hacer. Incluye directivas para Sentinel y biases si tienes observaciones relevantes."""


def _apply_llm_decisions(brain: Brain, journal: Journal, decisions: dict,
                         changes: list, context=None):
    """Apply Opus decisions to brain state and shared context."""
    sw = brain.data.get("strategy_weights", {})
    killed_strats = brain.data.setdefault("killed_strategies", [])
    killed_pairs = brain.data.setdefault("killed_pairs", [])

    # 1. Strategy decisions
    for strat_dec in decisions.get("strategies", []):
        name = strat_dec.get("name", "")
        action = strat_dec.get("action", "hold")
        reason = strat_dec.get("reason", "")
        if name not in sw:
            continue

        if action == "kill":
            for regime in sw[name]:
                sw[name][regime] = max(sw[name][regime] * 0.7, 0.2)
            if name not in killed_strats:
                killed_strats.append(name)
            changes.append(f"KILL strategy {name} ({reason})")

        elif action == "boost":
            for regime in sw[name]:
                sw[name][regime] = min(sw[name][regime] * 1.15, 1.5)
            if name in killed_strats:
                killed_strats.remove(name)
            changes.append(f"BOOST strategy {name} ({reason})")

    # 2. Pair decisions
    for pair_dec in decisions.get("pairs", []):
        name = pair_dec.get("name", "")
        action = pair_dec.get("action", "hold")
        reason = pair_dec.get("reason", "")

        if action == "kill" and name not in killed_pairs:
            killed_pairs.append(name)
            changes.append(f"KILL pair {name} ({reason})")

        elif action == "resurrect" and name in killed_pairs:
            killed_pairs.remove(name)
            changes.append(f"RESURRECT pair {name} ({reason})")

    # 3. Parameter adjustments
    params = brain.data.get("params", {})
    param_ranges = {
        "sl_atr_mult": (1.8, 3.0),
        "tp_atr_mult": (2.0, 5.0),
        "leverage_default": (3, 10),
        "min_score": (40, 70),
        "trailing_trigger_pct": (0.3, 1.5),
        "trailing_distance_pct": (25, 60),
    }
    import time as _time
    param_changed_at = brain.data.setdefault("param_changed_at", {})
    now = _time.time()
    for key, new_val in decisions.get("params", {}).items():
        if new_val is None or key not in params:
            continue
        lo, hi = param_ranges.get(key, (None, None))
        try:
            new_val = type(params[key])(new_val)
        except (ValueError, TypeError):
            continue
        if lo is not None:
            new_val = max(lo, min(hi, new_val))
        old = params[key]
        if new_val != old:
            # Anti-oscillation: skip if param was changed < 3 hours ago
            last_changed = param_changed_at.get(key, 0)
            hours_since = (now - last_changed) / 3600
            if hours_since < 3:
                logger.info(f"Darwin: SKIP {key} change ({old} → {new_val}), "
                            f"changed {hours_since:.1f}h ago (cooldown 3h)")
                continue
            params[key] = new_val
            param_changed_at[key] = now
            changes.append(f"ADJUST {key}: {old} → {new_val}")

    # 4. Shared context updates
    if context:
        # Directives
        directives = decisions.get("directives")
        if directives and isinstance(directives, list):
            context.set_directives(directives)
            changes.append(f"DIRECTIVES: {len(directives)} set")

        # Biases
        biases = decisions.get("biases")
        if biases and isinstance(biases, dict):
            for pair, bias in biases.items():
                if isinstance(bias, dict) and "direction" in bias:
                    context.set_bias(
                        pair,
                        bias["direction"],
                        bias.get("confidence", 0.5),
                        bias.get("reason", ""),
                    )
            changes.append(f"BIASES: {len(biases)} updated")

        # Market
        market = decisions.get("market")
        if market and isinstance(market, dict):
            context.update_market(
                regime=market.get("regime"),
                btc_trend=market.get("btc_trend"),
                volatility=market.get("volatility"),
                updated_by="darwin",
            )
            changes.append(f"MARKET: regime={market.get('regime')}, "
                           f"vol={market.get('volatility')}")

        # Sentinel adjustments
        sentinel_adj = decisions.get("sentinel_adjustments")
        if sentinel_adj and isinstance(sentinel_adj, dict):
            # Filter out null values
            updates = {k: v for k, v in sentinel_adj.items() if v is not None}
            if updates:
                context.update_sentinel_params(**updates)
                changes.append(f"SENTINEL: {updates}")

    # 5. Log summary
    summary = decisions.get("summary", "")
    if summary:
        changes.append(f"OPUS: {summary}")


async def darwin_cycle(brain: Brain, journal: Journal, llm=None, context=None):
    """One cycle of Darwinian evolution. Called hourly.

    Requires Claude Opus. If LLM unavailable or fails, skips the cycle.
    """
    if not llm:
        logger.info("Darwin: no LLM client, skipping")
        return

    recent = journal.get_recent(30)
    if len(recent) < 5:
        logger.info("Darwin: not enough trades yet, skipping")
        return

    changes = []

    try:
        prompt = _build_darwin_prompt(brain, journal, recent, context)
        response = await llm.generate(
            system=DARWIN_SYSTEM,
            user_message=prompt,
            model=DARWIN_MODEL,
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        decisions = json.loads(raw)
        _apply_llm_decisions(brain, journal, decisions, changes, context)
        logger.info(f"Darwin: Opus analysis complete (model={response.model})")
    except Exception as e:
        logger.warning(f"Darwin: Opus failed ({e}), skipping cycle")
        return

    if changes:
        brain.save()
        for c in changes:
            logger.info(f"Darwin: {c}")

    # Add Darwin observation to context
    if context and changes:
        summary = "; ".join(c for c in changes if not c.startswith("OPUS:"))
        if summary:
            context.add_observation("darwin", summary[:200])

    return changes


def _rules_fallback(brain: Brain, journal: Journal, recent: list, changes: list):
    """Original rule-based Darwin logic (fallback when LLM unavailable)."""
    _evolve_strategies(brain, recent, changes)
    _evolve_pairs(brain, journal, changes)
    _adjust_sl(brain, recent, changes)
    _adjust_leverage(brain, changes)


# ------------------------------------------------------------------
# Rule-based helpers (unchanged)
# ------------------------------------------------------------------

def _evolve_strategies(brain: Brain, recent: list, changes: list):
    """Kill or boost strategies."""
    sw = brain.data.get("strategy_weights", {})
    killed = brain.data.setdefault("killed_strategies", [])

    for strategy in list(sw.keys()):
        strat_trades = [t for t in recent if t.get("strategy") == strategy]
        if len(strat_trades) < 10:
            continue
        wins = sum(1 for t in strat_trades if t.get("pnl", 0) > 0)
        wr = wins / len(strat_trades)
        total_pnl = sum(t.get("pnl", 0) for t in strat_trades)

        if wr < 0.25 and total_pnl < 0:
            for regime in sw[strategy]:
                sw[strategy][regime] = max(sw[strategy][regime] * 0.7, 0.2)
            if strategy not in killed:
                killed.append(strategy)
            changes.append(f"KILL strategy {strategy} (WR={wr:.0%}, PnL=${total_pnl:.2f})")

        elif wr >= 0.4:
            for regime in sw[strategy]:
                sw[strategy][regime] = min(sw[strategy][regime] * 1.15, 2.5)
            if strategy in killed:
                killed.remove(strategy)
            changes.append(f"BOOST strategy {strategy} (WR={wr:.0%})")


def _evolve_pairs(brain: Brain, journal: Journal, changes: list):
    """Kill or resurrect pairs."""
    killed = brain.data.setdefault("killed_pairs", [])
    all_trades = journal.get_all()

    pairs_seen = set()
    for t in all_trades:
        p = t.get("pair")
        if p:
            pairs_seen.add(p)

    for pair in pairs_seen:
        stats = journal.get_stats_for_pair(pair)
        total = stats["total"]
        wr = stats["win_rate"] / 100 if stats["win_rate"] else 0

        if total >= 8 and wr < 0.20 and pair not in killed:
            killed.append(pair)
            changes.append(f"KILL pair {pair} (WR={wr:.0%}, {total} trades)")

    recent = journal.get_recent(15)
    for pair in list(killed):
        pair_recent = [t for t in recent if t.get("pair") == pair]
        if len(pair_recent) >= 3:
            wins = sum(1 for t in pair_recent if t.get("pnl", 0) > 0)
            if wins / len(pair_recent) > 0.35:
                killed.remove(pair)
                changes.append(f"RESURRECT pair {pair} (recent WR improved)")


def _adjust_sl(brain: Brain, recent: list, changes: list):
    """Adjust SL multiplier based on quick losses."""
    losses = [t for t in recent if t.get("pnl", 0) <= 0]
    if not losses:
        return

    quick = sum(1 for t in losses
                if t.get("hold_seconds", 999) <= 120)
    quick_pct = quick / len(losses) if losses else 0

    params = brain.data.get("params", {})
    sl = params.get("sl_atr_mult", 2.2)

    if quick_pct > 0.30:
        new_sl = min(sl * 1.15, 3.0)
        if new_sl != sl:
            params["sl_atr_mult"] = round(new_sl, 2)
            changes.append(f"WIDEN SL: {sl:.2f} → {new_sl:.2f} (quick_loss={quick_pct:.0%})")
    elif quick_pct < 0.10 and sl > 1.8:
        new_sl = max(sl * 0.95, 1.8)
        if new_sl != sl:
            params["sl_atr_mult"] = round(new_sl, 2)
            changes.append(f"TIGHTEN SL: {sl:.2f} → {new_sl:.2f} (quick_loss={quick_pct:.0%})")


def _adjust_leverage(brain: Brain, changes: list):
    """Adjust leverage based on streak."""
    stats = brain.stats
    streak = stats.get("streak", 0)
    params = brain.data.get("params", {})
    lev = params.get("leverage_default", 8)
    min_lev = CONFIG.get("leverage_min", 3)
    max_lev = CONFIG.get("leverage_max", 10)

    if streak <= -5:
        new_lev = max(lev - 2, min_lev)
        if new_lev != lev:
            params["leverage_default"] = new_lev
            changes.append(f"REDUCE leverage: {lev}x → {new_lev}x (losing streak={streak})")
    elif streak >= 4:
        new_lev = min(lev + 1, max_lev)
        if new_lev != lev:
            params["leverage_default"] = new_lev
            changes.append(f"INCREASE leverage: {lev}x → {new_lev}x (winning streak={streak})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    brain = Brain()
    brain.load()
    journal = Journal()
    journal.load()
    import asyncio
    asyncio.run(darwin_cycle(brain, journal))
