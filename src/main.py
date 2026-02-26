"""
FinBot v6 — Entry point.
Run: python3 src/main.py  (or python src/main.py on Windows)
Handles all setup automatically: venv, pip, node, npm, chromium.
"""
import subprocess
import shutil
import sys
import os
import platform
from pathlib import Path

# ---------------------------------------------------------------------------
# BOOTSTRAP — runs with stdlib only, before any third-party import
# ---------------------------------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Ensure project root is in sys.path so "from src.*" works
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
VENV_DIR = PROJECT_ROOT / "venv"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
BRIDGE_DIR = PROJECT_ROOT / "whatsapp-bridge"


def _print(msg: str):
    print(f"[finbot] {msg}", flush=True)


def _in_venv() -> bool:
    return sys.prefix != sys.base_prefix


def _venv_python() -> str:
    if IS_WINDOWS:
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "Scripts" / "python3") if (VENV_DIR / "Scripts").exists() else str(VENV_DIR / "bin" / "python3")


def _run(cmd: list[str], **kwargs) -> bool:
    try:
        subprocess.run(cmd, check=True, shell=IS_WINDOWS, **kwargs)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


# ---- System dependencies ----

def ensure_node():
    if _cmd_exists("node"):
        return
    _print("Node.js no encontrado. Instalando...")
    if IS_WINDOWS:
        if not _run(["winget", "install", "OpenJS.NodeJS.LTS",
                      "--accept-package-agreements", "--accept-source-agreements"]):
            _print("ERROR: No se pudo instalar Node.js. Instala desde https://nodejs.org")
            sys.exit(1)
        _print("Node.js instalado. Reinicia la terminal y ejecuta de nuevo.")
        sys.exit(0)
    else:
        # Linux / WSL / RPi
        _run(["sudo", "apt-get", "update", "-qq"])
        if not _run(["sudo", "apt-get", "install", "-y", "nodejs", "npm"]):
            _print("ERROR: No se pudo instalar Node.js. Instala manualmente.")
            sys.exit(1)


def ensure_chromium():
    if IS_WINDOWS:
        return  # Bridge auto-detecta Chrome/Edge/Brave en Windows
    # Linux: intentar instalar chromium si no existe
    for name in ("chromium-browser", "chromium", "google-chrome"):
        if _cmd_exists(name):
            return
    _print("Chromium no encontrado. Instalando...")
    _run(["sudo", "apt-get", "install", "-y", "chromium-browser"]) or \
        _run(["sudo", "apt-get", "install", "-y", "chromium"])


# ---- Python venv + deps ----

