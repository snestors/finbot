# PARTIALLY DEPRECATED: The router is only used when UNIFIED_AGENT_ENABLED=False
# (legacy pipeline). When unified agent is enabled, the fast_path handles common
# patterns directly, and everything else goes to unified_agent.py.
# Will be removed after unified agent is validated in production.
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
GENERAL = "chat"  # renamed internally; wire value stays "chat" for compatibility

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
    # 3D Printer
    r'\b(?:impresora|printer|3d|elegoo|imprimi\w*|filamento|nozzle|cama|capa|layer)\b',
    r'\b(?:como\s+va\w*\s+(?:la\s+)?impres)',
]

ADMIN_PATTERNS = [
    # System/tools
    r'\b(?:estado\s+del\s+(?:sistema|servidor|rpi|raspberry))',
    r'\b(?:reinicia|restart|status|rpi)\b',
    r'\b(?:lee?\s+(?:archivo|codigo|file)|muestra.*codigo)',
    r'\b(?:edita|modifica|cambia|arregla|actualiza|mejora|crea|escribe).*(?:codigo|archivo|prompt|readme|plugin)',

    # File / code operations
    r'\b(?:readme|\.md|\.py|\.ts|\.tsx|\.json)\b',
    r'\b(?:git\s+(?:push|commit|pull|status)|push(?:ea|alo)?|commit(?:ea)?)\b',
    r'\b(?:instala|desinstala|paquete|package|npm|pip)\b',
    r'\b(?:plugin|herramienta|tool|funcionalidad)\b',
    r'\b(?:programa|implementa|desarrolla|construye|programa)',

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

GENERAL_PATTERNS = [
    # Opinions, advice, recommendations
    r'\b(?:que\s+opinas|que\s+piensas|que\s+(?:me\s+)?recomiendas)',
    r'\b(?:dame\s+(?:tu\s+)?opinion|tu\s+opinion)',
    r'\b(?:ayudame\s+(?:a|con)|me\s+ayudas)',
    r'\b(?:como\s+(?:hago|puedo|podria|deberia))',
    r'\b(?:recomienda(?:me)?|sugier[ea](?:me)?)',

    # Planning, ideas
    r'\b(?:planifi(?:car|quemos)|planear|organiz(?:ar|ame))',
    r'\b(?:ideas?\s+(?:para|de|sobre))',
    r'\b(?:lluvia\s+de\s+ideas|brainstorm)',

    # General questions
    r'\b(?:explicame|cuentame|dime\s+(?:sobre|de|que))',
    r'\b(?:que\s+(?:es|son|significa)|como\s+funciona)',
    r'\b(?:por\s*que\s+(?:es|se|hay))',

    # Comparisons, decisions
    r'\b(?:que\s+es\s+mejor|cual\s+(?:es\s+mejor|prefieres|elijo))',
    r'\b(?:ventajas?\s+(?:y|o)\s+desventajas?|pros?\s+(?:y|o)\s+contras?)',
]


class MessageRouter:
    """Routes messages to the appropriate agent with zero API calls for ~85% of messages."""

    def __init__(self, llm_client=None):
        self._llm = llm_client
        self._finance_re = [re.compile(p, re.IGNORECASE) for p in FINANCE_PATTERNS]
        self._analysis_re = [re.compile(p, re.IGNORECASE) for p in ANALYSIS_PATTERNS]
        self._admin_re = [re.compile(p, re.IGNORECASE) for p in ADMIN_PATTERNS]
        self._general_re = [re.compile(p, re.IGNORECASE) for p in GENERAL_PATTERNS]

    # Hard priority: these words ALWAYS route to a specific agent, no scoring
    _PRIORITY_ADMIN = re.compile(r'\b(?:recuerdame|avisame|no\s+me\s+dejes\s+olvidar)\b', re.IGNORECASE)

    async def route(self, text: str, history: list[dict] = None) -> str:
        """Returns one of: 'finance', 'analysis', 'admin', 'chat'."""
        text_clean = text.strip()

        if len(text_clean) < 2:
            return GENERAL

        # Priority overrides — skip scoring entirely
        if self._PRIORITY_ADMIN.search(text):
            logger.debug(f"Router: '{text_clean[:40]}' → admin (priority keyword)")
            return ADMIN

        scores = {
            FINANCE: self._score(text, self._finance_re),
            ANALYSIS: self._score(text, self._analysis_re),
            ADMIN: self._score(text, self._admin_re),
            GENERAL: self._score(text, self._general_re),
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

        # No regex match → LLM fallback for non-trivial messages
        if max_score == 0 and len(text_clean) > 5 and self._llm:
            result = await self._llm_classify(text, history)
            logger.debug(f"Router: '{text_clean[:40]}' → {result} (llm fallback)")
            return result

        logger.debug(f"Router: '{text_clean[:40]}' → chat (default)")
        return GENERAL

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
            analysis_words = ['presupuesto', 'resumen', 'total', 'cuanto', 'limite mensual', 'kwh', 'consumo', 'categoria', 'impresora', 'printer', 'elegoo', 'capa', 'nozzle']
            admin_words = ['memoria', 'perfil', 'codigo', 'agente', 'calendario', 'calendar', 'gmail', 'drive']
            general_words = ['opinas', 'recomiend', 'ayud', 'planific', 'idea', 'consejo', 'explica']
            if any(w in lb for w in finance_words):
                boosted[FINANCE] += 2
            if any(w in lb for w in analysis_words):
                boosted[ANALYSIS] += 2
            if any(w in lb for w in admin_words):
                boosted[ADMIN] += 2
            if any(w in lb for w in general_words):
                boosted[GENERAL] += 2
        return boosted

    async def _llm_classify(self, text: str, history: list[dict] = None) -> str:
        """Async LLM classification for ambiguous messages."""
        recent = ""
        if history:
            for msg in history[-3:]:
                role = "U" if msg.get("role") == "user" else "B"
                recent += f"{role}: {msg.get('content', '')[:100]}\n"

        prompt = f"""Clasifica en UNA categoria: finance, analysis, admin, general
- finance: gastos, ingresos, pagos, cuentas, tarjetas, deudas
- analysis: consultas de datos, resumenes, presupuestos, tipo de cambio, energía
- admin: recordatorios, memoria, código, sistema, herramientas
- general: conversación casual, preguntas generales, opiniones, consejos, ideas, planificación, cualquier tema no financiero/admin

{f"Contexto reciente:\\n{recent}" if recent else ""}
Mensaje: "{text}"
Responde SOLO la categoria:"""

        try:
            response = await self._llm.generate(
                system="Eres un clasificador de mensajes. Responde solo con una palabra.",
                user_message=prompt,
            )
            category = response.text.strip().lower().split()[0]
            if category == "general":
                category = GENERAL
            if category in (FINANCE, ANALYSIS, ADMIN, GENERAL):
                return category
        except Exception as e:
            logger.warning(f"Router LLM fallback failed: {e}")

        return GENERAL
