import aiosqlite
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("data/finbot.db")
_db: aiosqlite.Connection | None = None

CURRENT_SCHEMA_VERSION = 4  # v4 = consumos extended + pagos_consumo + consumo_config

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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
    saldo_inicial REAL NOT NULL DEFAULT 0,
    metodos_pago TEXT NOT NULL DEFAULT '[]',
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
CREATE TABLE IF NOT EXISTS memoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL,
    clave TEXT NOT NULL,
    valor TEXT NOT NULL,
    confianza REAL NOT NULL DEFAULT 1.0,
    veces_confirmado INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(categoria, clave)
);

CREATE TABLE IF NOT EXISTS recordatorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mensaje TEXT NOT NULL,
    hora TEXT NOT NULL,
    dias TEXT NOT NULL DEFAULT 'todos',
    activo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gastos_mes ON gastos(mes);
CREATE INDEX IF NOT EXISTS idx_gastos_semana ON gastos(semana);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria_mes ON gastos(categoria, mes);
CREATE INDEX IF NOT EXISTS idx_ingresos_mes ON ingresos(mes);
CREATE INDEX IF NOT EXISTS idx_mensajes_timestamp ON mensajes(timestamp);
CREATE INDEX IF NOT EXISTS idx_memoria_categoria ON memoria(categoria);

CREATE TABLE IF NOT EXISTS gasto_cuotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gasto_id INTEGER NOT NULL,
    numero_cuota INTEGER NOT NULL,
    cuotas_total INTEGER NOT NULL,
    monto_cuota REAL NOT NULL,
    fecha_cargo TEXT NOT NULL,
    pagada INTEGER NOT NULL DEFAULT 0,
    tarjeta_id INTEGER,
    periodo_facturacion TEXT,
    FOREIGN KEY (gasto_id) REFERENCES gastos(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_gasto_cuotas_gasto ON gasto_cuotas(gasto_id);
CREATE INDEX IF NOT EXISTS idx_gasto_cuotas_tarjeta_periodo ON gasto_cuotas(tarjeta_id, periodo_facturacion);

CREATE TABLE IF NOT EXISTS tipo_cambio_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL UNIQUE,
    compra REAL NOT NULL,
    venta REAL NOT NULL,
    fuente TEXT NOT NULL DEFAULT 'SUNAT',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tipo_cambio_fecha ON tipo_cambio_historico(fecha);

CREATE INDEX IF NOT EXISTS idx_gastos_cuenta_id ON gastos(cuenta_id);
CREATE INDEX IF NOT EXISTS idx_gastos_tarjeta_id ON gastos(tarjeta_id);

CREATE TABLE IF NOT EXISTS transferencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cuenta_origen_id INTEGER NOT NULL,
    cuenta_destino_id INTEGER NOT NULL,
    monto REAL NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    monto_origen REAL NOT NULL,
    monto_destino REAL NOT NULL,
    descripcion TEXT DEFAULT '',
    fecha TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (cuenta_origen_id) REFERENCES cuentas(id),
    FOREIGN KEY (cuenta_destino_id) REFERENCES cuentas(id)
);
CREATE INDEX IF NOT EXISTS idx_transferencias_origen ON transferencias(cuenta_origen_id);
CREATE INDEX IF NOT EXISTS idx_transferencias_destino ON transferencias(cuenta_destino_id);

CREATE TABLE IF NOT EXISTS pago_tarjeta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarjeta_id INTEGER NOT NULL,
    cuenta_id INTEGER NOT NULL,
    monto REAL NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    monto_cuenta REAL NOT NULL,
    fecha TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (tarjeta_id) REFERENCES tarjetas(id),
    FOREIGN KEY (cuenta_id) REFERENCES cuentas(id)
);
CREATE INDEX IF NOT EXISTS idx_pago_tarjeta_tarjeta ON pago_tarjeta(tarjeta_id);
CREATE INDEX IF NOT EXISTS idx_pago_tarjeta_cuenta ON pago_tarjeta(cuenta_id);

