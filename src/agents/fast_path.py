"""Fast path — regex-based action extraction with zero LLM calls.

Handles ~85% of messages by directly extracting structured actions from
common user patterns. Returns a list of action dicts compatible with
ActionExecutor.execute(), or None if no pattern matches (falls through
to LLM).

Design: pure-function module, no class state, compiled regexes at module
level. Processing time target: <50ms (pure regex, no I/O).
"""
import re
import logging
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Remove accents: cuanto -> cuanto, limite -> limite."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _clean(text: str) -> str:
    """Normalize + lowercase + strip."""
    return _normalize(text.strip()).lower()


# ---------------------------------------------------------------------------
# Category inference — keyword -> category map
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "comida": [
        "almuerzo", "cena", "desayuno", "comida", "menu", "pollo",
        "hamburguesa", "pizza", "chifa", "ceviche", "sushi", "brasa",
        "anticucho", "lomo", "arroz", "sopa", "ensalada", "pan",
        "cafe", "snack", "helado", "postre", "galleta", "fruta",
        "verdura", "carne", "pescado", "merienda", "lonche",
    ],
    "delivery": [
        "rappi", "pedidosya", "pedidos ya", "didi food", "uber eats",
        "ubereats", "glovo", "delivery",
    ],
    "transporte": [
        "uber", "taxi", "cabify", "beat", "didi", "pasaje", "bus",
        "metro", "combi", "colectivo", "mototaxi", "gasolina",
        "grifo", "estacionamiento", "peaje", "movilidad",
    ],
    "supermercado": [
        "wong", "metro", "plaza vea", "plazavea", "tottus", "vivanda",
        "makro", "mass", "flora y fauna", "supermercado", "mercado",
    ],
    "salud": [
        "farmacia", "medicina", "doctor", "clinica", "hospital",
        "inkafarma", "mifarma", "botica", "pastilla", "vitamina",
        "consulta medica", "dentista", "oculista",
    ],
    "entretenimiento": [
        "cine", "netflix", "spotify", "youtube", "prime", "disney",
        "hbo", "juego", "videojuego", "steam", "playstation", "xbox",
        "concierto", "teatro", "museo",
    ],
    "hogar": [
        "sodimac", "promart", "maestro", "ferreteria", "limpieza",
        "detergente", "escoba", "lampara", "foco",
    ],
    "ropa": [
        "ropa", "zapatos", "zapatillas", "camisa", "pantalon", "polo",
        "falken", "zara", "h&m", "saga", "ripley", "oechsle",
    ],
    "educacion": [
        "libro", "curso", "universidad", "colegio", "academia",
        "udemy", "coursera", "capacitacion", "clase",
    ],
    "mascotas": [
        "veterinario", "mascota", "perro", "gato", "comida mascota",
        "pet",
    ],
    "servicios": [
        "luz", "agua", "gas", "internet", "telefono", "celular",
        "cable", "seguro",
    ],
    "suscripciones": [
        "suscripcion", "membresia", "premium", "plan mensual",
    ],
    "personal": [
        "peluqueria", "barberia", "corte", "gym", "gimnasio",
    ],
}

# Build inverted index: keyword -> category
_KEYWORD_TO_CATEGORY: dict[str, str] = {}
for _cat, _words in _CATEGORY_KEYWORDS.items():
    for _w in _words:
        _KEYWORD_TO_CATEGORY[_w] = _cat


def _infer_category(text: str) -> str:
    """Infer expense category from text keywords. Returns 'otros' if unknown."""
    t = _clean(text)
    # Exact multi-word match first (e.g. "pedidos ya", "uber eats")
    for kw, cat in _KEYWORD_TO_CATEGORY.items():
        if ' ' in kw and kw in t:
            return cat
    # Single-word match
    words = re.split(r'\s+', t)
    for w in words:
        if w in _KEYWORD_TO_CATEGORY:
            return _KEYWORD_TO_CATEGORY[w]
    return "otros"


# ---------------------------------------------------------------------------
# Payment method detection
# ---------------------------------------------------------------------------

_PAYMENT_METHODS = {
    "yape": "yape",
    "plin": "plin",
    "efectivo": "efectivo",
    "cash": "efectivo",
    "tarjeta": "tarjeta",
    "credito": "tarjeta",
    "debito": "debito",
    "transferencia": "transferencia",
    "deposito": "deposito",
    "bcp": "transferencia",
    "bbva": "transferencia",
    "interbank": "transferencia",
    "scotiabank": "transferencia",
}

