"""Trading bot parameters — all tuneable by brain/darwin."""

CONFIG = {
    # Pairs (Darwin will kill bad ones)
    "pairs": ["SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT", "ETH/USDT:USDT"],

    # Leverage & sizing
    "leverage_default": 6,
    "leverage_min": 3,
    "leverage_max": 8,
    "margin_pct": 0.40,  # 40% of available balance (leave buffer)

    # SL/TP based on ATR
    "sl_atr_mult": 2.0,
    "tp_atr_mult": 4.0,
    "sl_min_pct": 0.004,  # 0.4%
    "sl_max_pct": 0.007,  # 0.7% — tighter cap reduces avg loss

    # Trailing stop — let winners run bigger
    "trailing_trigger_pct": 5.0,   # was 0.5 — trigger at 5% leveraged PnL
    "trailing_distance_pct": 30,   # was 40 — tighter trail keeps more profit

    # Signal scoring
    "min_score": 55,
    "cooldown_candles": 8,  # 8 × 5m = 40 min between trades on same pair

    # Candle settings
    "candle_tf": "5m",
    "candle_count": 120,

    # Strategies
    "strategies": ["volume_momentum", "vwap_reversion", "ema_trend"],

    # Paper mode (default ON — no real money)
    "paper_mode": True,

    # Grace period (minutes) before declaring position closed
    "grace_period_min": 2,

    # Sentinel defaults (guardrails: max moderate, interval >= 5, interventions <= 5)
    "sentinel_check_interval_min": 5,
    "sentinel_max_interventions": 3,
    "sentinel_aggression": "moderate",

    # Hard contra-trend filter: block contra-trend trades below this score
    "contra_trend_min_score": 75,

    # Max consecutive losses before global cooldown
    "max_consecutive_losses": 5,

    # Min profit filter: expected gross must cover N× estimated fees
    "min_profit_fee_mult": 2.5,

    # Max trades per pair per day (reset at UTC midnight)
    "max_trades_per_pair_per_day": 4,
}
