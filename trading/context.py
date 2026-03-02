"""Shared context between Darwin and Sentinel — JSON-backed memory."""
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
CONTEXT_FILE = DATA_DIR / "context.json"

_DEFAULT_CONTEXT = {
    "market": {
        "regime": "ranging",
        "btc_trend": "",
        "volatility": "medium",
        "updated_by": "",
        "updated_at": 0,
    },
    "directives": [],
    "observations": [],
    "biases": {},
    "sentinel_params": {
        "aggression": "moderate",
        "check_interval_min": 5,
        "confidence_threshold": 0.6,
        "max_interventions": 3,
    },
}

MAX_OBSERVATIONS = 50


class SharedContext:
    def __init__(self):
        self.data: dict = {}

    def load(self):
        """Load context from JSON file, or create default."""
        if CONTEXT_FILE.exists():
            try:
                self.data = json.loads(CONTEXT_FILE.read_text())
                return
            except Exception as e:
                logger.error(f"Failed to load context: {e}")
        self.data = json.loads(json.dumps(_DEFAULT_CONTEXT))
        self.save()

    def save(self):
        """Persist context to JSON."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONTEXT_FILE.write_text(json.dumps(self.data, indent=2))

    # ---- Market ----

    @property
    def regime(self) -> str:
        return self.data.get("market", {}).get("regime", "ranging")

    @property
    def market(self) -> dict:
        return self.data.get("market", _DEFAULT_CONTEXT["market"])

    def update_market(self, regime: str = None, btc_trend: str = None,
                      volatility: str = None, updated_by: str = ""):
        """Update market state fields (only non-None values)."""
        m = self.data.setdefault("market", dict(_DEFAULT_CONTEXT["market"]))
        if regime is not None:
            m["regime"] = regime
        if btc_trend is not None:
            m["btc_trend"] = btc_trend
        if volatility is not None:
            m["volatility"] = volatility
        m["updated_by"] = updated_by
        m["updated_at"] = time.time()
        self.save()

    # ---- Directives ----

    @property
    def directives(self) -> list[str]:
        return self.data.get("directives", [])

    def set_directives(self, directives: list[str]):
        """Replace directives list."""
        self.data["directives"] = directives
        self.save()

    # ---- Observations ----

    @property
    def observations(self) -> list[dict]:
        return self.data.get("observations", [])

    def add_observation(self, agent: str, note: str):
        """Add an observation, auto-trim to MAX_OBSERVATIONS."""
        obs = self.data.setdefault("observations", [])
        obs.append({
            "time": time.strftime("%H:%M"),
            "ts": time.time(),
            "agent": agent,
            "note": note,
        })
        if len(obs) > MAX_OBSERVATIONS:
            self.data["observations"] = obs[-MAX_OBSERVATIONS:]
        self.save()

    # ---- Biases ----

    @property
    def biases(self) -> dict:
        return self.data.get("biases", {})

    def set_bias(self, pair: str, direction: str, confidence: float, reason: str):
        """Set bias for a specific pair."""
        biases = self.data.setdefault("biases", {})
        biases[pair] = {
            "direction": direction,
            "confidence": confidence,
            "reason": reason,
        }
        self.save()

    def get_bias(self, pair: str) -> dict | None:
        return self.data.get("biases", {}).get(pair)

    # ---- Sentinel params ----

    @property
    def sentinel_params(self) -> dict:
        return self.data.get("sentinel_params",
                             _DEFAULT_CONTEXT["sentinel_params"])

    def update_sentinel_params(self, **kwargs):
        """Update sentinel params (only known keys)."""
        sp = self.data.setdefault("sentinel_params",
                                  dict(_DEFAULT_CONTEXT["sentinel_params"]))
        valid_keys = {"aggression", "check_interval_min",
                      "confidence_threshold", "max_interventions"}
        for k, v in kwargs.items():
            if k in valid_keys and v is not None:
                sp[k] = v
        self.save()

    # ---- Summary ----

    def summary(self) -> dict:
        """Short summary for get_status()."""
        return {
            "regime": self.regime,
            "volatility": self.market.get("volatility", "medium"),
            "directives_count": len(self.directives),
            "observations_count": len(self.observations),
            "biases": {k: v.get("direction") for k, v in self.biases.items()},
            "sentinel_params": self.sentinel_params,
        }
