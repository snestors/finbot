import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.database.db import get_db

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Lima")


def _now():
    return datetime.now(TZ)


def _today():
    return _now().strftime("%Y-%m-%d")


def _mes_actual():
    return _now().strftime("%Y-%m")


# Gemini 2.5 Flash pricing (per 1M tokens)
GEMINI_INPUT_PRICE = 0.15
GEMINI_OUTPUT_PRICE = 0.60


class LLMUsageRepo:

    async def save(self, model: str, caller: str,
                   input_tokens: int, output_tokens: int):
        db = await get_db()
        now = _now()
        fecha = now.strftime("%Y-%m-%d")
        mes = now.strftime("%Y-%m")
        await db.execute(
            """INSERT INTO llm_usage (model, caller, input_tokens, output_tokens, fecha, mes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (model, caller, input_tokens, output_tokens, fecha, mes),
        )
        await db.commit()

    async def get_summary_today(self) -> list[dict]:
        db = await get_db()
        fecha = _today()
        cursor = await db.execute(
            """SELECT model,
                      COUNT(*) as calls,
                      SUM(input_tokens) as total_input,
                      SUM(output_tokens) as total_output
               FROM llm_usage WHERE fecha = ?
               GROUP BY model""",
            (fecha,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_summary_month(self, mes: str = None) -> list[dict]:
        db = await get_db()
        mes = mes or _mes_actual()
        cursor = await db.execute(
            """SELECT model,
                      COUNT(*) as calls,
                      SUM(input_tokens) as total_input,
                      SUM(output_tokens) as total_output
               FROM llm_usage WHERE mes = ?
               GROUP BY model""",
            (mes,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_daily_breakdown(self, mes: str = None) -> list[dict]:
        db = await get_db()
        mes = mes or _mes_actual()
        cursor = await db.execute(
            """SELECT fecha, model,
                      COUNT(*) as calls,
                      SUM(input_tokens) as total_input,
                      SUM(output_tokens) as total_output
               FROM llm_usage WHERE mes = ?
               GROUP BY fecha, model
               ORDER BY fecha""",
            (mes,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_by_caller(self, mes: str = None) -> list[dict]:
        db = await get_db()
        mes = mes or _mes_actual()
        cursor = await db.execute(
            """SELECT caller, model,
                      COUNT(*) as calls,
                      SUM(input_tokens) as total_input,
                      SUM(output_tokens) as total_output
               FROM llm_usage WHERE mes = ?
               GROUP BY caller, model
               ORDER BY total_input DESC""",
            (mes,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_recent(self, limit: int = 20) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """SELECT id, model, caller, input_tokens, output_tokens, created_at
               FROM llm_usage ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    @staticmethod
    def estimate_cost(input_tokens: int, output_tokens: int) -> float:
        cost = (input_tokens / 1_000_000) * GEMINI_INPUT_PRICE
        cost += (output_tokens / 1_000_000) * GEMINI_OUTPUT_PRICE
        return round(cost, 6)
