"""Rule-based message router. Zero API calls for ~85% of messages."""
import re
import logging
import unicodedata

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Remove accents: cuánto → cuanto, límite → limite."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

FINANCE = "finance"
ANALYSIS = "analysis"
ADMIN = "admin"
CHAT = "chat"

FINANCE_PATTERNS = [
    # Money amounts
    r'[sS]/?\s*\d+',
    r'\$\s*\d+',
    r'\b\d+\.\d+\b',

    # Expense keywords
    r'\b(?:gast[eéo]|pagu[eé]|compr[eé]|almor[zc]|cen[eé]|desayun)',
    r'\b(?:uber|taxi|pasaje|movilidad|delivery|rappi|pedidos\s*ya)',
    r'\b(?:yape|plin|efectivo|tarjeta|transferencia|deposito)',
    r'\b(?:sueldo|ingreso|me\s+pagaron|recibi|cobr[eé])',

    # Account operations
    r'\b(?:saqu[eé]|retir[eé]|transfier[ea])',
    r'\b(?:pago?\s+(?:de\s+)?(?:tarjeta|deuda|credito))',
    r'\b(?:edita|modifica|actualiza|renombra).*\b(?:cuenta|tarjeta)',
    r'\b(?:crear?\s+cuenta|nueva\s+cuenta|agregar?\s+cuenta)',

    # Debt/cobro
    r'\b(?:me\s+debe|le\s+debo|prest[eéo])',
    r'\b(?:deuda|cuota)\b',

    # CRUD on expenses
    r'\b(?:borra|elimina|quita|quedate\s+con|corrige|cambia)',
    r'#\d+',
]

ANALYSIS_PATTERNS = [
    r'\b(?:cuanto|cuánto)\s+(?:llevo|gast[eé]|van|debo)',
    r'\b(?:resumen|reporte|estadistic|analisis|análisis)',
    r'\b(?:semana|mes|hoy|ayer)\b.*(?:gast|total)',
    r'\b(?:presupuesto|budget|limite)',
    r'\b(?:tipo\s+de\s+cambio|dolar|convertir|cambiar\s+\d)',
    r'\b(?:busca|encuentra|donde\s+gast)',
    r'\bcuanto\b',
    r'\b(?:mis\s+(?:gastos?|cuentas?|tarjetas?|deudas?|cobros?))',
    # Energy / consumos
    r'\b(?:co[ns]+umo|electri\w*|energ[ií]a|kwh|watts?|potencia|corriente)',
    r'\bluz\b',
    r'\b(?:recibo\s+(?:de\s+)?(?:luz|agua|gas))',
    r'\b(?:ahorro|ahorrar|eficien)',
    r'\b(?:como\s+va\w*\s+(?:la\s+|el\s+|lo\s+)?(?:luz|agua|gas|electri|consum))',
]

ADMIN_PATTERNS = [
    # System/tools
    r'\b(?:estado\s+del\s+(?:sistema|servidor|rpi|raspberry))',
    r'\b(?:reinicia|restart|status|rpi)\b',
    r'\b(?:lee?\s+(?:archivo|codigo|file)|muestra.*codigo)',
    r'\b(?:edita|modifica|cambia).*(?:codigo|archivo|prompt)',

    # Memory
    r'\b(?:recuerda\s+que|memoriza|aprende|olvida)',
    r'\b(?:que\s+(?:sabes|recuerdas)\s+de)',

    # Reminders
    r'\b(?:recuerdame|recordatorio|alarma|avisa)',

    # Profile/setup
    r'\b(?:mi\s+nombre|me\s+llamo|moneda\s+default)',

    # Agent management
    r'\b(?:agentes?|prompts?|configurar?\s+agente)',

    # Personality / self-modification
    r'\b(?:no\s+(?:me\s+)?habl|deja\s+de\s+(?:habla|deci)|cambia\s+tu\s+(?:estilo|tono|forma))',
    r'\b(?:personalidad|jerga|slang|causa|bacán|chevere)',
    r'\b(?:edita|modifica|cambia).*(?:alma|personalidad|estilo)',
]