_PAYMENT_RE = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _PAYMENT_METHODS) + r')\b',
    re.IGNORECASE,
)


def _detect_payment_method(text: str) -> str | None:
    """Detect payment method from text. Returns None if not found."""
    t = _clean(text)
    m = _PAYMENT_RE.search(t)
    if m:
        return _PAYMENT_METHODS.get(m.group(1).lower())
    return None


# ---------------------------------------------------------------------------
# Currency + amount extraction
# ---------------------------------------------------------------------------

# s/50, S/50, s/ 50, S/.50, s/.50
_AMOUNT_SOLES = re.compile(r'[sS]/\.?\s*(\d+(?:\.\d{1,2})?)')
# $50, $ 50
_AMOUNT_USD = re.compile(r'\$\s*(\d+(?:\.\d{1,2})?)')
# bare number (integer or decimal)
_AMOUNT_BARE = re.compile(r'\b(\d+(?:\.\d{1,2})?)\b')


def _extract_amount(text: str) -> tuple[float | None, str]:
    """Extract amount and currency. Returns (amount, currency) or (None, 'PEN')."""
    m = _AMOUNT_SOLES.search(text)
    if m:
        return float(m.group(1)), "PEN"
    m = _AMOUNT_USD.search(text)
    if m:
        return float(m.group(1)), "USD"
    # Bare number — only if it looks like an amount (not just any number)
    m = _AMOUNT_BARE.search(text)
    if m:
        val = float(m.group(1))
        if val > 0:
            return val, "PEN"
    return None, "PEN"


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

def _extract_date(text: str) -> str | None:
    """Extract relative date from text. Returns value suitable for ActionExecutor._resolve_fecha."""
    t = _clean(text)
    if "ayer" in t and "anteayer" not in t and "ante ayer" not in t:
        return "ayer"
    if "anteayer" in t or "ante ayer" in t:
        return "anteayer"
    m = re.search(r'hace\s+(\d+)\s+dias?', t)
    if m:
        return f"hace {m.group(1)} dias"
    return None


# ---------------------------------------------------------------------------
# Description extraction — everything that's not amount, method, date
# ---------------------------------------------------------------------------

def _extract_description(text: str, amount_str: str | None = None,
                         metodo: str | None = None) -> str:
    """Extract meaningful description from text, removing noise words."""
    t = text.strip()
    # Remove amount patterns
    t = _AMOUNT_SOLES.sub('', t)
    t = _AMOUNT_USD.sub('', t)
    # Remove payment method keywords
    if metodo:
        t = re.sub(r'\b' + re.escape(metodo) + r'\b', '', t, flags=re.IGNORECASE)
    # Remove bank names used as payment
    for bank in ("bcp", "bbva", "interbank", "scotiabank"):
        t = re.sub(r'\b' + bank + r'\b', '', t, flags=re.IGNORECASE)
    # Remove date words
    for dw in ("ayer", "anteayer", "ante ayer", "hoy"):
        t = re.sub(r'\b' + re.escape(dw) + r'\b', '', t, flags=re.IGNORECASE)
    # Remove "hace N dias" patterns
    t = re.sub(r'hace\s+\d+\s+dias?', '', t, flags=re.IGNORECASE)
    # Remove common noise words (prepositions, articles)
    noise = re.compile(r'\b(?:en|de|del|con|por|para|el|la|los|las|un|una|a)\b', re.IGNORECASE)
    t = noise.sub('', t)
    # Remove extra whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    # Remove leading/trailing punctuation
    t = t.strip('.,;:!? ')
    return t


# ---------------------------------------------------------------------------
# Pattern matchers — each returns list[dict] or None
# ---------------------------------------------------------------------------

# --- GASTO (expense) patterns ---

# Pattern: "almuerzo 18 KFC yape" or "cena 25.50 rappi" or "uber 15"
# Optional leading keyword (category hint) + amount + optional description + optional method
_GASTO_KEYWORD_FIRST = re.compile(
    r'^(?P<keyword>[a-záéíóúñ]+)\s+'           # leading keyword
    r'(?:(?:[sS]/\.?\s*)?(?P<monto>\d+(?:\.\d{1,2})?))'  # amount (optional s/)
    r'(?:\s+(?P<rest>.+))?$',                   # optional rest (description + method)
    re.IGNORECASE,
)

