"""Plugin de alertas de energia en tiempo real."""
import asyncio
from datetime import datetime, time

PEAK_THRESHOLD_W = 150.0  # Watts
BASELINE_W = 34.0  # Consumo base (todo apagado)

# Cooldown para no spamear alertas (segundos)
_last_alert_ts = 0
COOLDOWN_SEC = 300  # 5 minutos entre alertas


def register():
    return {
        "tools": {
            "energy_check_peak": {
                "description": "Verifica si la ultima lectura supera el umbral de pico",
                "handler": check_peak,
            },
            "energy_set_threshold": {
                "description": "Cambia el umbral de pico en watts",
                "handler": set_threshold,
            },
        },
        "actions": {
            "energy_peak_alert": energy_peak_alert,
        },
    }


def _is_weekday_daytime():
    """Lunes a viernes, 07:00 - 20:00."""
    now = datetime.now()
    if now.weekday() >= 5:  # Sabado=5, Domingo=6
        return False
    return time(7, 0) <= now.time() <= time(20, 0)


def check_peak(params: dict) -> str:
    """Verifica si un valor de watts supera el umbral."""
    watts = float(params.get("watts", 0))
    if watts > PEAK_THRESHOLD_W:
        excess = watts - BASELINE_W
        return f"PICO DETECTADO: {watts}W (exceso: {excess:.0f}W sobre base de {BASELINE_W}W)"
    return f"Normal: {watts}W"


def set_threshold(params: dict) -> str:
    global PEAK_THRESHOLD_W
    new_val = float(params.get("watts", PEAK_THRESHOLD_W))
    PEAK_THRESHOLD_W = new_val
    return f"Umbral actualizado a {PEAK_THRESHOLD_W}W"


async def energy_peak_alert(accion: dict, repos: dict) -> dict:
    """Accion llamada cuando se detecta un pico de energia."""
    global _last_alert_ts

    watts = float(accion.get("watts", 0))
    amps = float(accion.get("amps", 0))
    volts = float(accion.get("volts", 0))

    if not _is_weekday_daytime():
        return {"data_response": "Fuera de horario de alerta (L-V 07-20h)"}

    now_ts = asyncio.get_event_loop().time()
    if now_ts - _last_alert_ts < COOLDOWN_SEC:
        remaining = int(COOLDOWN_SEC - (now_ts - _last_alert_ts))
        return {"data_response": f"Cooldown activo, proxima alerta en {remaining}s"}

    if watts <= PEAK_THRESHOLD_W:
        return {"data_response": f"Sin pico: {watts}W esta dentro del umbral"}

    _last_alert_ts = now_ts
    excess = watts - BASELINE_W
    hora = datetime.now().strftime("%H:%M")

    mensaje = (
        f"\u26a1 Pico detectado a las {hora}: {watts:.0f}W | {amps:.2f}A | {volts:.1f}V\n"
        f"Estas {excess:.0f}W por encima del consumo base. "
        f"Revisa que electrodomestico prendiste."
    )

    return {
        "data_response": mensaje,
        "alert": {
            "tipo": "energia_pico",
            "watts": watts,
            "threshold": PEAK_THRESHOLD_W,
            "hora": hora,
        },
    }
