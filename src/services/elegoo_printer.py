"""
Elegoo Centauri Carbon printer service — SDCP v3.0.0.

Auto-discovers the printer on the LAN via UDP broadcast,
then connects to its WebSocket for real-time status streaming.
Reconnects automatically if the connection drops or the IP changes.
"""
import asyncio
import json
import logging
import socket
import struct
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

DISCOVER_PORT = 3000
DISCOVER_MSG = b"M99999"
DISCOVER_TIMEOUT = 3
WS_RECONNECT_DELAY = 5

# SDCP status codes → human-readable
_STATUS_MAP = {
    0: "idle",
    1: "printing",
    2: "file_checking",
    3: "exposure_testing",
    4: "paused",
    5: "stopping",
    6: "stopped",
}


class ElegooPrinterService:
    """Discovers and streams status from an Elegoo Centauri Carbon printer."""

    def __init__(self, mainboard_id: str = ""):
        self.mainboard_id = mainboard_id
        self.latest: dict[str, Any] | None = None
        self._host: str | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("ElegooPrinterService started")

    async def stop(self):
        self._running = False
        logger.info("ElegooPrinterService stopped")

    # ------------------------------------------------------------------
    # Discovery — UDP broadcast
    # ------------------------------------------------------------------

    def discover(self) -> str | None:
        """Send UDP broadcast M99999 and return the printer's IP, or None."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(DISCOVER_TIMEOUT)
            sock.sendto(DISCOVER_MSG, ("<broadcast>", DISCOVER_PORT))

            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    break

                try:
                    payload = json.loads(data.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                # Match by MainboardID if configured
                mid = payload.get("Data", {}).get("MainboardID", "")
                if self.mainboard_id and mid != self.mainboard_id:
                    continue

                ip = payload.get("Data", {}).get("MainboardIP") or addr[0]
                logger.info(f"Elegoo printer discovered at {ip}")
                sock.close()
                return ip

            sock.close()
        except Exception as e:
            logger.debug(f"Elegoo discovery error: {e}")
        return None

    # ------------------------------------------------------------------
    # Main loop (runs in daemon thread)
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Discover → connect WS → stream. Re-discover on failure."""
        import websocket  # websocket-client (sync)

        while self._running:
            # Discover IP
            if not self._host:
                self._host = self.discover()
                if not self._host:
                    logger.debug("Elegoo printer not found, retrying in 30s")
                    self._sleep(30)
                    continue

            url = f"ws://{self._host}/websocket"
            logger.info(f"Connecting to Elegoo WS at {url}")

            try:
                ws = websocket.WebSocket()
                ws.settimeout(10)
                ws.connect(url)
                logger.info("Elegoo WS connected")

                while self._running:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception:
                        break

                    if not raw:
                        break

                    try:
                        msg = json.loads(raw)
                        self._handle_message(msg)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

                ws.close()
            except Exception as e:
                logger.warning(f"Elegoo WS error: {e}")

            # Connection lost — re-discover
            self._host = None
            if self._running:
                logger.info(f"Elegoo WS disconnected, reconnecting in {WS_RECONNECT_DELAY}s")
                self._sleep(WS_RECONNECT_DELAY)

    def _sleep(self, seconds: float):
        """Interruptible sleep."""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(0.5)

    # ------------------------------------------------------------------
    # Message parsing
    # ------------------------------------------------------------------

    def _handle_message(self, msg: dict):
        """Parse SDCP status message into self.latest."""
        status = msg.get("Status") or msg.get("status") or {}
        if not status and "Data" in msg:
            status = msg["Data"].get("Status", msg["Data"])

        # Try to extract from Attributes if present (SDCP v3)
        attrs = msg.get("Data", {}).get("Attributes", {}) or status

        current_status = attrs.get("CurrentStatus", attrs.get("Status", -1))
        progress = attrs.get("PrintProgress", attrs.get("Progress", 0))
        current_layer = attrs.get("CurrentLayer", 0)
        total_layers = attrs.get("TotalLayer", 0)
        filename = attrs.get("Filename", attrs.get("PrintFileName", ""))

        # Temperatures
        temp_nozzle = attrs.get("TempOfNozzle", attrs.get("NozzleTemp", 0))
        temp_bed = attrs.get("TempOfBed", attrs.get("BedTemp", 0))
        temp_box = attrs.get("TempOfBox", attrs.get("BoxTemp", 0))
        target_nozzle = attrs.get("TempOfNozzleTarget", attrs.get("NozzleTempTarget", 0))
        target_bed = attrs.get("TempOfBedTarget", attrs.get("BedTempTarget", 0))

        # Fans
        fan_model = attrs.get("FanOfModel", attrs.get("ModelFanSpeed", 0))
        fan_box = attrs.get("FanOfBox", attrs.get("BoxFanSpeed", 0))

        # Time
        elapsed_s = attrs.get("PrintDuration", attrs.get("ElapsedTime", 0))
        total_s = attrs.get("TotalTime", attrs.get("EstimatedTime", 0))

        eta_min = 0
        if total_s > 0 and elapsed_s > 0:
            remaining = max(0, total_s - elapsed_s)
            eta_min = round(remaining / 60)
        elif progress > 0 and elapsed_s > 0:
            estimated_total = elapsed_s / (progress / 100)
            remaining = max(0, estimated_total - elapsed_s)
            eta_min = round(remaining / 60)

        self.latest = {
            "status": _STATUS_MAP.get(current_status, f"unknown({current_status})"),
            "status_code": current_status,
            "progress": progress,
            "current_layer": current_layer,
            "total_layers": total_layers,
            "filename": filename,
            "temp_nozzle": temp_nozzle,
            "temp_bed": temp_bed,
            "temp_box": temp_box,
            "target_nozzle": target_nozzle,
            "target_bed": target_bed,
            "fan_model": fan_model,
            "fan_box": fan_box,
            "elapsed_s": elapsed_s,
            "total_s": total_s,
            "eta_min": eta_min,
            "host": self._host,
        }

    # ------------------------------------------------------------------
    # Commands via WebSocket (fire-and-forget via new connection)
    # ------------------------------------------------------------------

    def _send_command(self, cmd: dict) -> bool:
        """Send a command to the printer via a short-lived WS connection."""
        if not self._host:
            return False
        try:
            import websocket
            ws = websocket.WebSocket()
            ws.settimeout(5)
            ws.connect(f"ws://{self._host}/websocket")
            ws.send(json.dumps(cmd))
            ws.close()
            return True
        except Exception as e:
            logger.warning(f"Elegoo command error: {e}")
            return False

    def pause(self) -> bool:
        return self._send_command({"Cmd": 129, "Data": {"Cmd": 1}})  # SDCP pause

    def resume(self) -> bool:
        return self._send_command({"Cmd": 129, "Data": {"Cmd": 2}})  # SDCP resume

    def stop_print(self) -> bool:
        return self._send_command({"Cmd": 129, "Data": {"Cmd": 0}})  # SDCP stop

    # ------------------------------------------------------------------
    # Summary for LLM context
    # ------------------------------------------------------------------

    def get_summary(self) -> str:
        """Return a human-readable summary for the LLM."""
        if not self.latest:
            return ""

        d = self.latest
        status = d["status"].upper()

        if status == "IDLE":
            return f"Impresora 3D: IDLE (sin trabajo activo)"

        lines = [f"Impresora 3D: {status} {d['progress']}%"]

        if d["total_layers"]:
            lines[0] += f" (capa {d['current_layer']}/{d['total_layers']})"

        if d["filename"]:
            lines.append(f"Archivo: {d['filename']}")

        temps = []
        if d["temp_nozzle"]:
            temps.append(f"nozzle {d['temp_nozzle']}°C")
        if d["temp_bed"]:
            temps.append(f"cama {d['temp_bed']}°C")
        if d["temp_box"]:
            temps.append(f"caja {d['temp_box']}°C")
        if temps:
            lines.append(f"Temps: {', '.join(temps)}")

        if d["eta_min"] > 0:
            if d["eta_min"] >= 60:
                h = d["eta_min"] // 60
                m = d["eta_min"] % 60
                lines.append(f"ETA: ~{h}h {m}min restantes")
            else:
                lines.append(f"ETA: ~{d['eta_min']} min restantes")

        return "\n".join(lines)
