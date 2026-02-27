"""
Sonoff POW Elite service — reads power data via mDNS TXT records.

Uses sync Zeroconf ServiceBrowser in a daemon thread to receive
encrypted broadcasts from the device every ~1s. AES-128-CBC decryption
with the device key yields real-time power metrics.
"""
import hashlib
import json
import logging
import socket
import threading
from base64 import b64decode
from typing import Any

logger = logging.getLogger(__name__)


class SonoffService:
    def __init__(self, device_id: str, device_key: str, **_kwargs):
        self.device_id = device_id
        self.device_key = device_key
        self._aes_key = hashlib.md5(device_key.encode()).digest()
        self.latest: dict[str, Any] | None = None
        self._zc = None
        self._browser = None
        self._thread: threading.Thread | None = None

    async def start(self):
        self._thread = threading.Thread(target=self._run_listener, daemon=True)
        self._thread.start()
        logger.info("SonoffService mDNS listener started")

    async def stop(self):
        if self._browser:
            self._browser.cancel()
        if self._zc:
            self._zc.close()
        logger.info("SonoffService stopped")

    def _run_listener(self):
        from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

        self._zc = Zeroconf()
        self._browser = ServiceBrowser(
            self._zc,
            "_ewelink._tcp.local.",
            handlers=[self._on_service_state_change],
        )
        # Block thread forever — daemon=True ensures cleanup on exit
        threading.Event().wait()

    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        from zeroconf import ServiceStateChange

        if state_change not in (ServiceStateChange.Added, ServiceStateChange.Updated):
            return

        try:
            info = zeroconf.get_service_info(service_type, name)
            if not info or not info.properties:
                return

            props = {
                k.decode() if isinstance(k, bytes) else k:
                v.decode() if isinstance(v, bytes) else v
                for k, v in info.properties.items()
            }

            # Filter by our device
            if props.get("id") != self.device_id:
                return

            decrypted = self._decrypt_props(props)
            if decrypted:
                self.latest = self._parse(decrypted)
                logger.debug(f"Sonoff reading: {self.latest}")

        except Exception:
            logger.debug("Sonoff mDNS callback error", exc_info=True)

    def _decrypt_props(self, props: dict) -> dict | None:
        """Decrypt AES-128-CBC data from mDNS TXT record properties."""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
        except ImportError:
            try:
                from Cryptodome.Cipher import AES
                from Cryptodome.Util.Padding import unpad
            except ImportError:
                logger.error("pycryptodome not installed")
                return None

        try:
            iv_b64 = props.get("iv", "")
            # Concatenate data1..data4 (split due to 249-byte DNS TXT limit)
            data_b64 = ""
            for i in range(1, 5):
                data_b64 += props.get(f"data{i}", "")
            if not data_b64 or not iv_b64:
                return None

            iv = b64decode(iv_b64)
            ciphertext = b64decode(data_b64)
            cipher = AES.new(self._aes_key, AES.MODE_CBC, iv=iv)
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
            return json.loads(plaintext.decode())
        except Exception as e:
            logger.debug(f"Sonoff decrypt error: {e}")
            return None

    def _parse(self, data: dict) -> dict[str, Any]:
        """Extract power metrics from decrypted device data. Raw values ÷ 100."""
        return {
            "power_w": _div100(data.get("power")),
            "voltage_v": _div100(data.get("voltage")),
            "current_a": _div100(data.get("current")),
            "day_kwh": _div100(data.get("dayKwh", data.get("oneKwh"))),
            "month_kwh": _div100(data.get("monthKwh", data.get("hundredDaysKwh"))),
        }


def _div100(val) -> float:
    try:
        return float(val) / 100 if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0
