"""Immutable trade journal — append-only record of all trades."""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
JOURNAL_FILE = DATA_DIR / "journal.json"


class Journal:
    def __init__(self):
        self._trades: list[dict] = []

    def load(self):
        """Load journal from JSON."""
        if JOURNAL_FILE.exists():
            try:
                self._trades = json.loads(JOURNAL_FILE.read_text())
                return
            except Exception as e:
                logger.error(f"Failed to load journal: {e}")
        self._trades = []

    def save(self):
        """Persist journal."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        JOURNAL_FILE.write_text(json.dumps(self._trades, indent=2))

    def record(self, trade: dict):
        """Append a trade (immutable)."""
        trade.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        trade.setdefault("id", len(self._trades) + 1)
        self._trades.append(trade)
        self.save()
        logger.info(f"Journal: recorded trade #{trade['id']} "
                     f"{trade.get('pair')} {trade.get('side')} "
                     f"PnL=${trade.get('pnl', 0):.4f}")

    def get_recent(self, n: int = 10) -> list[dict]:
        """Return last N trades."""
        return self._trades[-n:]

    def get_all(self) -> list[dict]:
        return list(self._trades)

    def get_stats(self) -> dict:
        """Overall stats."""
        return self._calc_stats(self._trades)

    def get_stats_for_pair(self, pair: str) -> dict:
        trades = [t for t in self._trades if t.get("pair") == pair]
        return self._calc_stats(trades)

    def get_stats_for_strategy(self, strategy: str) -> dict:
        trades = [t for t in self._trades if t.get("strategy") == strategy]
        return self._calc_stats(trades)

    def _calc_stats(self, trades: list[dict]) -> dict:
        if not trades:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0,
                    "total_pnl": 0, "avg_pnl": 0, "best": 0, "worst": 0,
                    "total_fees": 0, "gross_pnl": 0}
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]
        pnls = [t.get("pnl", 0) for t in trades]
        total_pnl = sum(pnls)
        total_fees = sum(t.get("fees", 0) for t in trades)
        gross_pnl = sum(t.get("gross_pnl", t.get("pnl", 0)) for t in trades)
        return {
            "total": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "total_pnl": round(total_pnl, 4),
            "gross_pnl": round(gross_pnl, 4),
            "total_fees": round(total_fees, 4),
            "avg_pnl": round(total_pnl / len(trades), 4) if trades else 0,
            "best": round(max(pnls), 4) if pnls else 0,
            "worst": round(min(pnls), 4) if pnls else 0,
        }