class MessageRouter:
    """Routes messages to the appropriate agent with zero API calls for ~85% of messages."""

    def __init__(self, gemini_client=None):
        self._gemini = gemini_client
        self._finance_re = [re.compile(p, re.IGNORECASE) for p in FINANCE_PATTERNS]
        self._analysis_re = [re.compile(p, re.IGNORECASE) for p in ANALYSIS_PATTERNS]
        self._admin_re = [re.compile(p, re.IGNORECASE) for p in ADMIN_PATTERNS]

    def route(self, text: str, history: list[dict] = None) -> str:
        """Returns one of: 'finance', 'analysis', 'admin', 'chat'."""
        text_clean = text.strip()

        if len(text_clean) < 2:
            return CHAT

        scores = {
            FINANCE: self._score(text, self._finance_re),
            ANALYSIS: self._score(text, self._analysis_re),
            ADMIN: self._score(text, self._admin_re),
        }

        # Context boosting from recent history
        if history:
            last_bot = self._get_last_bot_content(history)
            if last_bot:
                scores = self._boost_from_context(scores, last_bot, text_clean)

        max_score = max(scores.values())

        # High confidence
        if max_score >= 2:
            winner = max(scores, key=scores.get)
            logger.debug(f"Router: '{text_clean[:40]}' → {winner} (score={max_score})")
            return winner

        # Single match with finance bias for numbers
        if max_score == 1:
            if re.search(r'\b\d+\.?\d*\b', text) and scores[FINANCE] >= 1:
                logger.debug(f"Router: '{text_clean[:40]}' → finance (number+signal)")
                return FINANCE
            winner = max(scores, key=scores.get)
            logger.debug(f"Router: '{text_clean[:40]}' → {winner} (score=1)")
            return winner

        # No match — try Gemini fallback for longer messages
        if len(text_clean) > 30 and self._gemini:
            result = self._gemini_classify(text)
            logger.debug(f"Router: '{text_clean[:40]}' → {result} (gemini fallback)")
            return result

        logger.debug(f"Router: '{text_clean[:40]}' → chat (default)")
        return CHAT

    def _score(self, text: str, patterns: list[re.Pattern]) -> int:
        return sum(1 for p in patterns if p.search(text))

    def _get_last_bot_content(self, history: list[dict]) -> str:
        for msg in reversed(history):
            if msg.get("role") != "user":
                return msg.get("content", "")
        return ""

    def _boost_from_context(self, scores: dict, last_bot: str, text: str) -> dict:
        """Boost scores for short follow-up messages based on conversation context."""
        boosted = scores.copy()
        lb = _normalize(last_bot.lower())

        if len(text) < 20:
            finance_words = ['gasto', 'registr', 'monto', 'pago', 'cuenta', 's/', 'tarjeta', 'cuota', 'credito', 'banco', 'digito']
            analysis_words = ['presupuesto', 'resumen', 'total', 'cuanto', 'limite mensual', 'kwh', 'consumo', 'categoria']
            admin_words = ['recordatorio', 'memoria', 'perfil', 'codigo', 'agente']
            if any(w in lb for w in finance_words):
                boosted[FINANCE] += 2
            if any(w in lb for w in analysis_words):
                boosted[ANALYSIS] += 2
            if any(w in lb for w in admin_words):
                boosted[ADMIN] += 2
        return boosted

    def _gemini_classify(self, text: str) -> str:
        """Fallback: use Gemini to classify truly ambiguous messages."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, can't block. Default to chat.
                return CHAT
        except RuntimeError:
            pass

        prompt = f"""Clasifica este mensaje en UNA categoria: finance, analysis, admin, chat
- finance: gastos, ingresos, pagos, cuentas, tarjetas, deudas, cobros
- analysis: consultas de cuanto llevo, resumenes, presupuestos, tipo de cambio
- admin: recordatorios, memoria, perfil, codigo, sistema, herramientas
- chat: conversacion casual, saludos, temas no financieros

Mensaje: "{text}"
Responde SOLO la categoria (una palabra):"""

        try:
            response = self._gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            category = response.text.strip().lower()
            if category in (FINANCE, ANALYSIS, ADMIN, CHAT):
                return category
        except Exception as e:
            logger.warning(f"Router Gemini fallback failed: {e}")

        return CHAT
