"""Wrapper around ccxt for Bitget futures. Paper mode simulates everything."""
import logging
import time

logger = logging.getLogger(__name__)


class Exchange:
    """Bitget futures wrapper. In paper mode, only fetch_candles hits the API."""

    def __init__(self, api_key: str = "", secret: str = "", passphrase: str = "",
                 paper_mode: bool = True):
        self.paper_mode = paper_mode
        self._exchange = None
        self._api_key = api_key
        self._secret = secret
        self._passphrase = passphrase
        # Paper-mode simulated state
        self._paper_position = None
        self._paper_balance = 100.0  # start with $100 simulated

    def _get_exchange(self):
        """Lazy-init ccxt Bitget client."""
        if self._exchange is None:
            try:
                import ccxt
                self._exchange = ccxt.bitget({
                    "apiKey": self._api_key,
                    "secret": self._secret,
                    "password": self._passphrase,
                    "options": {
                        "defaultType": "swap",
                        "defaultMode": "one_way",  # one-way position mode
                    },
                })
                logger.info("ccxt Bitget client initialized (one-way mode)")
            except ImportError:
                logger.warning("ccxt not installed — only paper mode available")
                self._exchange = None
        return self._exchange

    # ------------------------------------------------------------------
    # Market data (always hits real API when ccxt is available)
    # ------------------------------------------------------------------

    def fetch_candles(self, pair: str, timeframe: str = "5m", count: int = 60) -> list[list]:
        """Fetch OHLCV candles. Returns [[ts, o, h, l, c, v], ...]."""
        ex = self._get_exchange()
        if ex is None:
            logger.warning("No exchange client — returning empty candles")
            return []
        try:
            return ex.fetch_ohlcv(pair, timeframe, limit=count)
        except Exception as e:
            logger.error(f"fetch_candles({pair}) error: {e}")
            return []

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def fetch_position(self, pair: str) -> dict | None:
        """Return open position or None."""
        if self.paper_mode:
            return self._paper_position

        ex = self._get_exchange()
        if ex is None:
            return None
        try:
            positions = ex.fetch_positions([pair])
            for pos in positions:
                amt = float(pos.get("contracts", 0) or 0)
                if amt > 0:
                    return {
                        "pair": pair,
                        "side": pos.get("side", "long"),
                        "entry_price": float(pos.get("entryPrice", 0) or 0),
                        "contracts": amt,
                        "unrealized_pnl": float(pos.get("unrealizedPnl", 0) or 0),
                        "leverage": float(pos.get("leverage", 8) or 8),
                    }
        except Exception as e:
            logger.error(f"fetch_position({pair}) error: {e}")
        return None

    def open_position(self, pair: str, side: str, margin: float,
                      leverage: int, sl: float, tp: float,
                      entry_price: float = 0) -> dict | None:
        """Open a futures position. Returns order info or None."""
        if self.paper_mode:
            price = entry_price or self._get_last_price(pair)
            if not price:
                return None
            contracts = (margin * leverage) / price
            self._paper_position = {
                "pair": pair,
                "side": side,
                "entry_price": price,
                "contracts": contracts,
                "margin": margin,
                "leverage": leverage,
                "sl": sl,
                "tp": tp,
                "unrealized_pnl": 0,
                "paper": True,
            }
            self._paper_balance -= margin
            logger.info(f"[PAPER] Opened {side} {pair} @ {price:.4f} "
                        f"margin=${margin:.2f} lev={leverage}x SL={sl:.4f} TP={tp:.4f}")
            return self._paper_position

        ex = self._get_exchange()
        if ex is None:
            return None
        try:
            ex.set_leverage(leverage, pair)
            order_side = "buy" if side == "long" else "sell"
            price = entry_price or self._get_last_price(pair)
            if not price:
                return None
            amount = (margin * leverage) / price

            order = ex.create_market_order(pair, order_side, amount,
                                            params={"oneWayMode": True})
            logger.info(f"Opened {side} {pair}: {order.get('id')}")

            # Set SL and TP as separate orders
            close_side = "sell" if side == "long" else "buy"
            hold_side = "buy" if side == "long" else "sell"
            if sl:
                try:
                    ex.create_order(pair, "market", close_side, amount, None, {
                        "stopLossPrice": str(sl),
                        "reduceOnly": True,
                        "oneWayMode": True,
                        "holdSide": hold_side,
                    })
                    logger.info(f"SL set for {pair} @ {sl}")
                except Exception as e:
                    logger.warning(f"SL order failed for {pair}: {e}")
            if tp:
                try:
                    ex.create_order(pair, "market", close_side, amount, None, {
                        "takeProfitPrice": str(tp),
                        "reduceOnly": True,
                        "oneWayMode": True,
                        "holdSide": hold_side,
                    })
                    logger.info(f"TP set for {pair} @ {tp}")
                except Exception as e:
                    logger.warning(f"TP order failed for {pair}: {e}")

            return order
        except Exception as e:
            logger.error(f"open_position({pair}, {side}) error: {e}")
            return None

    def close_position(self, pair: str, reason: str = "manual") -> dict | None:
        """Close open position."""
        if self.paper_mode:
            pos = self._paper_position
            if not pos:
                return None
            price = self._get_last_price(pair)
            pnl = self._calc_paper_pnl(pos, price)
            self._paper_balance += pos["margin"] + pnl
            result = {
                "pair": pair,
                "side": pos["side"],
                "entry_price": pos["entry_price"],
                "exit_price": price,
                "pnl": pnl,
                "reason": reason,
                "paper": True,
            }
            self._paper_position = None
            logger.info(f"[PAPER] Closed {pair} reason={reason} PnL=${pnl:.4f}")
            return result

        ex = self._get_exchange()
        if ex is None:
            return None
        try:
            pos = self.fetch_position(pair)
            if not pos:
                return None
            close_side = "sell" if pos["side"] == "long" else "buy"
            order = ex.create_market_order(pair, close_side, pos["contracts"],
                                           params={"reduceOnly": True,
                                                   "oneWayMode": True})
            logger.info(f"Closed {pair} reason={reason}: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"close_position({pair}) error: {e}")
            return None

    def fetch_balance(self) -> float:
        """Return USDT available (free) balance."""
        if self.paper_mode:
            return self._paper_balance

        ex = self._get_exchange()
        if ex is None:
            return 0
        try:
            balance = ex.fetch_balance({"type": "swap"})
            return float(balance.get("USDT", {}).get("free", 0) or 0)
        except Exception as e:
            logger.error(f"fetch_balance error: {e}")
            return 0

    def fetch_equity(self) -> float:
        """Return USDT total equity (free + used margin + unrealized PnL)."""
        if self.paper_mode:
            return self._paper_balance

        ex = self._get_exchange()
        if ex is None:
            return 0
        try:
            balance = ex.fetch_balance({"type": "swap"})
            usdt = balance.get("USDT", {})
            total = float(usdt.get("total", 0) or 0)
            # If total is available, use it; ccxt includes unrealized PnL in equity
            if total > 0:
                return total
            # Fallback to free
            return float(usdt.get("free", 0) or 0)
        except Exception as e:
            logger.error(f"fetch_equity error: {e}")
            return 0

    def fetch_my_trades(self, pair: str, limit: int = 5) -> list[dict]:
        """Fetch recent trades for a pair."""
        if self.paper_mode:
            return []
        ex = self._get_exchange()
        if ex is None:
            return []
        try:
            return ex.fetch_my_trades(pair, limit=limit)
        except Exception as e:
            logger.error(f"fetch_my_trades({pair}) error: {e}")
            return []

    def fetch_last_trade_fee(self, pair: str) -> float:
        """Fetch fee from the most recent trade on a pair. Returns fee in USDT."""
        if self.paper_mode:
            return 0.0
        trades = self.fetch_my_trades(pair, limit=1)
        if not trades:
            return 0.0
        try:
            fee_info = trades[0].get("fee", {})
            return abs(float(fee_info.get("cost", 0) or 0))
        except (ValueError, TypeError):
            return 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_last_price(self, pair: str) -> float:
        """Get current price from last candle."""
        candles = self.fetch_candles(pair, "1m", 1)
        if candles:
            return float(candles[-1][4])  # close price
        return 0

    def _calc_paper_pnl(self, pos: dict, current_price: float) -> float:
        """Calculate paper PnL."""
        if not current_price or not pos:
            return 0
        entry = pos["entry_price"]
        contracts = pos["contracts"]
        if pos["side"] == "long":
            return (current_price - entry) * contracts
        else:
            return (entry - current_price) * contracts