# Pattern: "s/50 uber tarjeta" or "$25 taxi" — amount first
_GASTO_AMOUNT_FIRST = re.compile(
    r'^(?:[sS]/\.?\s*|\$\s*)(?P<monto>\d+(?:\.\d{1,2})?)'  # amount with currency
    r'(?:\s+(?P<rest>.+))?$',                               # optional rest
    re.IGNORECASE,
)

# Pattern: "50 efectivo delivery rappi" or "18.5 almuerzo yape" — bare number first
_GASTO_BARE_FIRST = re.compile(
    r'^(?P<monto>\d+(?:\.\d{1,2})?)'     # bare number
    r'\s+(?P<rest>.+)$',                  # must have something after
    re.IGNORECASE,
)

# Expense trigger keywords — if the message starts with these, it's likely an expense
_EXPENSE_TRIGGERS = {
    "almuerzo", "cena", "desayuno", "comida", "menu", "taxi", "uber", "pasaje",
    "delivery", "rappi", "pedidosya", "super", "supermercado", "mercado",
    "farmacia", "gasolina", "cafe", "cerveza", "trago", "snack", "helado",
    "cine", "parking", "estacionamiento", "peaje", "propina", "gimnasio",
    "gym", "peluqueria", "barberia", "recarga", "netflix", "spotify",
    "compre", "pague", "gaste",
}


def _try_gasto(text: str) -> list[dict] | None:
    """Try to extract a gasto (expense) from text."""
    t = text.strip()
    tc = _clean(t)

    # Skip if it looks like a query/question
    if re.match(r'^(?:cuanto|cuantos|cuantas|mis |que |como |donde |por ?que)\b', tc):
        return None

    # Skip if it looks like an income/transfer/payment
    if re.match(r'^(?:sueldo|me pagaron|recibi|cobr[eé]|pase\s|transfier)\b', tc):
        return None
    if re.match(r'^pagu[eé]\s+.*(tarjeta|visa|mastercard|deuda|hipoteca|cuota)', tc):
        return None

    monto = None
    moneda = "PEN"
    desc_parts = []
    metodo = None
    fecha = None

    # Try amount-first patterns: "s/50 uber tarjeta"
    m = _GASTO_AMOUNT_FIRST.match(t)
    if m:
        monto = float(m.group("monto"))
        moneda = "USD" if t.strip().startswith("$") else "PEN"
        rest = m.group("rest") or ""
        metodo = _detect_payment_method(rest)
        fecha = _extract_date(rest)
        desc_parts = [_extract_description(rest, metodo=metodo)]

    # Try keyword-first patterns: "almuerzo 18 KFC yape"
    if monto is None:
        m = _GASTO_KEYWORD_FIRST.match(t)
        if m:
            keyword = m.group("keyword").lower()
            keyword_clean = _normalize(keyword)
            if keyword_clean in _EXPENSE_TRIGGERS or keyword_clean in _KEYWORD_TO_CATEGORY:
                monto = float(m.group("monto"))
                rest = m.group("rest") or ""
                metodo = _detect_payment_method(keyword + " " + rest)
                fecha = _extract_date(rest)
                desc_raw = _extract_description(rest, metodo=metodo)
                desc_parts = [keyword, desc_raw] if desc_raw else [keyword]

    # Try bare-number-first: "50 efectivo delivery rappi"
    if monto is None:
        m = _GASTO_BARE_FIRST.match(t)
        if m:
            rest = m.group("rest") or ""
            rest_clean = _clean(rest)
            # Only if the rest contains expense-related words or a payment method
            has_expense_word = any(w in rest_clean for w in _EXPENSE_TRIGGERS)
            has_payment = _detect_payment_method(rest) is not None
            has_category_word = any(w in rest_clean for w in _KEYWORD_TO_CATEGORY)
            if has_expense_word or has_payment or has_category_word:
                monto = float(m.group("monto"))
                metodo = _detect_payment_method(rest)
                fecha = _extract_date(rest)
                desc_parts = [_extract_description(rest, metodo=metodo)]

    if monto is None or monto <= 0:
        return None

    # Build description
    descripcion = " ".join(p for p in desc_parts if p).strip()
    if not descripcion:
        descripcion = ""

    # Infer category from full text
    categoria = _infer_category(t)

    action = {
        "tipo": "gasto",
        "monto": monto,
        "moneda": moneda,
        "categoria": categoria,
        "descripcion": descripcion,
        "metodo_pago": metodo,
    }
    if fecha:
        action["fecha"] = fecha

    return [action]


