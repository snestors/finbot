"""Trading bot orchestrator — one cycle per minute.

v2: Sentinel monitor, pre-trade filter, fee-aware trailing, shared context.
"""
import json
import logging
import time

from trading.config import CONFIG
from trading.exchange import Exchange
from trading.signals import generate_signals, detect_regime
from trading.brain import Brain
from trading.journal import Journal
from trading.state import State
from trading.context import SharedContext
from trading.sentinel import sentinel_check

logger = logging.getLogger(__name__)

PRETRADE_MODEL = "claude-opus-4-6"

PRETRADE_SYSTEM = """Eres el filtro pre-trade de un bot de trading de futuros crypto.
Tu trabajo: decidir si una señal de trading debe ejecutarse o bloquearse.

Considera:
- El bias de Darwin para este par (si existe)
- El régimen de mercado actual
- Las directivas estratégicas de Darwin
- La calidad de la señal (score, estrategia)

Responde SOLO con JSON válido:
{"allow": true, "reason": "breve explicación"}
o
{"allow": false, "reason": "breve explicación"}

Sé permisivo: en caso de duda, permite el trade. Solo bloquea si hay contradicción clara
(ej: señal long pero Darwin dice bearish con alta confianza)."""


class TradingBot:
    """Main trading bot. Call run() or run_with_sentinel() every minute."""

    def __init__(self, api_key: str = "", secret: str = "", passphrase: str = "",
                 paper_mode: bool = True):
        self.brain = Brain()
        self.journal = Journal()
        self.state = State()
        self.context = SharedContext()
        self.exchange = Exchange(
            api_key=api_key,
            secret=secret,
            passphrase=passphrase,
            paper_mode=paper_mode,
        )
        self._loaded = False
        # Sentinel state (per-position, reset on new trade)
        self._sentinel_last_check = 0
        self._sentinel_interventions = 0
        self._sentinel_decisions = []
        # Activity log (ring buffer, max 50 entries)
        self._activity_log: list[dict] = []
        self._activity_max = 50

    def _log_activity(self, event: str, detail: str = "", **extra):
        """Append to activity ring buffer."""
        from datetime import datetime, timezone, timedelta
        lima_tz = timezone(timedelta(hours=-5))
        entry = {
            "time": datetime.now(lima_tz).strftime("%H:%M:%S"),
            "ts": time.time(),
            "event": event,
            "detail": detail,
            **extra,
        }
        self._activity_log.append(entry)
        if len(self._activity_log) > self._activity_max:
            self._activity_log = self._activity_log[-self._activity_max:]

    def _ensure_loaded(self):
        """Lazy load persistent data."""
        if not self._loaded:
            self.brain.load()
            self.journal.load()
            self.state.load()
            self.context.load()
            # Exchange is the single source of truth for paper_mode
            self.state.paper_mode = self.exchange.paper_mode
            self._loaded = True

    # ------------------------------------------------------------------
    # Main cycle (sync, backward compatible)
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute one complete cycle (sync). Returns status dict."""
        self._ensure_loaded()
        self.state.data["last_run"] = time.time()
        self.state.save()

        if self.state.paused:
            return {"action": "skip", "reason": "paused"}
        if self.state.is_globally_cooled_down():
            return {"action": "skip", "reason": "global_cooldown"}

        pos = self.state.position
        if pos:
            return self._monitor_position(pos)
        return self._scan_and_open()

    # ------------------------------------------------------------------
    # Main cycle v2 (async, with Sentinel + pre-trade filter)
    # ------------------------------------------------------------------

    async def run_with_sentinel(self, llm=None) -> dict:
        """Execute one cycle with Sentinel monitor and pre-trade filter."""
        self._ensure_loaded()
        self.state.data["last_run"] = time.time()
        self.state.save()

        if self.state.paused:
            return {"action": "skip", "reason": "paused"}
        if self.state.is_globally_cooled_down():
            return {"action": "skip", "reason": "global_cooldown"}

        pos = self.state.position
        if pos:
            # Normal monitor first
            result = self._monitor_position(pos)

            # If still monitoring (not closed), maybe run Sentinel
            # Skip sentinel during grace period — trade needs time to develop
            if (result.get("action") == "monitoring"
                    and result.get("reason") != "grace_period"
                    and llm):
                sentinel_result = await self._maybe_run_sentinel(pos, llm)
                if sentinel_result:
                    return sentinel_result

            return result

        # No position: scan with pre-trade filter
        return await self._scan_and_open_v2(llm)

    # ------------------------------------------------------------------
    # Position monitoring
    # ------------------------------------------------------------------

    def _monitor_position(self, pos: dict) -> dict:
        """Monitor open position: trailing, SL/TP, grace period."""
        pair = pos["pair"]

        # Grace period: don't close within first 2 minutes
        open_time = pos.get("open_time", 0)
        elapsed = time.time() - open_time
        grace = CONFIG.get("grace_period_min", 2) * 60
        if elapsed < grace:
            return {"action": "monitoring", "reason": "grace_period",
                    "elapsed_s": round(elapsed)}

        # Get current price
        candles = self.exchange.fetch_candles(pair, "1m", 1)
        if not candles:
            return {"action": "monitoring", "reason": "no_price_data"}
        current_price = candles[-1][4]

        # Calculate PnL %
        entry = pos["entry_price"]
        if pos["side"] == "long":
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100

        leverage = pos.get("leverage", 8)
        pnl_pct_leveraged = pnl_pct * leverage

        # Calculate actual PnL in USD
        margin = pos.get("margin", 0)
        pnl_usd = margin * (pnl_pct_leveraged / 100)

        # Fee-aware trailing stop
        params = self.brain.params
        trailing_trigger = params.get("trailing_trigger_pct", 0.5)

        # Use sentinel override if set
        override = pos.get("trailing_trigger_override")
        if override is not None:
            trailing_trigger = override

        should_close = self.state.update_trailing(
            pnl_pct_leveraged,
            trailing_trigger,
            params.get("trailing_distance_pct", 40),
        )
        if should_close:
            # Fee-aware check: if net PnL after fees is negative, skip trailing
            open_fee = pos.get("open_fee", 0.05)
            estimated_fees = open_fee + 0.05  # actual open + estimated close
            net_pnl_est = pnl_usd - estimated_fees
            if net_pnl_est < 0:
                logger.info(f"Trailing skip: net_pnl_est=${net_pnl_est:.4f} < 0 "
                            f"(fees ~${estimated_fees:.3f}), letting SL/TP handle")
                # Reset trailing to prevent re-triggering immediately
                pos["trailing_active"] = False
                pos["peak_pnl_pct"] = 0
                self.state.save()
            else:
                return self._close_trade(pair, pnl_usd, "trailing_stop", current_price)

        # Check SL hit
        if pos["side"] == "long" and current_price <= pos["sl"]:
            return self._close_trade(pair, pnl_usd, "stop_loss", current_price)
        if pos["side"] == "short" and current_price >= pos["sl"]:
            return self._close_trade(pair, pnl_usd, "stop_loss", current_price)

        # Check TP hit
        if pos["side"] == "long" and current_price >= pos["tp"]:
            return self._close_trade(pair, pnl_usd, "take_profit", current_price)
        if pos["side"] == "short" and current_price <= pos["tp"]:
            return self._close_trade(pair, pnl_usd, "take_profit", current_price)

        short_pair = pair.split("/")[0]
        trail = " TRAIL" if pos.get("trailing_active") else ""
        peak = pos.get("peak_pnl_pct", 0)
        logger.info(f"Monitor: {pos['side']} {short_pair} "
                     f"PnL={pnl_pct_leveraged:+.2f}% (${pnl_usd:+.4f}) "
                     f"peak={peak:.2f}%{trail}")
        self._log_activity("monitor", f"{pos['side']} {short_pair} "
                           f"PnL={pnl_pct_leveraged:+.2f}% (${pnl_usd:+.4f}){trail}")
        return {"action": "monitoring", "pair": pair,
                "pnl_pct": round(pnl_pct_leveraged, 2),
                "pnl_usd": round(pnl_usd, 4),
                "trailing_active": pos.get("trailing_active", False)}

    # ------------------------------------------------------------------
    # Sentinel integration
    # ------------------------------------------------------------------

    async def _maybe_run_sentinel(self, pos: dict, llm) -> dict | None:
        """Run Sentinel check if enough time has passed. Returns result or None."""
        sp = self.context.sentinel_params
        interval = sp.get("check_interval_min",
                          CONFIG.get("sentinel_check_interval_min", 5)) * 60
        max_interventions = sp.get("max_interventions",
                                   CONFIG.get("sentinel_max_interventions", 3))

        now = time.time()
        if now - self._sentinel_last_check < interval:
            return None
        if self._sentinel_interventions >= max_interventions:
            return None

        self._sentinel_last_check = now
        journal_recent = self.journal.get_recent(10)

        decision = await sentinel_check(
            pos, self.exchange, self.context, journal_recent, llm,
        )
        if not decision:
            return None

        action = decision["action"]
        self._sentinel_decisions.append({
            "time": time.time(),
            "action": action,
            "reason": decision.get("reason", ""),
        })

        # Write observation to shared context
        obs = decision.get("observation")
        if obs:
            self.context.add_observation("sentinel", obs)

        if action == "HOLD":
            logger.info(f"Sentinel: HOLD — {decision.get('reason', '')}")
            self._log_activity("sentinel", "HOLD", reason=decision.get("reason", ""))
            return None

        self._sentinel_interventions += 1
        pair = pos["pair"]

        if action == "TIGHTEN":
            new_sl = decision["new_sl"]
            old_sl = pos["sl"]
            pos["sl"] = new_sl
            self.state.save()
            logger.info(f"Sentinel: TIGHTEN SL {old_sl:.6f} → {new_sl:.6f}")
            short_pair = pair.split("/")[0]
            self._log_activity("sentinel", f"TIGHTEN {short_pair} SL {old_sl:.4f} → {new_sl:.4f}",
                               reason=decision.get("reason", ""))
            return {"action": "sentinel_tighten", "pair": pair,
                    "old_sl": old_sl, "new_sl": new_sl,
                    "reason": decision.get("reason", "")}

        if action == "CLOSE":
            # Calculate PnL for close
            candles = self.exchange.fetch_candles(pair, "1m", 1)
            if not candles:
                return None
            current_price = candles[-1][4]
            entry = pos["entry_price"]
            leverage = pos.get("leverage", 8)
            margin = pos.get("margin", 0)
            if pos["side"] == "long":
                pnl_pct = (current_price - entry) / entry * 100
            else:
                pnl_pct = (entry - current_price) / entry * 100
            pnl_usd = margin * (pnl_pct * leverage / 100)
            logger.info(f"Sentinel: CLOSE — {decision.get('reason', '')}")
            short_pair = pair.split("/")[0]
            self._log_activity("sentinel", f"CLOSE {short_pair}",
                               reason=decision.get("reason", ""))
            return self._close_trade(pair, pnl_usd, "sentinel_close", current_price)

        if action == "LET_RUN":
            old_trigger = self.brain.params.get("trailing_trigger_pct", 0.5)
            new_trigger = old_trigger * 1.5
            pos["trailing_trigger_override"] = new_trigger
            self.state.save()
            logger.info(f"Sentinel: LET_RUN — trailing trigger {old_trigger} → {new_trigger}")
            short_pair = pair.split("/")[0]
            self._log_activity("sentinel", f"LET_RUN {short_pair} trailing {old_trigger}% → {new_trigger:.1f}%",
                               reason=decision.get("reason", ""))
            return {"action": "sentinel_let_run", "pair": pair,
                    "new_trailing_trigger": new_trigger,
                    "reason": decision.get("reason", "")}

        return None

    # ------------------------------------------------------------------
    # Pre-trade filter
    # ------------------------------------------------------------------

    async def _pretrade_check(self, signal, llm) -> dict:
        """Pre-trade filter using Opus. Returns {"allow": bool, "reason": str}."""
        if not llm:
            return {"allow": True, "reason": "no_llm"}

        bias = self.context.get_bias(signal.pair)
        bias_text = (f"Bias Darwin: {bias['direction']} "
                     f"(confianza={bias['confidence']}, {bias['reason']})"
                     if bias else "Sin bias para este par")

        prompt = f"""SEÑAL:
  Par: {signal.pair}
  Dirección: {signal.direction}
  Score: {signal.score}
  Estrategia: {signal.strategy}
  Indicadores: {json.dumps(signal.indicators)}

