import json
import base64
import logging
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
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
               perfil_repo=None, cuenta_repo=None,
               lifespan=None) -> FastAPI:

    app = FastAPI(title="FinBot", docs_url="/api/docs", lifespan=lifespan)

    # --- Auth middleware ---
    app.add_middleware(AuthMiddleware)

    # --- Login page ---
    @app.get("/login")
    async def login_page():
        return FileResponse("web/login.html")

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
    async def upload_receipt(file: UploadFile = File(...)):
        content = await file.read()
        media = {
            "mimetype": file.content_type,
            "data": base64.b64encode(content).decode(),
        }
        await message_bus.handle_incoming(text="", media=media, source="web")
        return {"ok": True}

    # --- Chat history ---
    @app.get("/api/mensajes")
    async def get_mensajes(limit: int = 50, before: int = None):
        return await mensaje_repo.get_history(limit=limit, before=before)

    # --- Gastos ---
    @app.get("/api/gastos")
    async def get_gastos(mes: str = None):
        return await gasto_repo.get_by_month(mes)

    @app.get("/api/gastos/hoy")
    async def get_gastos_hoy():
        return await gasto_repo.get_today()

    @app.delete("/api/gastos/{gasto_id}")
    async def delete_gasto(gasto_id: int):
        await gasto_repo.delete(gasto_id)
        return {"ok": True}

    # --- Ingresos ---
    @app.get("/api/ingresos")
    async def get_ingresos(mes: str = None):
        return await ingreso_repo.get_by_month(mes)

    # --- Resúmenes ---
    @app.get("/api/resumen/diario")
    async def resumen_diario():
        return {"text": await gasto_repo.resumen_hoy()}

    @app.get("/api/resumen/semanal")
    async def resumen_semanal():
        return {"text": await gasto_repo.resumen_semana()}

    @app.get("/api/resumen/mensual")
    async def resumen_mensual():
        return {"text": await gasto_repo.resumen_mes()}

    @app.get("/api/resumen/categorias")
    async def resumen_categorias(mes: str = None):
        return await gasto_repo.resumen_categorias(mes)

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

    @app.delete("/api/cuentas/{cuenta_id}")
    async def delete_cuenta(cuenta_id: int):
        if not cuenta_repo:
            return {"error": "Cuentas no disponible"}
        await cuenta_repo.delete(cuenta_id)
        return {"ok": True}

    # --- Dashboard extras ---
    @app.get("/api/dashboard/top-comercios")
    async def top_comercios(mes: str = None):
        return await gasto_repo.top_comercios(mes)

    @app.get("/api/dashboard/metodos-pago")
    async def metodos_pago(mes: str = None):
        return await gasto_repo.metodo_pago_breakdown(mes)

    # --- WhatsApp status ---
    @app.get("/api/whatsapp/qr")
    async def get_qr():
        return {"qr": await whatsapp_channel.get_qr()}

    @app.get("/api/whatsapp/status")
    async def get_wa_status():
        return await whatsapp_channel.get_status()

    # --- Health ---
    @app.get("/api/health")
    async def health():
        wa_status = await whatsapp_channel.get_status()
        return {"status": "ok", "whatsapp": wa_status}

    # Static files (web dashboard) — mount last so it doesn't override API routes
    app.mount("/", StaticFiles(directory="web", html=True), name="web")

    return app