-- Unified movimientos model (v2)
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    monto REAL NOT NULL,
    moneda TEXT NOT NULL DEFAULT 'PEN',
    monto_cuenta REAL,
    descripcion TEXT NOT NULL DEFAULT '',
    categoria TEXT,
    comercio TEXT,
    metodo_pago TEXT,
    fuente TEXT NOT NULL DEFAULT 'texto',
    cuenta_id INTEGER REFERENCES cuentas(id),
    cuenta_destino_id INTEGER REFERENCES cuentas(id),
    tarjeta_id INTEGER REFERENCES tarjetas(id),
    tarjeta_periodo_id INTEGER REFERENCES tarjeta_periodos(id),
    deuda_id INTEGER REFERENCES deudas(id),
    cobro_id INTEGER REFERENCES cobros(id),
    cuotas INTEGER DEFAULT 0,
    monto_destino REAL,
    fecha TEXT NOT NULL,
    mes TEXT NOT NULL,
    semana TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_movimientos_tipo ON movimientos(tipo);
CREATE INDEX IF NOT EXISTS idx_movimientos_mes ON movimientos(mes);
CREATE INDEX IF NOT EXISTS idx_movimientos_semana ON movimientos(semana);
CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos(fecha);
CREATE INDEX IF NOT EXISTS idx_movimientos_cuenta ON movimientos(cuenta_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_tarjeta ON movimientos(tarjeta_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_categoria_mes ON movimientos(categoria, mes);
CREATE INDEX IF NOT EXISTS idx_movimientos_tipo_mes ON movimientos(tipo, mes);

CREATE TABLE IF NOT EXISTS tarjeta_periodos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tarjeta_id INTEGER NOT NULL REFERENCES tarjetas(id),
    periodo TEXT NOT NULL,
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT NOT NULL,
    fecha_pago TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierto',
    total_facturado REAL DEFAULT 0,
    total_pagado REAL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tarjeta_id, periodo)
);
CREATE INDEX IF NOT EXISTS idx_tarjeta_periodos_tarjeta ON tarjeta_periodos(tarjeta_id);

CREATE TABLE IF NOT EXISTS movimiento_cuotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movimiento_id INTEGER NOT NULL REFERENCES movimientos(id) ON DELETE CASCADE,
    tarjeta_id INTEGER REFERENCES tarjetas(id),
    tarjeta_periodo_id INTEGER REFERENCES tarjeta_periodos(id),
    numero_cuota INTEGER NOT NULL,
    cuotas_total INTEGER NOT NULL,
    monto_cuota REAL NOT NULL,
    fecha_cargo TEXT NOT NULL,
    pagada INTEGER NOT NULL DEFAULT 0,
    periodo_facturacion TEXT
);
CREATE INDEX IF NOT EXISTS idx_movimiento_cuotas_movimiento ON movimiento_cuotas(movimiento_id);
CREATE INDEX IF NOT EXISTS idx_movimiento_cuotas_tarjeta_periodo ON movimiento_cuotas(tarjeta_id, periodo_facturacion);

-- Consumos (agua, luz, gas) - v3
CREATE TABLE IF NOT EXISTS consumos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    valor REAL NOT NULL,
    unidad TEXT NOT NULL,
    costo REAL,
    fecha TEXT NOT NULL,
    mes TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_consumos_tipo_mes ON consumos(tipo, mes);
CREATE INDEX IF NOT EXISTS idx_consumos_fecha ON consumos(fecha);

-- Pagos de consumo (luz, agua, gas) - v4
CREATE TABLE IF NOT EXISTS pagos_consumo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL DEFAULT 'luz',
    monto REAL NOT NULL,
    fecha_pago TEXT NOT NULL,
    fecha_desde TEXT NOT NULL,
    fecha_hasta TEXT NOT NULL,
    kwh_periodo REAL,
    costo_kwh REAL,
    notas TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Configuracion de consumos - v4
CREATE TABLE IF NOT EXISTS consumo_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT NOT NULL UNIQUE,
    valor TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