CONTEXTO:
  Régimen: {self.context.regime}
  {bias_text}
  Directivas: {'; '.join(self.context.directives) if self.context.directives else 'Ninguna'}

¿Permitir este trade?"""

        try:
            response = await llm.generate(
                system=PRETRADE_SYSTEM,
                user_message=prompt,
                model=PRETRADE_MODEL,
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
            result = json.loads(raw)
            allow = result.get("allow", True)
            reason = result.get("reason", "")
            logger.info(f"Pre-trade {'ALLOWED' if allow else 'BLOCKED'}: "
                        f"{signal.pair} {signal.direction} — {reason}")
            return {"allow": allow, "reason": reason}
        except Exception as e:
            logger.warning(f"Pre-trade filter failed ({e}), allowing trade (fail-open)")
            return {"allow": True, "reason": f"filter_error: {e}"}

    # ------------------------------------------------------------------
    # Close trade
    # ------------------------------------------------------------------

    def _close_trade(self, pair: str, pnl: float, reason: str,
                     exit_price: float) -> dict:
        """Close position and record in journal."""
        pos = self.state.position
        self.exchange.close_position(pair, reason)

        # Fetch closing fee and add opening fee
        close_fee = self.exchange.fetch_last_trade_fee(pair)
        open_fee = pos.get("open_fee", 0.0)
        total_fee = round(open_fee + close_fee, 6)

        # Deduct fees from PnL
        net_pnl = round(pnl - total_fee, 4)

        hold_seconds = time.time() - pos.get("open_time", time.time())

        trade = {
            "pair": pair,
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "pnl": net_pnl,
            "gross_pnl": round(pnl, 4),
            "fees": total_fee,
            "reason": reason,
            "strategy": pos.get("strategy", "unknown"),
            "score": pos.get("score", 0),
            "leverage": pos.get("leverage", 8),
            "hold_seconds": round(hold_seconds),
            "paper": pos.get("paper", True),
        }

        # Save sentinel decisions if any
        if self._sentinel_decisions:
            trade["sentinel_decisions"] = list(self._sentinel_decisions)

        self.journal.record(trade)

        # Update brain (pass recent trades separately)
        self.brain.update_after_trade(trade, self.journal.get_recent(30))

        # Track streaks (based on net PnL after fees)
        if net_pnl > 0:
            self.state.record_win()
        else:
            self.state.record_loss()

        self.state.close_position()

        # Cooldown on this pair
        self.state.set_cooldown(pair, CONFIG.get("cooldown_candles", 3))

        logger.info(f"Trade closed: {pair} {pos['side']} "
                     f"gross=${pnl:.4f} fees=${total_fee:.4f} net=${net_pnl:.4f} "
                     f"reason={reason} hold={hold_seconds:.0f}s")

        short_pair = pair.split("/")[0]
        self._log_activity("close", f"{short_pair} {pos['side']} ${net_pnl:+.4f}",
                           reason=reason, gross=round(pnl, 4), fees=round(total_fee, 4))

        return {"action": "closed", "trade": trade}

    # ------------------------------------------------------------------
    # Signal scanning (v1 sync, backward compatible)
    # ------------------------------------------------------------------

    def _scan_and_open(self) -> dict:
        """Scan all pairs for signals and open best one (sync, no filter)."""
        candidate = self._scan_for_candidate()
        if not candidate:
            return {"action": "no_signal", "scanned": len(CONFIG.get("pairs", []))}
        return self._open_trade(candidate)

    # ------------------------------------------------------------------
    # Signal scanning v2 (async, with pre-trade filter + regime)
    # ------------------------------------------------------------------

    async def _scan_and_open_v2(self, llm=None) -> dict:
        """Scan with regime detection + pre-trade filter."""
        candidate = self._scan_for_candidate()
        if not candidate:
            return {"action": "no_signal", "scanned": len(CONFIG.get("pairs", []))}

        # Hard regime filter (deterministic, no LLM needed)
        regime = self.context.regime
        contra_score_min = CONFIG.get("contra_trend_min_score", 135)
        if (regime == "trending_up" and candidate.direction == "short"
                and candidate.score < contra_score_min):
            reason = (f"Hard filter: short in trending_up needs score >= "
                      f"{contra_score_min}, got {candidate.score:.1f}")
            logger.info(f"Pre-trade BLOCKED (hard): {candidate.pair} "
                        f"{candidate.direction} — {reason}")
            short_pair = candidate.pair.split("/")[0]
            self._log_activity("blocked", f"{candidate.direction} {short_pair} score={candidate.score:.0f}",
                               reason=reason, filter="hard")
            return {"action": "pretrade_blocked", "pair": candidate.pair,
                    "direction": candidate.direction,
                    "score": candidate.score, "reason": reason}
        if (regime == "trending_down" and candidate.direction == "long"
                and candidate.score < contra_score_min):
            reason = (f"Hard filter: long in trending_down needs score >= "
                      f"{contra_score_min}, got {candidate.score:.1f}")
            logger.info(f"Pre-trade BLOCKED (hard): {candidate.pair} "
                        f"{candidate.direction} — {reason}")
            short_pair = candidate.pair.split("/")[0]
            self._log_activity("blocked", f"{candidate.direction} {short_pair} score={candidate.score:.0f}",
                               reason=reason, filter="hard")
            return {"action": "pretrade_blocked", "pair": candidate.pair,
                    "direction": candidate.direction,
                    "score": candidate.score, "reason": reason}

        # LLM pre-trade filter (nuanced check)
        if llm:
            check = await self._pretrade_check(candidate, llm)
            if not check.get("allow", True):
                logger.info(f"Pre-trade BLOCKED: {candidate.pair} "
                            f"{candidate.direction} — {check.get('reason', '')}")
                short_pair = candidate.pair.split("/")[0]
                self._log_activity("blocked", f"{candidate.direction} {short_pair} score={candidate.score:.0f}",
                                   reason=check.get("reason", ""), filter="llm")
                return {"action": "pretrade_blocked", "pair": candidate.pair,
                        "direction": candidate.direction,
                        "score": candidate.score,
                        "reason": check.get("reason", "")}

        return self._open_trade(candidate)

    def _scan_for_candidate(self):
        """Scan all pairs for signals, return best candidate or None."""
        pairs = CONFIG.get("pairs", [])
        killed_pairs = self.brain.killed_pairs

        # Detect regime from BTC candles
        btc_candles = self.exchange.fetch_candles("BTC/USDT:USDT", "5m", 60)
        regime = detect_regime(btc_candles) if btc_candles else self.context.regime
        if regime != self.context.regime:
            self.context.update_market(regime=regime, updated_by="signals")
            logger.info(f"Regime detected: {regime}")

        brain_weights = self.brain.get_weights_for_regime(regime)
        min_score = self.brain.params.get("min_score", CONFIG["min_score"])

        all_signals = []
        scan_details = []
        for pair in pairs:
            short_pair = pair.split("/")[0]
            if pair in killed_pairs:
                scan_details.append(f"{short_pair}:KILLED")
                continue
            if self.state.is_on_cooldown(pair):
                scan_details.append(f"{short_pair}:COOLDOWN")
                continue

            candles = self.exchange.fetch_candles(
                pair,
                CONFIG.get("candle_tf", "5m"),
                CONFIG.get("candle_count", 60),
            )
            if not candles:
                scan_details.append(f"{short_pair}:NO_DATA")
                continue

            signals = generate_signals(pair, candles, brain_weights)
            if signals:
                best_sig = max(signals, key=lambda s: s.score)
                scan_details.append(
                    f"{short_pair}:{best_sig.direction}={best_sig.score:.0f}"
                    f"({best_sig.strategy[:4]})"
                )
            else:
                scan_details.append(f"{short_pair}:NO_SIGNAL")
            all_signals.extend(signals)

        candidates = [s for s in all_signals if s.score >= min_score]

        summary = " | ".join(scan_details)
        if not candidates:
            logger.info(f"Scan[{regime}]: {summary} → sin candidatos (min={min_score})")
            self._log_activity("scan", f"[{regime}] {summary}", result="no_signal",
                               min_score=min_score)
            return None

        best = max(candidates, key=lambda s: s.score)
        short_best = best.pair.split("/")[0]
        logger.info(f"Scan[{regime}]: {summary} → CANDIDATE {best.direction} "
                     f"{short_best} score={best.score:.1f}")
        self._log_activity("scan", f"[{regime}] {summary}",
                           result="candidate", candidate=f"{best.direction} {short_best}",
                           score=best.score)
        return best

    def _open_trade(self, signal) -> dict:
        """Open a position based on signal."""
        pair = signal.pair
        atr = signal.indicators.get("atr", 0)
        params = self.brain.params

        # Calculate SL/TP from ATR
        candles = self.exchange.fetch_candles(pair, "1m", 1)
        if not candles:
            return {"action": "error", "reason": "no_price_for_entry"}
        price = candles[-1][4]

        sl_dist = atr * params.get("sl_atr_mult", CONFIG["sl_atr_mult"])
        tp_dist = atr * params.get("tp_atr_mult", CONFIG["tp_atr_mult"])

        # Clamp SL
        sl_pct = sl_dist / price if price > 0 else 0.01
        sl_pct = max(sl_pct, CONFIG["sl_min_pct"])
        sl_pct = min(sl_pct, CONFIG["sl_max_pct"])
        sl_dist = price * sl_pct

        if signal.direction == "long":
            sl = price - sl_dist
            tp = price + tp_dist
        else:
            sl = price + sl_dist
            tp = price - tp_dist

        # Position sizing
        balance = self.exchange.fetch_balance()
        margin = balance * CONFIG.get("margin_pct", 0.5)
        leverage = params.get("leverage_default", CONFIG["leverage_default"])

        if margin < 1:
            return {"action": "skip", "reason": "insufficient_balance",
                    "balance": balance}

        # Open on exchange
        result = self.exchange.open_position(
            pair=pair,
            side=signal.direction,
            margin=margin,
            leverage=leverage,
            sl=sl,
            tp=tp,
            entry_price=price,
        )
        if not result:
            return {"action": "error", "reason": "exchange_open_failed"}

        # Fetch opening fee from exchange
        open_fee = self.exchange.fetch_last_trade_fee(pair)

        # Record in state
        self.state.open_position(
            pair=pair,
            side=signal.direction,
            entry_price=price,
            sl=sl,
            tp=tp,
            margin=margin,
            leverage=leverage,
            strategy=signal.strategy,
            score=signal.score,
            paper=self.exchange.paper_mode,
            open_fee=open_fee,
        )

        # Reset sentinel state for new position
        # Use time.time() so sentinel waits check_interval_min before first check
        self._sentinel_last_check = time.time()
        self._sentinel_interventions = 0
        self._sentinel_decisions = []

        logger.info(f"Opened {signal.direction} {pair} @ {price:.4f} "
                     f"score={signal.score} strategy={signal.strategy} "
                     f"SL={sl:.4f} TP={tp:.4f} fee=${open_fee:.4f}")

        short_pair = pair.split("/")[0]
        self._log_activity("open", f"{signal.direction.upper()} {short_pair} @ {price:.4f}",
                           score=signal.score, strategy=signal.strategy)

        return {"action": "opened", "pair": pair, "side": signal.direction,
                "price": price, "score": signal.score,
                "strategy": signal.strategy, "sl": sl, "tp": tp,
                "margin": margin, "leverage": leverage}

    # ------------------------------------------------------------------
    # API for KYN3D agent
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Full status for the trading agent."""
        self._ensure_loaded()
        return {
            "state": self.state.summary(),
            "brain": self.brain.summary(),
            "journal_stats": self.journal.get_stats(),
            "recent_trades": self.journal.get_recent(10),
            "balance": self.exchange.fetch_equity(),
            "config": {k: v for k, v in CONFIG.items() if k != "paper_mode"},
            "context": self.context.summary(),
            "activity": self._activity_log[-30:],
        }

    def get_brain(self) -> dict:
        self._ensure_loaded()
        return self.brain.summary()

    def get_journal_stats(self) -> dict:
        self._ensure_loaded()
        return self.journal.get_stats()

    def pause(self):
        self._ensure_loaded()
        self.state.paused = True
        logger.info("Trading bot PAUSED")

    def resume(self):
        self._ensure_loaded()
        self.state.paused = False
        logger.info("Trading bot RESUMED")

    def set_param(self, key: str, value) -> bool:
        """Update a brain parameter. Returns True if valid."""
        self._ensure_loaded()
        return self.brain.set_param(key, value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    bot = TradingBot(paper_mode=True)
    result = bot.run()
    print(result)
