"""Learning engine — strategy weights by regime, Bayesian evolution."""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
BRAIN_FILE = DATA_DIR / "brain.json"

_DEFAULT_BRAIN = {
    "params": {
        "sl_atr_mult": 2.2,
        "tp_atr_mult": 3.3,
        "leverage_default": 8,
        "min_score": 50,
        "trailing_trigger_pct": 0.5,
        "trailing_distance_pct": 40,
    },
    "strategy_weights": {
        "volume_momentum": {
            "regime_trending_up": 1.0,
            "regime_trending_down": 1.2,
            "regime_ranging": 0.8,
        },
        "vwap_reversion": {
            "regime_trending_up": 0.8,
            "regime_trending_down": 0.9,
            "regime_ranging": 1.3,
        },
    },
    "stats": {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "streak": 0,
        "total_pnl": 0.0,
        "evolve_count": 0,
    },
    "killed_pairs": [],
    "killed_strategies": [],
}


class Brain:
    def __init__(self):
        self.data = {}

    def load(self):
        """Load brain from JSON file, or create default."""
        if BRAIN_FILE.exists():
            try:
                self.data = json.loads(BRAIN_FILE.read_text())
                return
            except Exception as e:
                logger.error(f"Failed to load brain: {e}")
        self.data = json.loads(json.dumps(_DEFAULT_BRAIN))
        self.save()

    def save(self):
        """Persist brain to JSON."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BRAIN_FILE.write_text(json.dumps(self.data, indent=2))

    @property
    def params(self) -> dict:
        return self.data.get("params", _DEFAULT_BRAIN["params"])

    @property
    def stats(self) -> dict:
        return self.data.get("stats", _DEFAULT_BRAIN["stats"])

    @property
    def killed_pairs(self) -> list:
        return self.data.get("killed_pairs", [])

    @property
    def killed_strategies(self) -> list:
        return self.data.get("killed_strategies", [])

    def get_weight(self, strategy: str, regime: str = "regime_ranging") -> float:
        """Get multiplicative weight for strategy × regime."""
        sw = self.data.get("strategy_weights", {})
        return sw.get(strategy, {}).get(regime, 1.0)

    def get_weights_flat(self) -> dict:
        """Return flat {strategy: average_weight} for signal scoring."""
        sw = self.data.get("strategy_weights", {})
        result = {}
        for strategy, regimes in sw.items():
            vals = list(regimes.values())
            result[strategy] = sum(vals) / len(vals) if vals else 1.0
        return result

    def get_weights_for_regime(self, regime: str) -> dict:
        """Return {strategy: weight} for a specific regime.

        Args:
            regime: "trending_up", "trending_down", or "ranging"
        """
        regime_key = f"regime_{regime}"
        sw = self.data.get("strategy_weights", {})
        result = {}
        for strategy, regimes in sw.items():
            result[strategy] = regimes.get(regime_key, 1.0)
        return result

    def update_after_trade(self, trade: dict, recent_trades: list = None):
        """Update stats after a completed trade."""
        stats = self.data.setdefault("stats", dict(_DEFAULT_BRAIN["stats"]))
        stats["total_trades"] = stats.get("total_trades", 0) + 1
        pnl = trade.get("pnl", 0)
        stats["total_pnl"] = stats.get("total_pnl", 0) + pnl
        fees = trade.get("fees", 0)
        stats["total_fees"] = round(stats.get("total_fees", 0) + fees, 6)

        if pnl > 0:
            stats["wins"] = stats.get("wins", 0) + 1
            streak = stats.get("streak", 0)
            stats["streak"] = max(streak, 0) + 1
        else:
            stats["losses"] = stats.get("losses", 0) + 1
            streak = stats.get("streak", 0)
            stats["streak"] = min(streak, 0) - 1

        # Check if we should evolve (every 15 trades)
        if stats["total_trades"] % 15 == 0:
            self.evolve(recent_trades or [])

        self.save()

    def evolve(self, recent_trades: list = None):
        """Bayesian weight update per strategy × regime. Called every 15 trades."""
        if not recent_trades:
            return

        sw = self.data.get("strategy_weights", {})
        for strategy in list(sw.keys()):
            strat_trades = [t for t in recent_trades if t.get("strategy") == strategy]
            if len(strat_trades) < 5:
                continue
            wins = sum(1 for t in strat_trades if t.get("pnl", 0) > 0)
            wr = wins / len(strat_trades)

            for regime_key in sw[strategy]:
                if wr > 0.4:
                    sw[strategy][regime_key] = min(sw[strategy][regime_key] * 1.1, 2.0)
                elif wr < 0.25:
                    sw[strategy][regime_key] = max(sw[strategy][regime_key] * 0.8, 0.3)

        stats = self.data.get("stats", {})
        stats["evolve_count"] = stats.get("evolve_count", 0) + 1
        logger.info(f"Brain evolved (#{stats['evolve_count']})")
        self.save()

    def set_param(self, key: str, value) -> bool:
        """Update a brain parameter. Returns True if valid."""
        params = self.data.get("params", {})
        if key not in params:
            return False
        # Type-cast to match existing type
        old_type = type(params[key])
        try:
            params[key] = old_type(value)
            self.save()
            return True
        except (ValueError, TypeError):
            return False

    def summary(self) -> dict:
        """Return a summary for display."""
        stats = self.stats
        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        wr = (wins / total * 100) if total > 0 else 0
        return {
            "total_trades": total,
            "wins": wins,
            "losses": stats.get("losses", 0),
            "win_rate": round(wr, 1),
            "total_pnl": round(stats.get("total_pnl", 0), 4),
            "total_fees": round(stats.get("total_fees", 0), 4),
            "streak": stats.get("streak", 0),
            "evolve_count": stats.get("evolve_count", 0),
            "killed_pairs": self.killed_pairs,
            "killed_strategies": self.killed_strategies,
            "params": self.params,
        }
