"""Signal generation: Volume Momentum (contrarian fade) + VWAP Reversion."""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    pair: str
    direction: str  # "long" or "short"
    score: float
    strategy: str
    indicators: dict


def generate_signals(pair: str, candles: list[list], brain_weights: dict = None) -> list[Signal]:
    """Analyze candles and return scored signal candidates."""
    if not candles or len(candles) < 30:
        return []

    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    volumes = [c[5] for c in candles]

    # Calculate indicators
    atr = _atr(highs, lows, closes, 14)
    rsi = _rsi(closes, 14)
    roc_10 = _roc(closes, 10)
    roc_5 = _roc(closes, 5)
    roc_20 = _roc(closes, 20) if len(closes) >= 21 else roc_10
    adx = _adx(highs, lows, closes, 14)
    vwap = _vwap(candles)
    vol_delta = _volume_delta(candles)
    vol_ratio = _volume_ratio(volumes)

    price = closes[-1]
    signals = []

    # ---- Strategy 1: Volume Momentum (Contrarian Fade) ----
    sig = _volume_momentum(pair, price, rsi, roc_10, roc_5, roc_20,
                           adx, vol_delta, atr, brain_weights)
    if sig:
        signals.append(sig)

    # ---- Strategy 2: VWAP Reversion ----
    sig = _vwap_reversion(pair, price, vwap, rsi, vol_delta, vol_ratio,
                          candles, atr, brain_weights)
    if sig:
        signals.append(sig)

    return signals


def _volume_momentum(pair, price, rsi, roc_10, roc_5, roc_20,
                     adx, vol_delta, atr, weights) -> Signal | None:
    """Contrarian fade: momentum decelerating → fade the move."""
    direction = None
    score = 35  # Low base — must earn points

    # SHORT: bullish momentum decelerating
    if roc_10 > 0.1 and vol_delta > 0.05 and adx > 18:
        if 45 < rsi < 75:
            direction = "short"
            decelerating = roc_5 < roc_20 * 0.8 if roc_20 > 0 else False
            score += min(roc_10 * 6, 8)
            score += min(vol_delta * 12, 6)
            score += min((adx - 18) * 0.4, 6)
            if decelerating:
                score += 8

    # LONG: bearish momentum decelerating
    elif roc_10 < -0.1 and vol_delta < -0.05 and adx > 18:
        if 25 < rsi < 55:
            direction = "long"
            decelerating = abs(roc_5) < abs(roc_20) * 0.8 if roc_20 != 0 else False
            score += min(abs(roc_10) * 6, 8)
            score += min(abs(vol_delta) * 12, 6)
            score += min((adx - 18) * 0.4, 6)
            if decelerating:
                score += 8

    if not direction:
        return None

    # Penalize RSI extremes
    if rsi > 75 or rsi < 25:
        score -= 10

    # Apply brain weight
    w = (weights or {}).get("volume_momentum", 1.0)
    score *= w

    if score < 30:  # absolute floor
        return None

    return Signal(
        pair=pair,
        direction=direction,
        score=round(score, 1),
        strategy="volume_momentum",
        indicators={"rsi": rsi, "roc_10": roc_10, "adx": adx,
                     "vol_delta": vol_delta, "atr": atr},
    )


