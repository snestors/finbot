"""Bot state — current position, cooldowns, paused flag, paper mode."""
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = DATA_DIR / "state.json"

_DEFAULT_STATE = {
    "position": None,
    "cooldowns": {},  # pair → unix timestamp when cooldown expires
    "paused": False,
    "paper_mode": True,
    "last_run": None,
    "last_trade_time": None,
    "consecutive_losses": 0,
    "cooldown_until": None,  # unix ts — global cooldown after losing streak
}


class State:
    def __init__(self):
        self.data: dict = {}

    def load(self):
        """Load state from JSON."""
        if STATE_FILE.exists():
            try:
                self.data = json.loads(STATE_FILE.read_text())
                return
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        self.data = dict(_DEFAULT_STATE)
        self.save()

    def save(self):
        """Persist state."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.data, indent=2))

    # ---- Properties ----

    @property
    def position(self) -> dict | None:
        return self.data.get("position")

    @position.setter
    def position(self, value):
        self.data["position"] = value
        self.save()

    @property
    def paused(self) -> bool:
        return self.data.get("paused", False)

    @paused.setter
    def paused(self, value: bool):
        self.data["paused"] = value
        self.save()

    @property
    def paper_mode(self) -> bool:
        return self.data.get("paper_mode", True)

    @paper_mode.setter
    def paper_mode(self, value: bool):
        self.data["paper_mode"] = value
        self.save()

    # ---- Cooldown management ----

    def is_on_cooldown(self, pair: str) -> bool:
        """Check if pair is on cooldown."""
        cooldowns = self.data.get("cooldowns", {})
        expires = cooldowns.get(pair, 0)
        return time.time() < expires

    def set_cooldown(self, pair: str, candles: int, tf_minutes: int = 5):
        """Set cooldown for pair (candles × tf in minutes)."""
        duration = candles * tf_minutes * 60
        cooldowns = self.data.setdefault("cooldowns", {})
        cooldowns[pair] = time.time() + duration
        self.save()

    def is_globally_cooled_down(self) -> bool:
        """Check if global cooldown is active (after losing streak)."""
        until = self.data.get("cooldown_until")
        if until and time.time() < until:
            return True
        return False

    def set_global_cooldown(self, minutes: int = 30):
        """Set global cooldown (e.g. after 8 consecutive losses)."""
        self.data["cooldown_until"] = time.time() + minutes * 60
        self.save()
        logger.warning(f"Global cooldown set for {minutes} minutes")

    # ---- Position tracking ----

    def open_position(self, pair: str, side: str, entry_price: float,
                      sl: float, tp: float, margin: float, leverage: int,
                      strategy: str, score: float, paper: bool = True,
                      open_fee: float = 0.0):
        """Record an opened position."""
        self.data["position"] = {
            "pair": pair,
            "side": side,
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "margin": margin,
            "leverage": leverage,
            "strategy": strategy,
            "score": score,
            "paper": paper,
            "open_time": time.time(),
            "peak_pnl_pct": 0,
            "trailing_active": False,
            "open_fee": open_fee,
        }
        self.data["last_trade_time"] = time.time()
        self.save()

    def close_position(self):
        """Clear position."""
        self.data["position"] = None
        self.save()

    def update_trailing(self, pnl_pct: float, trigger_pct: float, distance_pct: float) -> bool:
        """Update trailing stop state. Returns True if should close."""
        pos = self.data.get("position")
        if not pos:
            return False

        peak = pos.get("peak_pnl_pct", 0)
        if pnl_pct > peak:
            pos["peak_pnl_pct"] = pnl_pct

        if pnl_pct > trigger_pct:
            pos["trailing_active"] = True

        if pos.get("trailing_active"):
            trailing_level = pos["peak_pnl_pct"] * (1 - distance_pct / 100)
            if pnl_pct < trailing_level:
                return True  # Close via trailing stop

        self.save()
        return False

    def record_loss(self):
        """Track consecutive losses for global cooldown."""
        self.data["consecutive_losses"] = self.data.get("consecutive_losses", 0) + 1
        if self.data["consecutive_losses"] >= 8:
            self.set_global_cooldown(30)
        self.save()

    def record_win(self):
        """Reset loss counter."""
        self.data["consecutive_losses"] = 0
        self.save()

    def summary(self) -> dict:
        """Summary for display."""
        pos = self.position
        return {
            "has_position": pos is not None,
            "position": pos,
            "paused": self.paused,
            "paper_mode": self.paper_mode,
            "last_run": self.data.get("last_run"),
            "consecutive_losses": self.data.get("consecutive_losses", 0),
            "globally_cooled_down": self.is_globally_cooled_down(),
        }
