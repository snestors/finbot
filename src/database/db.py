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
    semana TEXT NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    comercio TEXT,
    metodo_pago TEXT,
    cuenta_id INTEGER
);

CREATE TABLE IF NOT EXISTS ingresos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monto REAL NOT NULL,
    fuente TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    mes TEXT NOT NULL,
    fecha TEXT NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    cuenta_id INTEGER
);

CREATE TABLE IF NOT EXISTS deudas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    saldo_actual REAL NOT NULL DEFAULT 0,
    tasa_interes_mensual REAL NOT NULL DEFAULT 0,
    pago_minimo REAL NOT NULL DEFAULT 0,
    fecha_corte INTEGER DEFAULT 0,
    fecha_pago INTEGER DEFAULT 0,
    activa INTEGER NOT NULL DEFAULT 1,
    entidad TEXT,
    cuotas_total INTEGER DEFAULT 0,
    cuotas_pagadas INTEGER DEFAULT 0,
    cuota_monto REAL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS perfil_usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    moneda_default TEXT NOT NULL DEFAULT 'PEN',
    onboarding_completo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cuentas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'efectivo',
    moneda TEXT NOT NULL DEFAULT 'PEN',
    saldo REAL NOT NULL DEFAULT 0,
    color TEXT DEFAULT '#00f0ff',
    activa INTEGER NOT NULL DEFAULT 1
);


CREATE TABLE IF NOT EXISTS cobros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deudor TEXT NOT NULL,
    concepto TEXT NOT NULL DEFAULT '',
    monto_total REAL NOT NULL,
    saldo_pendiente REAL NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cobro_pagos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cobro_id INTEGER NOT NULL,
    monto REAL NOT NULL,
    fecha TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cobro_id) REFERENCES cobros(id)
);

CREATE TABLE IF NOT EXISTS tarjetas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    banco TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'credito',
    ultimos_4 TEXT DEFAULT '',
    limite_credito REAL DEFAULT 0,
    fecha_corte INTEGER DEFAULT 1,
    fecha_pago INTEGER DEFAULT 15,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    activa INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_gastos_mes ON gastos(mes);
CREATE INDEX IF NOT EXISTS idx_gastos_semana ON gastos(semana);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria_mes ON gastos(categoria, mes);
CREATE INDEX IF NOT EXISTS idx_ingresos_mes ON ingresos(mes);
CREATE INDEX IF NOT EXISTS idx_mensajes_timestamp ON mensajes(timestamp);
"""

MIGRATIONS = [
    ("gastos", "moneda", "ALTER TABLE gastos ADD COLUMN moneda TEXT NOT NULL DEFAULT 'PEN'"),
    ("gastos", "comercio", "ALTER TABLE gastos ADD COLUMN comercio TEXT"),
    ("gastos", "metodo_pago", "ALTER TABLE gastos ADD COLUMN metodo_pago TEXT"),
    ("gastos", "cuenta_id", "ALTER TABLE gastos ADD COLUMN cuenta_id INTEGER"),
    ("ingresos", "moneda", "ALTER TABLE ingresos ADD COLUMN moneda TEXT NOT NULL DEFAULT 'PEN'"),
    ("ingresos", "cuenta_id", "ALTER TABLE ingresos ADD COLUMN cuenta_id INTEGER"),
    ("deudas", "entidad", "ALTER TABLE deudas ADD COLUMN entidad TEXT"),
    ("deudas", "cuotas_total", "ALTER TABLE deudas ADD COLUMN cuotas_total INTEGER DEFAULT 0"),
    ("deudas", "cuotas_pagadas", "ALTER TABLE deudas ADD COLUMN cuotas_pagadas INTEGER DEFAULT 0"),
    ("deudas", "cuota_monto", "ALTER TABLE deudas ADD COLUMN cuota_monto REAL DEFAULT 0"),
]


async def _run_migrations(db: aiosqlite.Connection):
    for table, column, sql in MIGRATIONS:
        try:
            await db.execute(sql)
            logger.info(f"Migration: added {table}.{column}")
        except Exception:
            pass  # Column already exists
    await db.commit()


async def init_db():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _run_migrations(_db)
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