MIGRATIONS = [
    ("gastos", "moneda", "ALTER TABLE gastos ADD COLUMN moneda TEXT NOT NULL DEFAULT 'PEN'"),
    ("gastos", "comercio", "ALTER TABLE gastos ADD COLUMN comercio TEXT"),
    ("gastos", "metodo_pago", "ALTER TABLE gastos ADD COLUMN metodo_pago TEXT"),
    ("gastos", "cuenta_id", "ALTER TABLE gastos ADD COLUMN cuenta_id INTEGER"),
    ("gastos", "tarjeta_id", "ALTER TABLE gastos ADD COLUMN tarjeta_id INTEGER"),
    ("gastos", "cuotas", "ALTER TABLE gastos ADD COLUMN cuotas INTEGER DEFAULT 0"),
    ("ingresos", "moneda", "ALTER TABLE ingresos ADD COLUMN moneda TEXT NOT NULL DEFAULT 'PEN'"),
    ("ingresos", "cuenta_id", "ALTER TABLE ingresos ADD COLUMN cuenta_id INTEGER"),
    ("deudas", "entidad", "ALTER TABLE deudas ADD COLUMN entidad TEXT"),
    ("deudas", "cuotas_total", "ALTER TABLE deudas ADD COLUMN cuotas_total INTEGER DEFAULT 0"),
    ("deudas", "cuotas_pagadas", "ALTER TABLE deudas ADD COLUMN cuotas_pagadas INTEGER DEFAULT 0"),
    ("deudas", "cuota_monto", "ALTER TABLE deudas ADD COLUMN cuota_monto REAL DEFAULT 0"),
    ("tarjetas", "saldo_usado", "ALTER TABLE tarjetas ADD COLUMN saldo_usado REAL DEFAULT 0"),
    # Modelo financiero v2: saldos calculados
    ("gastos", "monto_cuenta", "ALTER TABLE gastos ADD COLUMN monto_cuenta REAL"),
    ("ingresos", "monto_cuenta", "ALTER TABLE ingresos ADD COLUMN monto_cuenta REAL"),
    ("deuda_pagos", "cuenta_id", "ALTER TABLE deuda_pagos ADD COLUMN cuenta_id INTEGER"),
    ("deuda_pagos", "monto_cuenta", "ALTER TABLE deuda_pagos ADD COLUMN monto_cuenta REAL"),
    ("cobro_pagos", "cuenta_id", "ALTER TABLE cobro_pagos ADD COLUMN cuenta_id INTEGER"),
    ("cobro_pagos", "monto_cuenta", "ALTER TABLE cobro_pagos ADD COLUMN monto_cuenta REAL"),
    ("cuentas", "metodos_pago", "ALTER TABLE cuentas ADD COLUMN metodos_pago TEXT NOT NULL DEFAULT '[]'"),
    # v2: model indicator in messages
    ("mensajes", "model", "ALTER TABLE mensajes ADD COLUMN model TEXT"),
]


async def _run_migrations(db: aiosqlite.Connection):
    for table, column, sql in MIGRATIONS:
        try:
            await db.execute(sql)
            logger.info(f"Migration: added {table}.{column}")
        except Exception:
            pass  # Column already exists

    # Rename cuentas.saldo → saldo_inicial (if saldo column still exists)
    try:
        cursor = await db.execute("PRAGMA table_info(cuentas)")
        cols = [row[1] for row in await cursor.fetchall()]
        if "saldo" in cols and "saldo_inicial" not in cols:
            await db.execute("ALTER TABLE cuentas RENAME COLUMN saldo TO saldo_inicial")
            logger.info("Migration: renamed cuentas.saldo → saldo_inicial")
    except Exception as e:
        logger.debug(f"saldo rename skip: {e}")

    # Backfill monto_cuenta = monto where NULL
    await db.execute("UPDATE gastos SET monto_cuenta = monto WHERE monto_cuenta IS NULL")
    await db.execute("UPDATE ingresos SET monto_cuenta = monto WHERE monto_cuenta IS NULL")
    await db.execute("UPDATE deuda_pagos SET monto_cuenta = monto WHERE monto_cuenta IS NULL")
    await db.execute("UPDATE cobro_pagos SET monto_cuenta = monto WHERE monto_cuenta IS NULL")

    await db.commit()


def _backup_db():
    """Create a timestamped backup of the database before migration."""
    if not DB_PATH.exists():
        return
    backup_dir = DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"finbot_{ts}.db"
    shutil.copy2(str(DB_PATH), str(backup_path))
    logger.info(f"Database backup created: {backup_path}")


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    try:
        cursor = await db.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        return row[0] if row and row[0] else 0
    except Exception:
        return 0


async def _set_schema_version(db: aiosqlite.Connection, version: int):
    await db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    await db.commit()


