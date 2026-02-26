"""
Multi-currency support with exchange rates.
Uses free exchangerate.host API (no key needed).
Caches rates for 1 hour.
"""
import logging
import time
import httpx

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES = {
    "PEN": "Sol Peruano",
    "USD": "Dolar Americano",
    "EUR": "Euro",
    "COP": "Peso Colombiano",
    "MXN": "Peso Mexicano",
    "BRL": "Real Brasileno",
    "CLP": "Peso Chileno",
    "ARS": "Peso Argentino",
    "BOB": "Boliviano",
    "GBP": "Libra Esterlina",
}

# Fallback rates (approx) in case API is down
FALLBACK_RATES_TO_USD = {
    "PEN": 3.72, "EUR": 0.92, "COP": 4150.0, "MXN": 17.1,
    "BRL": 4.97, "CLP": 930.0, "ARS": 870.0, "BOB": 6.91,
    "GBP": 0.79, "USD": 1.0,
}


class CurrencyService:
    def __init__(self):
        self._rates: dict[str, float] = {}  # rates relative to USD
        self._last_fetch: float = 0
        self._cache_ttl: int = 3600  # 1 hour

    async def get_rates(self) -> dict[str, float]:
        if self._rates and (time.time() - self._last_fetch) < self._cache_ttl:
            return self._rates
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://open.er-api.com/v6/latest/USD")
                data = resp.json()
                if data.get("result") == "success":
                    self._rates = {k: v for k, v in data["rates"].items() if k in SUPPORTED_CURRENCIES}
                    self._last_fetch = time.time()
                    logger.info(f"Exchange rates updated: {len(self._rates)} currencies")
                    return self._rates
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates: {e}. Using fallback.")
        self._rates = FALLBACK_RATES_TO_USD.copy()
        self._last_fetch = time.time()
        return self._rates

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return amount
        rates = await self.get_rates()
        from_rate = rates.get(from_currency, 1.0)
        to_rate = rates.get(to_currency, 1.0)
        # Convert: from -> USD -> to
        usd_amount = amount / from_rate
        return round(usd_amount * to_rate, 2)

    async def get_rate(self, from_currency: str, to_currency: str) -> float:
        return await self.convert(1.0, from_currency, to_currency)

    async def format_multi(self, amount: float, base_currency: str, target_currencies: list[str] = None) -> str:
        if not target_currencies:
            target_currencies = ["USD", "PEN"]
        parts = [f"{base_currency} {amount:.2f}"]
        for tc in target_currencies:
            if tc != base_currency:
                converted = await self.convert(amount, base_currency, tc)
                parts.append(f"{tc} {converted:.2f}")
        return " | ".join(parts)


class SunatTipoCambio:
    """Tipo de cambio SUNAT/SBS para Peru."""
    SUNAT_URL = "https://api.apis.net.pe/v2/sunat/tipo-cambio"
    TOKEN = "apis-token-11526.ogNVdWq1ZL7S4SjfUIbz5xyAnlXulamA"

    def __init__(self):
        self._cache: dict = {}
        self._last_fetch: float = 0

    async def get_tipo_cambio(self) -> dict:
        if self._cache and (time.time() - self._last_fetch) < 3600:
            return self._cache
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    self.SUNAT_URL,
                    headers={"Authorization": f"Bearer {self.TOKEN}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._cache = {
                        "compra": data.get("precioCompra", 0),
                        "venta": data.get("precioVenta", 0),
                        "fecha": data.get("fecha", ""),
                        "fuente": "SUNAT"
                    }
                    self._last_fetch = time.time()
                    logger.info(f"SUNAT tipo cambio: compra={self._cache['compra']} venta={self._cache['venta']}")
                    return self._cache
        except Exception as e:
            logger.warning(f"Error fetching SUNAT tipo cambio: {e}")
        return {"compra": 3.72, "venta": 3.75, "fecha": "", "fuente": "fallback"}