# --- INGRESO (income) patterns ---

_INGRESO_RE = re.compile(
    r'^(?P<trigger>sueldo|me\s+pagaron|recibi|cobr[eé]|ingreso)\s+'
    r'(?:[sS]/\.?\s*|\$\s*)?(?P<monto>\d+(?:\.\d{1,2})?)'
    r'(?:\s+(?P<rest>.+))?$',
    re.IGNORECASE,
)


def _try_ingreso(text: str) -> list[dict] | None:
    """Try to extract an income from text."""
    t = text.strip()
    m = _INGRESO_RE.match(t)
    if not m:
        return None

    monto = float(m.group("monto"))
    moneda = "USD" if "$" in t[:20] else "PEN"
    trigger = m.group("trigger").strip().lower()
    rest = m.group("rest") or ""

    metodo = _detect_payment_method(rest)
    descripcion = _extract_description(rest, metodo=metodo)

    # Use the trigger phrase as description fallback
    if not descripcion:
        descripcion = trigger

    action = {
        "tipo": "ingreso",
        "mov_tipo": "ingreso",
        "monto": monto,
        "moneda": moneda,
        "descripcion": descripcion,
    }
    if metodo:
        action["metodo_pago"] = metodo

    return [action]


# --- TRANSFERENCIA (transfer) patterns ---

_TRANSFERENCIA_RE = re.compile(
    r'^(?:pase|transfier[ea]|movi)\s+'
    r'(?:[sS]/\.?\s*|\$\s*)?(?P<monto>\d+(?:\.\d{1,2})?)\s+'
    r'(?:de\s+)?(?P<origen>\w+)\s+a\s+(?P<destino>\w+)'
    r'(?:\s+(?P<rest>.+))?$',
    re.IGNORECASE,
)


def _try_transferencia(text: str) -> list[dict] | None:
    """Try to extract a transfer from text."""
    t = text.strip()
    m = _TRANSFERENCIA_RE.match(t)
    if not m:
        return None

    monto = float(m.group("monto"))
    moneda = "USD" if "$" in t[:30] else "PEN"
    origen = m.group("origen")
    destino = m.group("destino")

    action = {
        "tipo": "movimiento",
        "mov_tipo": "transferencia",
        "monto": monto,
        "moneda": moneda,
        "descripcion": f"de {origen} a {destino}",
        "metodo_pago": origen.lower(),
    }
    return [action]


# --- PAGO TARJETA (credit card payment) patterns ---

_PAGO_TARJETA_RE = re.compile(
    r'^pagu[eé]\s+'
    r'(?:[sS]/\.?\s*|\$\s*)?(?P<monto>\d+(?:\.\d{1,2})?)\s+'
    r'(?:a\s+(?:la\s+)?|de\s+(?:la\s+)?)?'
    r'(?P<tarjeta>(?:visa|mastercard|tarjeta|cmr|oh|ripley|falabella)(?:\s+\w+)?)',
    re.IGNORECASE,
)


def _try_pago_tarjeta(text: str) -> list[dict] | None:
    """Try to extract a credit card payment from text."""
    t = text.strip()
    m = _PAGO_TARJETA_RE.match(t)
    if not m:
        return None

    monto = float(m.group("monto"))
    tarjeta_name = m.group("tarjeta").strip()

    action = {
        "tipo": "movimiento",
        "mov_tipo": "pago_tarjeta",
        "monto": monto,
        "descripcion": f"pago {tarjeta_name}",
    }
    return [action]


# --- PAGO DEUDA (debt payment) patterns ---

_PAGO_DEUDA_RE = re.compile(
    r'^pagu[eé]\s+'
    r'(?:(?:la\s+)?cuota\s+(?:de\s+)?)?'
    r'(?:[sS]/\.?\s*|\$\s*)?(?P<monto>\d+(?:\.\d{1,2})?)\s+'
    r'(?:de\s+(?:la\s+)?|a\s+(?:la\s+)?)?'
    r'(?P<nombre>(?:hipoteca|prestamo|deuda|cuota)\w*(?:\s+\w+)?)',
    re.IGNORECASE,
)


