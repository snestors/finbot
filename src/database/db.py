import aiosqlite
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("data/finbot.db")
_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    media_path TEXT,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    gasto_ids TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monto REAL NOT NULL,
    categoria TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    fuente TEXT NOT NULL,
    fecha TEXT NOT NULL,
    mes TEXT NOT NULL,
    semana TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingresos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monto REAL NOT NULL,
    fuente TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    mes TEXT NOT NULL,
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deudas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    saldo_actual REAL NOT NULL DEFAULT 0,
    tasa_interes_mensual REAL NOT NULL DEFAULT 0,
    pago_minimo REAL NOT NULL DEFAULT 0,
    fecha_corte INTEGER DEFAULT 0,
    fecha_pago INTEGER DEFAULT 0,
    activa INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS deuda_pagos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deuda_id INTEGER NOT NULL,
    monto REAL NOT NULL,
    fecha TEXT NOT NULL,
    FOREIGN KEY (deuda_id) REFERENCES deudas(id)
);

CREATE TABLE IF NOT EXISTS presupuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL UNIQUE,
    limite_mensual REAL NOT NULL,
    alerta_porcentaje REAL NOT NULL DEFAULT 80
);

CREATE INDEX IF NOT EXISTS idx_gastos_mes ON gastos(mes);
CREATE INDEX IF NOT EXISTS idx_gastos_semana ON gastos(semana);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria_mes ON gastos(categoria, mes);
CREATE INDEX IF NOT EXISTS idx_ingresos_mes ON ingresos(mes);
CREATE INDEX IF NOT EXISTS idx_mensajes_timestamp ON mensajes(timestamp);
"""


async def init_db():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    logger.info(f"SQLite initialized: {DB_PATH}")


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