def ensure_venv():
    if _in_venv():
        return
    if not VENV_DIR.exists():
        _print("Creando entorno virtual...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    # Install/update pip dependencies inside venv
    vpy = _venv_python()
    _print("Instalando dependencias Python...")
    subprocess.run([vpy, "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS)], check=True)

    # Re-launch ourselves inside the venv
    _print("Reiniciando dentro del venv...")
    os.execv(vpy, [vpy, __file__])


# ---- Bridge npm deps ----

def ensure_bridge_deps():
    if (BRIDGE_DIR / "node_modules").exists():
        return
    _print("Instalando dependencias del bridge WhatsApp...")
    npm = "npm.cmd" if IS_WINDOWS else "npm"
    _run([npm, "install"], cwd=str(BRIDGE_DIR))


# ---- Data dirs + .env ----

def ensure_data():
    (PROJECT_ROOT / "data" / "receipts").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "knowledge").mkdir(parents=True, exist_ok=True)

    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        example = PROJECT_ROOT / ".env.example"
        if example.exists():
            shutil.copy(example, env_file)
            _print(".env creado desde .env.example — configura tus variables.")
        else:
            _print("WARNING: .env no encontrado.")


def bootstrap():
    os.chdir(PROJECT_ROOT)
    _print("Verificando dependencias...")
    ensure_node()
    ensure_chromium()
    ensure_venv()      # <- puede hacer os.execv() y no retorna
    ensure_bridge_deps()
    ensure_data()
    _print("Todo listo.")


# ---------------------------------------------------------------------------
# APP — only runs after bootstrap, inside venv with all deps available
# ---------------------------------------------------------------------------

def run_app():
    import logging
    import threading
    from contextlib import asynccontextmanager

    import uvicorn

    from src.config import settings
    from src.database.db import init_db, close_db
    from src.repository.mensaje_repo import MensajeRepo
    from src.repository.gasto_repo import GastoRepo
    from src.repository.ingreso_repo import IngresoRepo
    from src.repository.deuda_repo import DeudaRepo
    from src.repository.presupuesto_repo import PresupuestoRepo
    from src.repository.perfil_repo import PerfilRepo
    from src.repository.cuenta_repo import CuentaRepo
    from src.services.parser import AgentParser
    from src.services.receipt_parser import ReceiptParser
    from src.services.document_parser import DocumentParser
    from src.services.budget import BudgetService
    from src.services.scheduler import SchedulerService
    from src.channels.whatsapp import WhatsAppChannel
    from src.channels.web import WebSocketManager, create_app
    from src.bus.message_bus import MessageBus
    from src.bot.processor import Processor

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("finbot")

    # ---- Bridge ----
    bridge_process = None

    def start_bridge():
        nonlocal bridge_process
        node = "node.exe" if IS_WINDOWS else "node"
        env = os.environ.copy()
        env["PYTHON_WEBHOOK"] = f"http://localhost:{settings.port}/webhook/whatsapp"
        env["BRIDGE_PORT"] = str(settings.bridge_port)

        bridge_process = subprocess.Popen(
            [node, "index.js"],
            cwd=str(BRIDGE_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=IS_WINDOWS,
        )
        logger.info(f"WhatsApp bridge started (PID {bridge_process.pid}) on :{settings.bridge_port}")

        def _log():
            for line in bridge_process.stdout:
                logger.info(f"[bridge] {line.decode().rstrip()}")
        threading.Thread(target=_log, daemon=True).start()

    def stop_bridge():
        nonlocal bridge_process
        if bridge_process:
            logger.info("Stopping WhatsApp bridge...")
            bridge_process.terminate()
            try:
                bridge_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bridge_process.kill()
            bridge_process = None

    # ---- Wiring (sync — no DB needed yet) ----
    mensaje_repo = MensajeRepo()
    gasto_repo = GastoRepo()
    ingreso_repo = IngresoRepo()
    deuda_repo = DeudaRepo()
    presupuesto_repo = PresupuestoRepo()
    perfil_repo = PerfilRepo()
    cuenta_repo = CuentaRepo()

    agent_parser = AgentParser(api_key=settings.google_ai_api_key)
    receipt_parser = ReceiptParser(api_key=settings.google_ai_api_key)
    document_parser = DocumentParser(api_key=settings.google_ai_api_key)
    budget_service = BudgetService(presupuesto_repo=presupuesto_repo, gasto_repo=gasto_repo, perfil_repo=perfil_repo)

    whatsapp = WhatsAppChannel()
    ws_manager = WebSocketManager()

    processor = Processor(
        agent_parser=agent_parser,
        receipt_parser=receipt_parser,
        gasto_repo=gasto_repo,
        ingreso_repo=ingreso_repo,
        budget_service=budget_service,
        deuda_repo=deuda_repo,
        perfil_repo=perfil_repo,
        cuenta_repo=cuenta_repo,
        presupuesto_repo=presupuesto_repo,
        mensaje_repo=mensaje_repo,
        document_parser=document_parser,
    )

    message_bus = MessageBus(
        mensaje_repo=mensaje_repo,
        processor=processor,
        whatsapp=whatsapp,
        ws_manager=ws_manager,
    )

    scheduler = SchedulerService(
        message_bus=message_bus,
        gasto_repo=gasto_repo,
        presupuesto_repo=presupuesto_repo,
        budget_service=budget_service,
        perfil_repo=perfil_repo,
        timezone=settings.timezone,
    )

    # ---- Lifespan ----
    @asynccontextmanager
    async def lifespan(app):
        await init_db()
        logger.info("SQLite database ready")
        scheduler.start()
        yield
        scheduler.stop()
        await whatsapp.close()
        await close_db()
        logger.info("Cleanup complete")

    app = create_app(
        message_bus=message_bus,
        mensaje_repo=mensaje_repo,
        gasto_repo=gasto_repo,
        ingreso_repo=ingreso_repo,
        presupuesto_repo=presupuesto_repo,
        deuda_repo=deuda_repo,
        perfil_repo=perfil_repo,
        cuenta_repo=cuenta_repo,
        whatsapp_channel=whatsapp,
        ws_manager=ws_manager,
        lifespan=lifespan,
    )

    # ---- Start ----
    start_bridge()

    logger.info(f"Starting FinBot on :{settings.port}")
    logger.info(f"Web: http://localhost:{settings.port}")

    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=settings.port,
            workers=settings.uvicorn_workers,
            log_level="info",
        )
    finally:
        stop_bridge()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bootstrap()
    run_app()