def _try_pago_deuda(text: str) -> list[dict] | None:
    """Try to extract a debt payment from text."""
    t = text.strip()
    m = _PAGO_DEUDA_RE.match(t)
    if not m:
        return None

    monto = float(m.group("monto"))
    nombre = m.group("nombre").strip()

    action = {
        "tipo": "movimiento",
        "mov_tipo": "pago_deuda",
        "monto": monto,
        "nombre": nombre,
        "descripcion": f"pago {nombre}",
    }
    return [action]


# --- CONSULTA shortcuts (queries) ---

_CONSULTA_PATTERNS: list[tuple[re.Pattern, dict]] = [
    # "cuanto llevo hoy" / "cuanto gaste hoy" / "gastos de hoy"
    (re.compile(r'\b(?:cuanto\s+(?:llevo|gaste|van?|he\s+gastado)\s+hoy|gastos?\s+(?:de\s+)?hoy|que\s+he\s+gastado\s+hoy)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "hoy"}),

    # "cuanto llevo esta semana" / "gastos de la semana"
    (re.compile(r'\b(?:cuanto\s+(?:llevo|gaste|van?)\s+(?:esta\s+)?semana|gastos?\s+(?:de\s+(?:la|esta)\s+)?semana)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "semana"}),

    # "cuanto llevo este mes" / "mis gastos del mes" / "gastos del mes"
    (re.compile(r'\b(?:cuanto\s+(?:llevo|gaste|van?)\s+(?:este\s+|el\s+)?mes|(?:mis\s+)?gastos?\s+(?:de[l]?\s+)?(?:este\s+)?mes)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "mes"}),

    # "mis deudas" / "como van mis deudas" / "cuanto debo"
    (re.compile(r'\b(?:(?:mis|las)\s+deudas?|cuanto\s+debo|estado\s+de\s+deudas?)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "deudas"}),

    # "mis cuentas" / "saldo de mis cuentas"
    (re.compile(r'\b(?:(?:mis|las)\s+cuentas?|saldos?\s+(?:de\s+)?(?:mis\s+)?cuentas?)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "cuentas"}),

    # "mis tarjetas" / "estado de tarjetas"
    (re.compile(r'\b(?:(?:mis|las)\s+tarjetas?|estado\s+de\s+(?:mis\s+)?tarjetas?)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "tarjetas"}),

    # "mis cobros" / "quien me debe"
    (re.compile(r'\b(?:(?:mis|los)\s+cobros?|quien\s+me\s+debe)\b', re.IGNORECASE),
     {"tipo": "consulta", "periodo": "cobros"}),

    # "tipo de cambio" / "cuanto esta el dolar"
    (re.compile(r'\b(?:tipo\s+de\s+cambio|cuanto\s+(?:esta|cuesta)\s+(?:el\s+)?dolar)\b', re.IGNORECASE),
     {"tipo": "tipo_cambio_sunat"}),
]


def _try_consulta(text: str) -> list[dict] | None:
    """Try to match a query/consultation shortcut."""
    t = _clean(text)
    for pattern, action in _CONSULTA_PATTERNS:
        if pattern.search(t):
            return [action.copy()]
    return None


# --- ELIMINAR movimiento (delete) ---

_ELIMINAR_RE = re.compile(
    r'^(?:borra|elimina|quita|anula)\s+'
    r'(?:el\s+)?#?(?P<id>\d+)$',
    re.IGNORECASE,
)

_ELIMINAR_MULTI_RE = re.compile(
    r'^(?:borra|elimina|quita|anula)\s+'
    r'(?:los?\s+)?(?P<ids>(?:#?\d+[\s,y]+)+#?\d+)$',
    re.IGNORECASE,
)


def _try_eliminar(text: str) -> list[dict] | None:
    """Try to extract a delete action from text."""
    t = text.strip()

    # Single delete: "borra el #5" or "elimina 5"
    m = _ELIMINAR_RE.match(t)
    if m:
        return [{"tipo": "eliminar_movimiento", "movimiento_id": int(m.group("id"))}]

    # Multiple delete: "borra #5, #6 y #7"
    m = _ELIMINAR_MULTI_RE.match(t)
    if m:
        ids_raw = m.group("ids")
        ids = [int(x) for x in re.findall(r'\d+', ids_raw)]
        if ids:
            return [{"tipo": "eliminar_movimientos", "ids": ids}]

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Ordered list of matchers — first match wins
_MATCHERS = [
    ("consulta", _try_consulta),
    ("eliminar", _try_eliminar),
    ("pago_tarjeta", _try_pago_tarjeta),
    ("pago_deuda", _try_pago_deuda),
    ("ingreso", _try_ingreso),
    ("transferencia", _try_transferencia),
    ("gasto", _try_gasto),
]


def try_fast_path(text: str) -> tuple[list[dict], str] | None:
    """Try to extract structured actions from user text using regex patterns.

    Returns:
        A tuple of (actions, response_text) if a pattern matched,
        or None if no pattern matches (should fall through to LLM).

    The actions list is compatible with ActionExecutor.execute().
    The response_text is a user-facing confirmation message.
    """
    if not text or len(text.strip()) < 2:
        return None

    t = text.strip()

    # Skip messages that are clearly conversational / questions requiring LLM
    tc = _clean(t)
    if tc.startswith(("que opinas", "que piensas", "ayudame", "explicame",
                      "cuentame", "como hago", "como puedo", "recomienda",
                      "sugiere", "por que", "que es ", "como funciona",
                      "dame tu opinion", "que me recomiendas")):
        return None

    for matcher_name, matcher_fn in _MATCHERS:
        try:
            result = matcher_fn(t)
            if result is not None:
                response = _build_response(matcher_name, result)
                logger.info(f"[fast_path] HIT {matcher_name}: '{t[:50]}' -> {len(result)} actions")
                return result, response
        except Exception as e:
            logger.warning(f"[fast_path] Error in {matcher_name} matcher: {e}")
            continue

    logger.debug(f"[fast_path] MISS: '{t[:50]}'")
    return None


def _build_response(matcher_name: str, actions: list[dict]) -> str:
    """Build a user-facing response string from matched actions."""
    if not actions:
        return ""

    a = actions[0]
    tipo = a.get("tipo", "")
    mov_tipo = a.get("mov_tipo", tipo)

    if tipo == "consulta":
        periodo = a.get("periodo", "")
        labels = {
            "hoy": "Reviso tus gastos de hoy...",
            "semana": "Reviso tus gastos de la semana...",
            "mes": "Reviso tus gastos del mes...",
            "deudas": "Reviso tus deudas...",
            "cuentas": "Reviso tus cuentas...",
            "tarjetas": "Reviso tus tarjetas...",
            "cobros": "Reviso tus cobros...",
        }
        return labels.get(periodo, "Consultando...")

    if tipo == "tipo_cambio_sunat":
        return "Consulto el tipo de cambio SUNAT..."

    if tipo == "eliminar_movimiento":
        return f"Elimino el #{a.get('movimiento_id', '?')}"

    if tipo == "eliminar_movimientos":
        ids = a.get("ids", [])
        return f"Elimino {len(ids)} movimientos"

    monto = a.get("monto", 0)
    moneda_sym = "$" if a.get("moneda") == "USD" else "S/"
    desc = a.get("descripcion", "")
    metodo_str = f" con {a.get('metodo_pago')}" if a.get("metodo_pago") else ""
    fecha_str = f" ({a.get('fecha')})" if a.get("fecha") else ""

    if tipo == "gasto" or mov_tipo == "gasto":
        cat = a.get("categoria", "otros")
        return f"Registro {cat}: {moneda_sym}{monto:.2f} {desc}{metodo_str}{fecha_str}".strip()

    if tipo == "ingreso" or mov_tipo == "ingreso":
        return f"Registro ingreso: {moneda_sym}{monto:.2f} {desc}{metodo_str}".strip()

    if mov_tipo == "transferencia":
        return f"Registro transferencia: {moneda_sym}{monto:.2f} {desc}".strip()

    if mov_tipo == "pago_tarjeta":
        return f"Registro pago tarjeta: {moneda_sym}{monto:.2f} {desc}".strip()

    if mov_tipo == "pago_deuda":
        return f"Registro pago deuda: {moneda_sym}{monto:.2f} {desc}".strip()

    return f"Registro: {moneda_sym}{monto:.2f} {desc}".strip()