async def _migrate_to_v2(db: aiosqlite.Connection):
    """Migrate data from legacy tables to unified movimientos table."""
    version = await _get_schema_version(db)
    if version >= 2:
        logger.info("Schema already at v2+, skipping migration")
        return

    logger.info("Starting v2 migration: unifying into movimientos...")

    # Migrate gastos → movimientos (tipo='gasto')
    try:
        await db.execute("""
            INSERT INTO movimientos (tipo, monto, moneda, monto_cuenta, descripcion, categoria,
                comercio, metodo_pago, fuente, cuenta_id, tarjeta_id, cuotas, fecha, mes, semana, created_at)
            SELECT 'gasto', monto, COALESCE(moneda, 'PEN'), monto_cuenta, COALESCE(descripcion, ''),
                categoria, comercio, metodo_pago, COALESCE(fuente, 'texto'), cuenta_id, tarjeta_id,
                COALESCE(cuotas, 0), fecha, mes, semana, fecha
            FROM gastos
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM gastos")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} gastos → movimientos")
    except Exception as e:
        logger.warning(f"  gastos migration: {e}")

    # Migrate ingresos → movimientos (tipo='ingreso')
    try:
        await db.execute("""
            INSERT INTO movimientos (tipo, monto, moneda, monto_cuenta, descripcion, fuente,
                cuenta_id, fecha, mes, semana, created_at)
            SELECT 'ingreso', monto, COALESCE(moneda, 'PEN'), monto_cuenta,
                COALESCE(descripcion, ''), COALESCE(fuente, 'texto'), cuenta_id, fecha, mes,
                strftime('%Y-W%W', fecha), fecha
            FROM ingresos
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM ingresos")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} ingresos → movimientos")
    except Exception as e:
        logger.warning(f"  ingresos migration: {e}")

    # Migrate transferencias → movimientos (tipo='transferencia')
    try:
        await db.execute("""
            INSERT INTO movimientos (tipo, monto, moneda, monto_cuenta, monto_destino, descripcion,
                cuenta_id, cuenta_destino_id, fecha, mes, semana, created_at)
            SELECT 'transferencia', monto, COALESCE(moneda, 'PEN'), monto_origen, monto_destino,
                COALESCE(descripcion, ''), cuenta_origen_id, cuenta_destino_id, fecha,
                strftime('%Y-%m', fecha), strftime('%Y-W%W', fecha),
                COALESCE(created_at, fecha)
            FROM transferencias
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM transferencias")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} transferencias → movimientos")
    except Exception as e:
        logger.warning(f"  transferencias migration: {e}")

    # Migrate pago_tarjeta → movimientos (tipo='pago_tarjeta')
    try:
        await db.execute("""
            INSERT INTO movimientos (tipo, monto, moneda, monto_cuenta, descripcion,
                cuenta_id, tarjeta_id, fecha, mes, semana, created_at)
            SELECT 'pago_tarjeta', monto, COALESCE(moneda, 'PEN'), monto_cuenta,
                COALESCE(descripcion, ''), cuenta_id, tarjeta_id, fecha,
                strftime('%Y-%m', fecha), strftime('%Y-W%W', fecha),
                COALESCE(created_at, fecha)
            FROM pago_tarjeta
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM pago_tarjeta")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} pago_tarjeta → movimientos")
    except Exception as e:
        logger.warning(f"  pago_tarjeta migration: {e}")

    # Migrate deuda_pagos → movimientos (tipo='pago_deuda')
    try:
        await db.execute("""
            INSERT INTO movimientos (tipo, monto, moneda, monto_cuenta, deuda_id,
                cuenta_id, fecha, mes, semana, created_at)
            SELECT 'pago_deuda', monto, 'PEN', monto_cuenta, deuda_id,
                cuenta_id, fecha,
                strftime('%Y-%m', fecha), strftime('%Y-W%W', fecha), fecha
            FROM deuda_pagos
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM deuda_pagos")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} deuda_pagos → movimientos")
    except Exception as e:
        logger.warning(f"  deuda_pagos migration: {e}")

    # Migrate cobro_pagos → movimientos (tipo='pago_cobro')
    try:
        await db.execute("""
            INSERT INTO movimientos (tipo, monto, moneda, monto_cuenta, cobro_id,
                cuenta_id, fecha, mes, semana, created_at)
            SELECT 'pago_cobro', monto, 'PEN', monto_cuenta, cobro_id,
                cuenta_id, fecha,
                strftime('%Y-%m', fecha), strftime('%Y-W%W', fecha), fecha
            FROM cobro_pagos
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM cobro_pagos")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} cobro_pagos → movimientos")
    except Exception as e:
        logger.warning(f"  cobro_pagos migration: {e}")

    # Migrate gasto_cuotas → movimiento_cuotas
    # We need to map old gasto_id to new movimiento_id
    try:
        # Build mapping: old gasto.id → new movimiento.id (matched by tipo='gasto' and same fecha+monto)
        await db.execute("""
            INSERT INTO movimiento_cuotas (movimiento_id, tarjeta_id, numero_cuota, cuotas_total,
                monto_cuota, fecha_cargo, pagada, periodo_facturacion)
            SELECT m.id, gc.tarjeta_id, gc.numero_cuota, gc.cuotas_total,
                gc.monto_cuota, gc.fecha_cargo, gc.pagada, gc.periodo_facturacion
            FROM gasto_cuotas gc
            JOIN gastos g ON gc.gasto_id = g.id
            JOIN movimientos m ON m.tipo = 'gasto'
                AND m.monto = g.monto AND m.fecha = g.fecha
                AND COALESCE(m.categoria, '') = COALESCE(g.categoria, '')
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM gasto_cuotas")
        count = (await cursor.fetchone())[0]
        logger.info(f"  Migrated {count} gasto_cuotas → movimiento_cuotas")
    except Exception as e:
        logger.warning(f"  gasto_cuotas migration: {e}")

    # Rename old tables to _legacy_* (keep data, don't break anything)
    legacy_tables = [
        ("gastos", "_legacy_gastos"),
        ("ingresos", "_legacy_ingresos"),
        ("transferencias", "_legacy_transferencias"),
        ("pago_tarjeta", "_legacy_pago_tarjeta"),
        ("deuda_pagos", "_legacy_deuda_pagos"),
        ("cobro_pagos", "_legacy_cobro_pagos"),
        ("gasto_cuotas", "_legacy_gasto_cuotas"),
    ]
    for old_name, new_name in legacy_tables:
        try:
            await db.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
            logger.info(f"  Renamed {old_name} → {new_name}")
        except Exception:
            pass  # Already renamed or doesn't exist

    await _set_schema_version(db, 2)
    await db.commit()
    logger.info("v2 migration complete")


async def _migrate_to_v3(db: aiosqlite.Connection):
    """Add consumos table (agua, luz, gas tracking)."""
    version = await _get_schema_version(db)
    if version >= 3:
        return
    logger.info("Starting v3 migration: adding consumos table...")
    # Table is already created by SCHEMA (CREATE IF NOT EXISTS)
    await _set_schema_version(db, 3)
    await db.commit()
    logger.info("v3 migration complete")


async def _migrate_to_v4(db: aiosqlite.Connection):
    """Add power columns to consumos, pagos_consumo, consumo_config tables."""
    version = await _get_schema_version(db)
    if version >= 4:
        return
    logger.info("Starting v4 migration: consumos extended + pagos_consumo + config...")

    # Add power metric columns to consumos
    new_cols = [
        ("consumos", "power_w", "ALTER TABLE consumos ADD COLUMN power_w REAL"),
        ("consumos", "voltage_v", "ALTER TABLE consumos ADD COLUMN voltage_v REAL"),
        ("consumos", "current_a", "ALTER TABLE consumos ADD COLUMN current_a REAL"),
        ("consumos", "day_kwh", "ALTER TABLE consumos ADD COLUMN day_kwh REAL"),
        ("consumos", "month_kwh", "ALTER TABLE consumos ADD COLUMN month_kwh REAL"),
    ]
    for table, col, sql in new_cols:
        try:
            await db.execute(sql)
            logger.info(f"  Added {table}.{col}")
        except Exception:
            pass

    # Tables pagos_consumo and consumo_config are created by SCHEMA (CREATE IF NOT EXISTS)

    # Insert default config
    try:
        await db.execute(
            "INSERT OR IGNORE INTO consumo_config (clave, valor) VALUES (?, ?)",
            ("costo_kwh_luz", "0.75"),
        )
    except Exception:
        pass

    await _set_schema_version(db, 4)
    await db.commit()
    logger.info("v4 migration complete")


async def init_db():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Backup before any migration
    _backup_db()
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _run_migrations(_db)
    await _migrate_to_v2(_db)
    await _migrate_to_v3(_db)
    await _migrate_to_v4(_db)
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
