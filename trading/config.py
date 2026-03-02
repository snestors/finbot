"""Trading bot parameters — all tuneable by brain/darwin."""

CONFIG = {
    # Pairs (Darwin will kill bad ones)
    "pairs": ["SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT"],

    # Leverage & sizing
    "leverage_default": 8,
    "leverage_min": 3,
    "leverage_max": 10,
    "margin_pct": 0.50,  # 50% of available balance

    # SL/TP based on ATR
    "sl_atr_mult": 2.2,
    "tp_atr_mult": 3.3,
    "sl_min_pct": 0.005,  # 0.5%
    "sl_max_pct": 0.015,  # 1.5%

    # Trailing stop (MVP — most profitable mechanism)
    "trailing_trigger_pct": 0.5,
    "trailing_distance_pct": 40,

    # Signal scoring
    "min_score": 50,
    "cooldown_candles": 3,

    # Candle settings
    "candle_tf": "5m",
    "candle_count": 60,

    # Strategies
    "strategies": ["volume_momentum", "vwap_reversion"],

    # Paper mode (default ON — no real money)
    "paper_mode": True,

    # Grace period (minutes) before declaring position closed
    "grace_period_min": 2,

    # Sentinel defaults
    "sentinel_check_interval_min": 5,
    "sentinel_max_interventions": 3,
    "sentinel_aggression": "moderate",

    # Hard contra-trend filter: block contra-trend trades below this score
    "contra_trend_min_score": 135,

    # Max consecutive losses before global cooldown
    "max_consecutive_losses": 5,
}