def _vwap_reversion(pair, price, vwap, rsi, vol_delta, vol_ratio,
                     candles, atr, weights) -> Signal | None:
    """Price far from VWAP + exhaustion confirmations → revert."""
    if not vwap or vwap == 0:
        return None

    dev_pct = (price - vwap) / vwap * 100
    direction = None
    score = 35

    # LONG: price below VWAP
    if dev_pct < -0.15 and rsi < 50:
        direction = "long"
        confirms = 0
        if vol_ratio < 0.8:
            confirms += 1  # Volume declining
        if _small_body(candles):
            confirms += 1  # Doji/indecision
        if vol_delta > 0:
            confirms += 1  # Buyers entering
        if confirms < 2:
            return None
        score += confirms * 5
        score += min(abs(dev_pct) * 8, 10)

    # SHORT: price above VWAP
    elif dev_pct > 0.15 and rsi > 50:
        direction = "short"
        confirms = 0
        if vol_ratio < 0.8:
            confirms += 1
        if _small_body(candles):
            confirms += 1
        if vol_delta < 0:
            confirms += 1  # Sellers entering
        if confirms < 2:
            return None
        score += confirms * 5
        score += min(abs(dev_pct) * 8, 10)

    if not direction:
        return None

    # Penalize RSI extremes
    if rsi > 75 or rsi < 25:
        score -= 8

    # Apply brain weight
    w = (weights or {}).get("vwap_reversion", 1.0)
    score *= w

    if score < 30:
        return None

    return Signal(
        pair=pair,
        direction=direction,
        score=round(score, 1),
        strategy="vwap_reversion",
        indicators={"rsi": rsi, "vwap": vwap, "dev_pct": dev_pct,
                     "vol_delta": vol_delta, "atr": atr},
    )


# ======================================================================
# Technical indicator calculations
# ======================================================================

def _atr(highs, lows, closes, period=14) -> float:
    """Average True Range."""
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0
    return sum(trs[-period:]) / period


def _rsi(closes, period=14) -> float:
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return 50
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _roc(closes, period=10) -> float:
    """Rate of Change (percent)."""
    if len(closes) <= period or closes[-period - 1] == 0:
        return 0
    return ((closes[-1] - closes[-period - 1]) / closes[-period - 1]) * 100


def _adx(highs, lows, closes, period=14) -> float:
    """Simplified ADX calculation."""
    if len(closes) < period * 2:
        return 0
    plus_dm = []
    minus_dm = []
    trs = []
    for i in range(1, len(closes)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)

    if len(trs) < period:
        return 0

    atr_val = sum(trs[-period:]) / period
    if atr_val == 0:
        return 0
    plus_di = (sum(plus_dm[-period:]) / period) / atr_val * 100
    minus_di = (sum(minus_dm[-period:]) / period) / atr_val * 100
    di_sum = plus_di + minus_di
    if di_sum == 0:
        return 0
    dx = abs(plus_di - minus_di) / di_sum * 100
    return dx


def _vwap(candles) -> float:
    """Volume-weighted average price."""
    total_vol = 0
    total_vp = 0
    for c in candles:
        typical = (c[2] + c[3] + c[4]) / 3  # (H+L+C)/3
        vol = c[5]
        total_vp += typical * vol
        total_vol += vol
    return total_vp / total_vol if total_vol > 0 else 0


def _volume_delta(candles) -> float:
    """Estimate buy/sell pressure from candle direction × volume."""
    if not candles:
        return 0
    buy_vol = 0
    sell_vol = 0
    for c in candles[-14:]:
        o, cl, v = c[1], c[4], c[5]
        if cl >= o:
            buy_vol += v
        else:
            sell_vol += v
    total = buy_vol + sell_vol
    if total == 0:
        return 0
    return (buy_vol - sell_vol) / total


def _volume_ratio(volumes, period=14) -> float:
    """Current volume vs average."""
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period - 1:-1]) / period
    if avg == 0:
        return 1.0
    return volumes[-1] / avg


def detect_regime(candles: list[list]) -> str:
    """Detect market regime from candles: trending_up, trending_down, or ranging."""
    if not candles or len(candles) < 30:
        return "ranging"

    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]

    adx = _adx(highs, lows, closes, 14)
    roc = _roc(closes, 10)

    if adx > 25 and roc > 0.1:
        return "trending_up"
    if adx > 25 and roc < -0.1:
        return "trending_down"
    return "ranging"


def _small_body(candles) -> bool:
    """Check if last candle has small body (doji/indecision)."""
    if not candles:
        return False
    c = candles[-1]
    body = abs(c[4] - c[1])
    total_range = c[2] - c[3]
    if total_range == 0:
        return True
    return body / total_range < 0.3
