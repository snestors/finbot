import json
import os
import asyncio
import base64
import logging
import traceback
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.auth import AuthMiddleware, verify_pin, create_session

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.remove(ws)


def create_app(message_bus, mensaje_repo, gasto_repo, ingreso_repo,
               presupuesto_repo, deuda_repo, whatsapp_channel, ws_manager,
               perfil_repo=None, cuenta_repo=None, cobro_repo=None,
               tarjeta_repo=None, currency_service=None, sunat_service=None,
               gasto_cuota_repo=None, tipo_cambio_repo=None,
               memoria_repo=None,
               transferencia_repo=None, pago_tarjeta_repo=None,
               lifespan=None,
               movimiento_repo=None, tarjeta_periodo_repo=None,
               movimiento_cuota_repo=None,
               sonoff_service=None, consumo_repo=None,
               pago_consumo_repo=None, consumo_config_repo=None,
               gasto_fijo_repo=None,
               llm_usage_repo=None,
               printer_service=None,
               llm_client=None,
               google_assistant=None,
               control_repo=None) -> FastAPI:

    app = FastAPI(title="FinBot", docs_url="/api/docs", lifespan=lifespan)

    # --- Auth middleware ---
    app.add_middleware(AuthMiddleware)

    # --- Login page (served by React SPA) ---
    @app.get("/login")
    async def login_page():
        return FileResponse("web/index.html")

    # --- Login ---
    @app.post("/api/login")
    async def login(data: dict):
        pin = data.get("pin", "")
        if verify_pin(pin):
            token = create_session()
            response = JSONResponse({"ok": True})
            response.set_cookie("finbot_session", token, httponly=True, samesite="lax", max_age=86400 * 30)
            return response
        return JSONResponse({"error": "PIN incorrecto"}, status_code=401)

    # --- WebSocket ---
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        _ensure_stats_loop()
        # Send stats immediately on connect
        try:
            stats = await _read_system_stats()
            await websocket.send_json({"type": "system_stats", **stats})
        except Exception:
            pass
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from WebSocket: {data[:100]}")
                    continue
                try:
                    if msg.get("type") == "message":
                        await message_bus.handle_incoming(
                            text=msg.get("text", ""),
                            media=None,
                            source="web",
                        )
                except Exception:
                    logger.error(f"Error processing WS message: {traceback.format_exc()}")
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            logger.error(f"WebSocket error: {traceback.format_exc()}")
            ws_manager.disconnect(websocket)

    # --- WhatsApp Webhook ---
    @app.post("/webhook/whatsapp")
    async def whatsapp_webhook(payload: dict):
        try:
            media = None
            if payload.get("hasMedia") and payload.get("media"):
                media = {
                    "mimetype": payload["media"]["mimetype"],
                    "data": payload["media"]["data"],
                }
            await message_bus.handle_incoming(
                text=payload.get("body", ""),
                media=media,
                source="whatsapp",
                reply_to=payload.get("from"),
            )
        except Exception:
            logger.error(f"Webhook error: {traceback.format_exc()}")
        return {"ok": True}

    # --- Upload receipt photo from web ---
    @app.post("/api/upload-receipt")
    async def upload_receipt(file: UploadFile = File(...), text: str = Form("")):
        content = await file.read()
        media = {
            "mimetype": file.content_type,
            "data": base64.b64encode(content).decode(),
        }
        await message_bus.handle_incoming(text=text, media=media, source="web")
        return {"ok": True}

    # --- Chat history ---
    @app.get("/api/mensajes")
    async def get_mensajes(limit: int = 50, before: int = None):
        return await mensaje_repo.get_history(limit=limit, before=before)

    # --- Movimientos (unified) ---
    @app.get("/api/movimientos")
    async def get_movimientos(mes: str = None, tipo: str = None,
                              cuenta_id: int = None, tarjeta_id: int = None):
        if not movimiento_repo:
            return []
        if cuenta_id:
            return await movimiento_repo.get_by_cuenta(cuenta_id, mes, tipo)
        if tarjeta_id:
            return await movimiento_repo.get_by_tarjeta(tarjeta_id, mes)
        return await movimiento_repo.get_by_month(mes, tipo)

    @app.get("/api/movimientos/hoy")
    async def get_movimientos_hoy(tipo: str = None):
        if not movimiento_repo:
            return []
        return await movimiento_repo.get_today(tipo)

    @app.delete("/api/movimientos/{mov_id}")
    async def delete_movimiento(mov_id: int):
        if not movimiento_repo:
            return {"error": "Movimientos no disponible"}
        await movimiento_repo.delete(mov_id)
        return {"ok": True}

    # --- Gastos (legacy aliases → movimientos) ---
    @app.get("/api/gastos")
    async def get_gastos(mes: str = None, cuenta_id: int = None, tarjeta_id: int = None):
        if movimiento_repo:
            if cuenta_id:
                return await movimiento_repo.get_by_cuenta(cuenta_id, mes, "gasto")
            if tarjeta_id:
                return await movimiento_repo.get_by_tarjeta(tarjeta_id, mes)
            return await movimiento_repo.get_by_tipo("gasto", mes)
        if cuenta_id:
            return await gasto_repo.get_by_cuenta(cuenta_id, mes)
        if tarjeta_id:
            return await gasto_repo.get_by_tarjeta(tarjeta_id, mes)
        return await gasto_repo.get_by_month(mes)

    @app.get("/api/gastos/hoy")
    async def get_gastos_hoy():
        if movimiento_repo:
            return await movimiento_repo.get_gastos_hoy()
        return await gasto_repo.get_today()

    @app.delete("/api/gastos/{gasto_id}")
    async def delete_gasto(gasto_id: int):
        if movimiento_repo:
            await movimiento_repo.delete(gasto_id)
        else:
            await gasto_repo.delete(gasto_id)
        return {"ok": True}

    # --- Ingresos (legacy alias → movimientos) ---
    @app.get("/api/ingresos")
    async def get_ingresos(mes: str = None):
        if movimiento_repo:
            return await movimiento_repo.get_ingresos_mes(mes)
        return await ingreso_repo.get_by_month(mes)

    # --- Resúmenes ---
    @app.get("/api/resumen/diario")
    async def resumen_diario():
        repo = movimiento_repo or gasto_repo
        return {"text": await repo.resumen_hoy()}

    @app.get("/api/resumen/semanal")
    async def resumen_semanal():
        repo = movimiento_repo or gasto_repo
        return {"text": await repo.resumen_semana()}

    @app.get("/api/resumen/mensual")
    async def resumen_mensual():
        repo = movimiento_repo or gasto_repo
        return {"text": await repo.resumen_mes()}

    @app.get("/api/resumen/categorias")
    async def resumen_categorias(mes: str = None):
        repo = movimiento_repo or gasto_repo
        return await repo.resumen_categorias(mes)

    # --- Presupuestos ---
    @app.get("/api/presupuestos")
    async def get_presupuestos():
        return await presupuesto_repo.get_all()

    @app.post("/api/presupuestos")
    async def save_presupuesto(data: dict):
        doc_id = await presupuesto_repo.save(data)
        return {"id": doc_id}

    @app.delete("/api/presupuestos/{presupuesto_id}")
    async def delete_presupuesto(presupuesto_id: int):
        from src.database.db import get_db
        db = await get_db()
        await db.execute("DELETE FROM presupuestos WHERE id = ?", (presupuesto_id,))
        await db.commit()
        return {"ok": True}

    # --- Deudas ---
    @app.get("/api/deudas")
    async def get_deudas():
        return await deuda_repo.get_all()

    @app.post("/api/deudas")
    async def save_deuda(data: dict):
        doc_id = await deuda_repo.save(data)
        return {"id": doc_id}

    @app.post("/api/deudas/{deuda_id}/pago")
    async def registrar_pago(deuda_id: int, data: dict):
        await deuda_repo.registrar_pago(deuda_id, data["monto"])
        return {"ok": True}

    @app.get("/api/deudas/{deuda_id}/pagos")
    async def get_deuda_pagos(deuda_id: int):
        deuda = await deuda_repo.get_by_id(deuda_id)
        if not deuda:
            return []
        return deuda.get("pagos", [])

    # --- Perfil ---
    @app.get("/api/perfil")
    async def get_perfil():
        if not perfil_repo:
            return {"error": "Perfil no disponible"}
        perfil = await perfil_repo.get()
        return perfil or {}

    @app.post("/api/perfil")
    async def save_perfil(data: dict):
        if not perfil_repo:
            return {"error": "Perfil no disponible"}
        result = await perfil_repo.create_or_update(data)
        return result

    # --- Cuentas ---
    @app.get("/api/cuentas")
    async def get_cuentas():
        if not cuenta_repo:
            return []
        return await cuenta_repo.get_all()

    @app.post("/api/cuentas")
    async def save_cuenta(data: dict):
        if not cuenta_repo:
            return {"error": "Cuentas no disponible"}
        doc_id = await cuenta_repo.save(data)
        return {"id": doc_id}

    @app.put("/api/cuentas/{cuenta_id}")
    async def update_cuenta(cuenta_id: int, data: dict):
        if not cuenta_repo:
            return {"error": "Cuentas no disponible"}
        data["id"] = cuenta_id
        doc_id = await cuenta_repo.save(data)
        return {"id": doc_id}

    @app.delete("/api/cuentas/{cuenta_id}")
    async def delete_cuenta(cuenta_id: int):
        if not cuenta_repo:
            return {"error": "Cuentas no disponible"}
        await cuenta_repo.delete(cuenta_id)
        return {"ok": True}

    @app.get("/api/cuentas/{cuenta_id}/movimientos")
    async def get_cuenta_movimientos(cuenta_id: int, mes: str = None):
        """All movements for an account with enriched names."""
        if movimiento_repo:
            from src.database.db import get_db
            db = await get_db()
            q = """SELECT m.*,
                          co.nombre as cuenta_origen,
                          cd.nombre as cuenta_destino,
                          t.nombre as tarjeta_nombre
                   FROM movimientos m
                   LEFT JOIN cuentas co ON co.id = m.cuenta_id
                   LEFT JOIN cuentas cd ON cd.id = m.cuenta_destino_id
                   LEFT JOIN tarjetas t ON t.id = m.tarjeta_id
                   WHERE (m.cuenta_id = ? OR m.cuenta_destino_id = ?)"""
            params: list = [cuenta_id, cuenta_id]
            if mes:
                q += " AND m.mes = ?"
                params.append(mes)
            q += " ORDER BY m.fecha DESC"
            cursor = await db.execute(q, params)
            return [dict(r) for r in await cursor.fetchall()]
        # Legacy fallback
        movimientos = []
        for g in await gasto_repo.get_by_cuenta(cuenta_id, mes):
            g["_tipo"] = "gasto"
            movimientos.append(g)
        from src.database.db import get_db as get_db_legacy
        db = await get_db_legacy()
        q = "SELECT * FROM ingresos WHERE cuenta_id = ?"
        params_legacy = [cuenta_id]
        if mes:
            q += " AND mes = ?"
            params_legacy.append(mes)
        cursor = await db.execute(q + " ORDER BY fecha DESC", params_legacy)
        for r in await cursor.fetchall():
            d = dict(r)
            d["_tipo"] = "ingreso"
            movimientos.append(d)
        if transferencia_repo:
            for t in await transferencia_repo.get_by_cuenta(cuenta_id):
                t["_tipo"] = "transferencia"
                movimientos.append(t)
        if pago_tarjeta_repo:
            for p in await pago_tarjeta_repo.get_by_cuenta(cuenta_id):
                p["_tipo"] = "pago_tarjeta"
                movimientos.append(p)
        movimientos.sort(key=lambda x: x.get("fecha", ""), reverse=True)
        return movimientos

    # --- Transferencias ---
    @app.get("/api/transferencias")
    async def get_transferencias():
        if not transferencia_repo:
            return []
        return await transferencia_repo.get_all()

    # --- Dashboard extras ---
    @app.get("/api/dashboard/top-comercios")
    async def top_comercios(mes: str = None):
        repo = movimiento_repo or gasto_repo
        return await repo.top_comercios(mes)

    @app.get("/api/dashboard/metodos-pago")
    async def metodos_pago(mes: str = None):
        repo = movimiento_repo or gasto_repo
        return await repo.metodo_pago_breakdown(mes)

    # --- WhatsApp status ---
    @app.get("/api/whatsapp/qr")
    async def get_qr():
        return {"qr": await whatsapp_channel.get_qr()}

    @app.get("/api/whatsapp/status")
    async def get_wa_status():
        return await whatsapp_channel.get_status()

    # --- Cobros ---
    @app.get("/api/cobros")
    async def get_cobros(include_pagos: bool = False):
        if not cobro_repo:
            return []
        if include_pagos:
            return await cobro_repo.get_all_with_pagos()
        return await cobro_repo.get_all()

    @app.post("/api/cobros")
    async def save_cobro(data: dict):
        if not cobro_repo:
            return {"error": "Cobros no disponible"}
        doc_id = await cobro_repo.save(data)
        return {"id": doc_id}

    @app.get("/api/cobros/{cobro_id}/pagos")
    async def get_cobro_pagos(cobro_id: int):
        if not cobro_repo:
            return []
        return await cobro_repo.get_pagos(cobro_id)

    @app.post("/api/cobros/{cobro_id}/pago")
    async def cobro_pago(cobro_id: int, data: dict):
        if not cobro_repo:
            return {"error": "Cobros no disponible"}
        result = await cobro_repo.registrar_pago(cobro_id, data["monto"])
        return result

    @app.delete("/api/cobros/{cobro_id}")
    async def delete_cobro(cobro_id: int):
        if not cobro_repo:
            return {"error": "Cobros no disponible"}
        await cobro_repo.delete(cobro_id)
        return {"ok": True}

    # --- Tarjetas ---
    @app.get("/api/tarjetas")
    async def get_tarjetas():
        if not tarjeta_repo:
            return []
        return await tarjeta_repo.get_all()

    @app.post("/api/tarjetas")
    async def save_tarjeta(data: dict):
        if not tarjeta_repo:
            return {"error": "Tarjetas no disponible"}
        doc_id = await tarjeta_repo.save(data)
        return {"id": doc_id}

    @app.get("/api/tarjetas/{tarjeta_id}/periodos")
    async def get_tarjeta_periodos(tarjeta_id: int):
        """Get all billing periods for a credit card."""
        if not tarjeta_periodo_repo:
            return []
        return await tarjeta_periodo_repo.get_by_tarjeta(tarjeta_id)

    @app.get("/api/tarjetas/{tarjeta_id}/estado-cuenta")
    async def get_estado_cuenta(tarjeta_id: int):
        """Get current billing statement for a credit card."""
        if not tarjeta_repo:
            return {"error": "Tarjetas no disponible"}
        tarjeta = await tarjeta_repo.get_by_id(tarjeta_id)
        if not tarjeta:
            return {"error": "Tarjeta no encontrada"}
        period = tarjeta_repo.get_billing_period(tarjeta)
        # Use movimientos if available
        if movimiento_repo:
            gastos = await movimiento_repo.get_by_tarjeta_daterange(
                tarjeta_id, period["inicio"], period["fin"]
            )
        else:
            gastos = await gasto_repo.get_by_tarjeta_daterange(
                tarjeta_id, period["inicio"], period["fin"]
            )
        cuotas = []
        cuota_repo = movimiento_cuota_repo or gasto_cuota_repo
        if cuota_repo:
            cuotas = await cuota_repo.get_pendientes_tarjeta(
                tarjeta_id, period["periodo"]
            )
        total_gastos = sum(g["monto"] for g in gastos)
        total_cuotas = sum(c["monto_cuota"] for c in cuotas)
        return {
            "tarjeta": tarjeta,
            "periodo": period,
            "gastos": gastos,
            "cuotas": cuotas,
            "total_gastos": round(total_gastos, 2),
            "total_cuotas": round(total_cuotas, 2),
            "total": round(total_gastos + total_cuotas, 2),
        }

    @app.get("/api/tarjetas/{tarjeta_id}/cuotas")
    async def get_cuotas_tarjeta(tarjeta_id: int):
        """Get all pending installments for a credit card."""
        if movimiento_cuota_repo:
            return await movimiento_cuota_repo.get_pendientes_tarjeta(tarjeta_id)
        if gasto_cuota_repo:
            return await gasto_cuota_repo.get_pendientes_tarjeta(tarjeta_id)
        return []

    @app.get("/api/tarjetas/{tarjeta_id}/pagos")
    async def get_tarjeta_pagos(tarjeta_id: int):
        """Get credit card payment history."""
        if movimiento_repo:
            from src.database.db import get_db
            db = await get_db()
            cursor = await db.execute(
                """SELECT m.*, c.nombre as cuenta_nombre
                   FROM movimientos m
                   LEFT JOIN cuentas c ON c.id = m.cuenta_id
                   WHERE m.tipo = 'pago_tarjeta' AND m.tarjeta_id = ?
                   ORDER BY m.fecha DESC""",
                (tarjeta_id,),
            )
            return [dict(r) for r in await cursor.fetchall()]
        if not pago_tarjeta_repo:
            return []
        return await pago_tarjeta_repo.get_by_tarjeta(tarjeta_id)

    @app.delete("/api/tarjetas/{tarjeta_id}")
    async def delete_tarjeta(tarjeta_id: int):
        if not tarjeta_repo:
            return {"error": "Tarjetas no disponible"}
        await tarjeta_repo.delete(tarjeta_id)
        return {"ok": True}

    # --- Tipo de Cambio ---
    @app.get("/api/tipo-cambio")
    async def get_tipo_cambio():
        result = {}
        if sunat_service:
            try:
                result["sunat"] = await sunat_service.get_tipo_cambio()
            except Exception:
                result["sunat"] = None
        if currency_service:
            try:
                result["rates"] = await currency_service.get_rates()
            except Exception:
                result["rates"] = {}
        return result

    @app.get("/api/tipo-cambio/historico")
    async def get_tipo_cambio_historico(dias: int = 30):
        if not tipo_cambio_repo:
            return []
        return await tipo_cambio_repo.get_historico(dias)

    @app.get("/api/convertir")
    async def convertir(monto: float = 1, de: str = "USD", a: str = "PEN"):
        if not currency_service:
            return {"error": "Currency service no disponible"}
        resultado = await currency_service.convert(monto, de, a)
        tasa = await currency_service.get_rate(de, a)
        return {"resultado": resultado, "tasa": tasa, "de": de, "a": a}

    # --- Memoria ---
    @app.get("/api/memoria")
    async def get_memoria():
        if not memoria_repo:
            return []
        return await memoria_repo.get_all()

    @app.delete("/api/memoria/{memoria_id}")
    async def delete_memoria(memoria_id: int):
        if not memoria_repo:
            return {"error": "Memoria no disponible"}
        await memoria_repo.delete(memoria_id)
        return {"ok": True}

    # --- System Stats (RPi) via WebSocket ---
    async def _read_system_stats() -> dict:
        stats: dict = {}
        # CPU temperature
        try:
            stats["temp"] = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000
        except Exception:
            stats["temp"] = None
        # Memory
        try:
            meminfo = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                parts = line.split()
                if parts[0].rstrip(":") in ("MemTotal", "MemAvailable"):
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
            total = meminfo.get("MemTotal", 0)
            avail = meminfo.get("MemAvailable", 0)
            used = total - avail
            stats["mem_total_mb"] = round(total / 1024)
            stats["mem_used_mb"] = round(used / 1024)
            stats["mem_pct"] = round(used / total * 100) if total else 0
        except Exception:
            stats["mem_total_mb"] = stats["mem_used_mb"] = stats["mem_pct"] = None
        # CPU usage (sample /proc/stat over 0.5s)
        try:
            def read_cpu():
                line = Path("/proc/stat").read_text().splitlines()[0]
                vals = [int(v) for v in line.split()[1:]]
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                total = sum(vals)
                return idle, total
            idle1, total1 = read_cpu()
            await asyncio.sleep(0.2)
            idle2, total2 = read_cpu()
            d_total = total2 - total1
            d_idle = idle2 - idle1
            stats["cpu_pct"] = round((1 - d_idle / d_total) * 100) if d_total else 0
        except Exception:
            stats["cpu_pct"] = None
        # Disk
        try:
            st = os.statvfs("/")
            total_bytes = st.f_frsize * st.f_blocks
            free_bytes = st.f_frsize * st.f_bavail
            used_bytes = total_bytes - free_bytes
            stats["disk_total_gb"] = round(total_bytes / (1024**3), 1)
            stats["disk_used_gb"] = round(used_bytes / (1024**3), 1)
            stats["disk_pct"] = round(used_bytes / total_bytes * 100) if total_bytes else 0
        except Exception:
            stats["disk_total_gb"] = stats["disk_used_gb"] = stats["disk_pct"] = None
        # WiFi signal
        try:
            wireless = Path("/proc/net/wireless").read_text().splitlines()
            for line in wireless:
                if "wlan0" in line:
                    parts = line.split()
                    stats["wifi_dbm"] = int(float(parts[3]))  # signal level dBm
                    break
        except Exception:
            stats["wifi_dbm"] = None
        # Uptime
        try:
            uptime_secs = float(Path("/proc/uptime").read_text().split()[0])
            days = int(uptime_secs // 86400)
            hours = int((uptime_secs % 86400) // 3600)
            mins = int((uptime_secs % 3600) // 60)
            if days > 0:
                stats["uptime"] = f"{days}d {hours}h"
            elif hours > 0:
                stats["uptime"] = f"{hours}h {mins}m"
            else:
                stats["uptime"] = f"{mins}m"
        except Exception:
            stats["uptime"] = None
        return stats

    _stats_task = None

    async def _stats_broadcast_loop():
        while True:
            try:
                if ws_manager.connections:
                    stats = await _read_system_stats()
                    if sonoff_service and sonoff_service.latest:
                        stats["power_w"] = sonoff_service.latest.get("power_w")
                        stats["voltage_v"] = sonoff_service.latest.get("voltage_v")
                        stats["current_a"] = sonoff_service.latest.get("current_a")
                        stats["day_kwh"] = sonoff_service.latest.get("day_kwh")
                        stats["month_kwh"] = sonoff_service.latest.get("month_kwh")
                    if printer_service and printer_service.latest:
                        stats["printer"] = printer_service.latest
                    if _sensor_data:
                        stats["sensors"] = _sensor_data
                    await ws_manager.broadcast({"type": "system_stats", **stats})
            except Exception:
                logger.debug("Stats broadcast error", exc_info=True)
            await asyncio.sleep(1)

    def _ensure_stats_loop():
        nonlocal _stats_task
        if _stats_task is None or _stats_task.done():
            _stats_task = asyncio.create_task(_stats_broadcast_loop())

    # --- External Sensors (ESP32 SHT31, etc.) ---
    _sensor_data: dict = {}  # latest readings by device_id

    @app.post("/api/sensors")
    async def receive_sensor_data(data: dict):
        device_id = data.get("device_id", "unknown")
        _sensor_data[device_id] = {
            "temperature": data.get("temperature"),
            "humidity": data.get("humidity"),
            "device_id": device_id,
            "updated_at": __import__("datetime").datetime.now().isoformat(),
        }
        logger.info(f"[sensor] {device_id}: T={data.get('temperature')}°C H={data.get('humidity')}%")
        return {"ok": True}

    @app.get("/api/sensors")
    async def get_sensors():
        return _sensor_data

    # --- Consumos (agua, luz, gas) ---
    @app.get("/api/consumos")
    async def get_consumos(tipo: str = "luz", mes: str = None):
        if not consumo_repo:
            return []
        return await consumo_repo.get_by_month(tipo, mes)

    @app.get("/api/consumos/actual")
    async def get_consumo_actual():
        if sonoff_service and sonoff_service.latest:
            return sonoff_service.latest
        return {}

    @app.get("/api/consumos/resumen")
    async def get_consumo_resumen(mes: str = None):
        if not consumo_repo:
            return []
        return await consumo_repo.get_all_resumen(mes)

    @app.post("/api/consumos")
    async def create_consumo(data: dict):
        if not consumo_repo:
            return {"error": "Consumos no disponible"}
        doc_id = await consumo_repo.create(
            tipo=data["tipo"],
            valor=data["valor"],
            unidad=data.get("unidad", "m3"),
            fecha=data["fecha"],
            source="manual",
            costo=data.get("costo"),
        )
        return {"id": doc_id}

    @app.delete("/api/consumos/{consumo_id}")
    async def delete_consumo(consumo_id: int):
        if not consumo_repo:
            return {"error": "Consumos no disponible"}
        await consumo_repo.delete(consumo_id)
        return {"ok": True}

    # --- Consumos: chart, periodo, pagos, config ---
    @app.get("/api/consumos/chart")
    async def get_consumo_chart(tipo: str = "luz", desde: str = "", hasta: str = "",
                                 slice: int = 1):
        if not consumo_repo:
            return []
        if not desde:
            from datetime import datetime, timedelta
            desde = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
        if not hasta:
            from datetime import datetime
            hasta = datetime.now().strftime("%Y-%m-%dT23:59:59")
        return await consumo_repo.get_chart_data(tipo, desde, hasta, slice)

    @app.get("/api/consumos/periodo")
    async def get_consumo_periodo(tipo: str = "luz", desde: str = "", hasta: str = ""):
        if not consumo_repo:
            return {"error": "Consumos no disponible"}
        return await consumo_repo.get_consumo_periodo(tipo, desde, hasta)

    @app.get("/api/consumos/pagos")
    async def get_consumo_pagos(tipo: str = "luz"):
        if not pago_consumo_repo:
            return []
        return await pago_consumo_repo.get_all(tipo)

    @app.post("/api/consumos/pagos")
    async def create_consumo_pago(data: dict):
        if not pago_consumo_repo:
            return {"error": "Pagos de consumo no disponible"}
        # Auto-calculate kWh and costo_kwh if consumo data available
        kwh = data.get("kwh_periodo")
        costo_kwh = data.get("costo_kwh")
        if consumo_repo and data.get("fecha_desde") and data.get("fecha_hasta"):
            if kwh is None:
                periodo = await consumo_repo.get_consumo_periodo(
                    data.get("tipo", "luz"), data["fecha_desde"], data["fecha_hasta"])
                kwh = periodo.get("kwh_total")
            if kwh and kwh > 0 and costo_kwh is None:
                costo_kwh = round(data["monto"] / kwh, 4)
        doc_id = await pago_consumo_repo.create(
            tipo=data.get("tipo", "luz"),
            monto=data["monto"],
            fecha_pago=data["fecha_pago"],
            fecha_desde=data.get("fecha_desde", ""),
            fecha_hasta=data.get("fecha_hasta", ""),
            kwh_periodo=kwh,
            costo_kwh=costo_kwh,
            notas=data.get("notas", ""),
        )
        return {"id": doc_id, "kwh_periodo": kwh, "costo_kwh": costo_kwh}

    @app.delete("/api/consumos/pagos/{pago_id}")
    async def delete_consumo_pago(pago_id: int):
        if not pago_consumo_repo:
            return {"error": "Pagos de consumo no disponible"}
        await pago_consumo_repo.delete(pago_id)
        return {"ok": True}

    @app.get("/api/consumos/config")
    async def get_consumo_config():
        if not consumo_config_repo:
            return {}
        return await consumo_config_repo.get_all()

    @app.post("/api/consumos/config")
    async def save_consumo_config(data: dict):
        if not consumo_config_repo:
            return {"error": "Config no disponible"}
        for clave, valor in data.items():
            await consumo_config_repo.set(clave, str(valor))
        return {"ok": True}

    # --- Gastos Fijos ---
    @app.get("/api/gastos-fijos")
    async def get_gastos_fijos(solo_activos: bool = True):
        if not gasto_fijo_repo:
            return []
        return await gasto_fijo_repo.get_all(solo_activos=solo_activos)

    @app.post("/api/gastos-fijos")
    async def create_gasto_fijo(data: dict):
        if not gasto_fijo_repo:
            return {"error": "No disponible"}
        gf_id = await gasto_fijo_repo.create(
            nombre=data.get("nombre", ""),
            monto=data.get("monto", 0),
            frecuencia=data.get("frecuencia", "mensual"),
            dia=data.get("dia", 1),
            **{k: v for k, v in data.items() if k not in ("nombre", "monto", "frecuencia", "dia")}
        )
        return {"id": gf_id}

    @app.post("/api/gastos-fijos/{gf_id}/toggle")
    async def toggle_gasto_fijo(gf_id: int):
        if not gasto_fijo_repo:
            return {"error": "No disponible"}
        gf = await gasto_fijo_repo.get_by_id(gf_id)
        if not gf:
            return JSONResponse({"error": "No encontrado"}, 404)
        if gf.get("activo"):
            await gasto_fijo_repo.desactivar(gf_id)
        else:
            await gasto_fijo_repo.activar(gf_id)
        return {"ok": True}

    @app.delete("/api/gastos-fijos/{gf_id}")
    async def delete_gasto_fijo(gf_id: int):
        if not gasto_fijo_repo:
            return {"error": "No disponible"}
        await gasto_fijo_repo.delete(gf_id)
        return {"ok": True}

    # --- LLM Usage / Analytics ---
    @app.get("/api/llm-usage/summary")
    async def llm_usage_summary(mes: str = ""):
        if not llm_usage_repo:
            return {}
        rows = await llm_usage_repo.get_summary_month(mes or None)
        # Aggregate into single summary
        total_calls = sum(r["calls"] for r in rows)
        total_input = sum(r["total_input"] for r in rows)
        total_output = sum(r["total_output"] for r in rows)
        cost = llm_usage_repo.estimate_cost(total_input, total_output)
        return {"calls": total_calls, "input_tokens": total_input,
                "output_tokens": total_output, "cost_usd": cost, "by_model": rows}

    @app.get("/api/llm-usage/daily")
    async def llm_usage_daily(mes: str = ""):
        if not llm_usage_repo:
            return []
        return await llm_usage_repo.get_daily_breakdown(mes or None)

    @app.get("/api/llm-usage/by-caller")
    async def llm_usage_by_caller(mes: str = ""):
        if not llm_usage_repo:
            return []
        return await llm_usage_repo.get_by_caller(mes or None)

    @app.get("/api/llm-usage/recent")
    async def llm_usage_recent(limit: int = 30):
        if not llm_usage_repo:
            return []
        return await llm_usage_repo.get_recent(limit)

    # --- Logs Stream (SSE) ---
    @app.get("/api/logs/stream")
    async def logs_stream():
        from starlette.responses import StreamingResponse

        async def event_generator():
            # Follow journalctl with last 200 lines of history
            proc = await asyncio.create_subprocess_exec(
                "journalctl", "-u", "finbot", "-f", "-n", "200", "--no-pager",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    yield f"data: {json.dumps({'line': line.decode().rstrip()})}\n\n"
            except asyncio.CancelledError:
                proc.kill()
            finally:
                proc.kill()

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # --- Printer ---
    @app.get("/api/printer/status")
    async def get_printer_status():
        if not printer_service or not printer_service.latest:
            return {"status": "offline"}
        return printer_service.latest

    @app.get("/printer/{path:path}")
    async def printer_proxy(path: str):
        """Reverse proxy to the printer's local web UI for remote access via tunnel."""
        if not printer_service or not printer_service._host:
            return JSONResponse({"error": "Printer not found"}, status_code=503)
        import httpx
        url = f"http://{printer_service._host}/{path}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            return JSONResponse(
                content=resp.text if resp.headers.get("content-type", "").startswith("text") else resp.json(),
                status_code=resp.status_code,
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)

    # --- Device control (Google Assistant) ---
    @app.post("/api/devices/command")
    async def device_command(data: dict):
        if not google_assistant:
            return JSONResponse({"error": "Google Assistant no configurado"}, status_code=503)
        command = data.get("command", "").strip()
        if not command:
            return JSONResponse({"error": "Falta el campo 'command'"}, status_code=400)
        try:
            response = await google_assistant.send_command(command)
            return {"ok": True, "response": response}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # --- Controls (NSPanel smart home) ---
    @app.get("/api/controls")
    async def get_controls():
        if not control_repo:
            return []
        return await control_repo.get_all()

    @app.post("/api/controls")
    async def create_control(data: dict):
        if not control_repo:
            return {"error": "Controls no disponible"}
        control_id = await control_repo.create(data)
        await ws_manager.broadcast({"type": "controls_changed", "controls": await control_repo.get_all()})
        return {"id": control_id}

    @app.put("/api/controls/reorder")
    async def reorder_controls(data: dict):
        if not control_repo:
            return {"error": "Controls no disponible"}
        await control_repo.reorder(data.get("ids", []))
        await ws_manager.broadcast({"type": "controls_changed", "controls": await control_repo.get_all()})
        return {"ok": True}

    @app.put("/api/controls/{control_id}")
    async def update_control(control_id: str, data: dict):
        if not control_repo:
            return {"error": "Controls no disponible"}
        ok = await control_repo.update(control_id, data)
        if not ok:
            return JSONResponse({"error": "Control no encontrado"}, status_code=404)
        await ws_manager.broadcast({"type": "controls_changed", "controls": await control_repo.get_all()})
        return {"ok": True}

    @app.delete("/api/controls/{control_id}")
    async def delete_control(control_id: str):
        if not control_repo:
            return {"error": "Controls no disponible"}
        ok = await control_repo.delete(control_id)
        if not ok:
            return JSONResponse({"error": "Control no encontrado"}, status_code=404)
        await ws_manager.broadcast({"type": "controls_changed", "controls": await control_repo.get_all()})
        return {"ok": True}

    @app.post("/api/controls/{control_id}/toggle")
    async def toggle_control(control_id: str):
        if not control_repo:
            return {"error": "Controls no disponible"}
        result = await control_repo.toggle(control_id)
        if not result:
            return JSONResponse({"error": "Control no encontrado"}, status_code=404)
        await ws_manager.broadcast({"type": "control_toggle", "id": control_id, "is_active": result["is_active"]})
        return result

    # --- Health ---
    @app.get("/api/health")
    async def health():
        wa_status = await whatsapp_channel.get_status()
        return {"status": "ok", "whatsapp": wa_status}

    # Static files for assets
    if Path("web/assets").exists():
        app.mount("/assets", StaticFiles(directory="web/assets"), name="assets")
    if Path("web/css").exists():
        app.mount("/css", StaticFiles(directory="web/css"), name="css")
    if Path("web/js").exists():
        app.mount("/js", StaticFiles(directory="web/js"), name="js")

    # SPA fallback: any unmatched route serves index.html for React Router
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse("web/index.html")

    return app
