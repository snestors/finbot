"""EngramClient — async wrapper for engram MCP persistent memory.

Calls engram tools via the MCPManager (stdio transport). Falls back to
direct SQLite queries against ~/.engram/engram.db if MCP is unavailable.

All methods are fire-and-forget safe — they log errors but never raise,
so memory failures don't break the main agent flow.
"""
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Default engram DB location (used for fallback only)
_ENGRAM_DB = Path.home() / ".engram" / "engram.db"

# Default project name for finbot memories
DEFAULT_PROJECT = "finbot"


class EngramClient:
    """Async client for engram persistent memory."""

    def __init__(self, mcp_manager=None, project: str = DEFAULT_PROJECT):
        self._mcp = mcp_manager
        self._project = project

    @property
    def _has_mcp(self) -> bool:
        """Check if engram is available via MCP."""
        return self._mcp is not None and self._mcp.has_tool("mem_save")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def save(
        self,
        title: str,
        content: str,
        type: str = "manual",
        project: str | None = None,
    ) -> bool:
        """Save an observation to engram. Returns True on success."""
        proj = project or self._project
        try:
            if self._has_mcp:
                await self._mcp.call_tool("mem_save", {
                    "title": title,
                    "content": content,
                    "type": type,
                    "project": proj,
                })
                logger.info(f"[engram] Saved: '{title}' ({type})")
                return True
            else:
                return self._save_fallback(title, content, type, proj)
        except Exception as e:
            logger.warning(f"[engram] Save failed: {e}")
            return False

    async def search(
        self,
        query: str,
        project: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Semantic search for memories. Returns list of {id, title, content, type}."""
        proj = project or self._project
        try:
            if self._has_mcp:
                raw = await self._mcp.call_tool("mem_search", {
                    "query": query,
                    "project": proj,
                    "limit": limit,
                })
                return self._parse_search_results(raw)
            else:
                return self._search_fallback(query, proj, limit)
        except Exception as e:
            logger.warning(f"[engram] Search failed: {e}")
            return []

    async def get_context(
        self,
        project: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent memory context. Returns list of {id, title, content, type}."""
        proj = project or self._project
        try:
            if self._has_mcp:
                raw = await self._mcp.call_tool("mem_context", {
                    "project": proj,
                    "limit": limit,
                })
                return self._parse_context_results(raw)
            else:
                return self._context_fallback(proj, limit)
        except Exception as e:
            logger.warning(f"[engram] Context failed: {e}")
            return []

    async def get_observation(self, obs_id: int) -> dict | None:
        """Get a single observation by ID. Returns {id, title, content, type} or None."""
        try:
            if self._has_mcp:
                raw = await self._mcp.call_tool("mem_get_observation", {
                    "id": obs_id,
                })
                return self._parse_single_observation(raw)
            else:
                return self._get_observation_fallback(obs_id)
        except Exception as e:
            logger.warning(f"[engram] Get observation {obs_id} failed: {e}")
            return None

    async def format_for_context(self, query: str = "", limit: int = 5) -> str:
        """Format memories as a text block for system prompt injection.

        If query is provided, does semantic search. Otherwise returns recent context.
        """
        if query:
            memories = await self.search(query, limit=limit)
        else:
            memories = await self.get_context(limit=limit)

        if not memories:
            return ""

        lines = ["Memorias relevantes:"]
        for m in memories:
            title = m.get("title", "")
            content = m.get("content", "")
            mtype = m.get("type", "")
            # Truncate long content for context
            if len(content) > 300:
                content = content[:300] + "..."
            type_tag = f" [{mtype}]" if mtype else ""
            lines.append(f"  - {title}{type_tag}: {content}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # MCP result parsers
    # ------------------------------------------------------------------

    def _parse_search_results(self, raw: str) -> list[dict]:
        """Parse engram mem_search text output into structured dicts."""
        results = []
        if not raw:
            return results

        # Engram search returns text like:
        # Found N memories:
        #
        # [1] #ID (type) -- title
        #     content preview...
        #     date | project: X | scope: Y
        current = None
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Match header: [1] #42 (type) -- title
            if line.startswith("[") and "#" in line:
                if current:
                    results.append(current)
                try:
                    # Extract ID
                    hash_pos = line.index("#")
                    space_after = line.index(" ", hash_pos + 1)
                    obs_id = int(line[hash_pos + 1:space_after])

                    # Extract type (in parentheses)
                    paren_start = line.index("(", space_after)
                    paren_end = line.index(")", paren_start)
                    obs_type = line[paren_start + 1:paren_end]

                    # Extract title (after " -- " or " — ")
                    title_part = line[paren_end + 1:].strip()
                    for sep in (" -- ", " — ", "— ", "-- "):
                        if sep in title_part:
                            title_part = title_part.split(sep, 1)[1].strip()
                            break

                    current = {
                        "id": obs_id,
                        "type": obs_type,
                        "title": title_part,
                        "content": "",
                    }
                except (ValueError, IndexError):
                    current = None
            elif current is not None:
                # Skip metadata lines (date | project: ...)
                if "|" in line and ("project:" in line or "scope:" in line):
                    continue
                # Append content
                if current["content"]:
                    current["content"] += " " + line
                else:
                    current["content"] = line

        if current:
            results.append(current)
        return results

    def _parse_context_results(self, raw: str) -> list[dict]:
        """Parse engram mem_context output. Same format as search."""
        return self._parse_search_results(raw)

    def _parse_single_observation(self, raw: str) -> dict | None:
        """Parse engram mem_get_observation output."""
        if not raw:
            return None

        # Format: #ID [type] title\ncontent...
        lines = raw.split("\n")
        if not lines:
            return None

        header = lines[0]
        obs_id = None
        obs_type = ""
        title = ""

        # Parse header: #42 [type] title
        if header.startswith("#"):
            try:
                space = header.index(" ")
                obs_id = int(header[1:space])
                rest = header[space:].strip()
                if rest.startswith("["):
                    bracket_end = rest.index("]")
                    obs_type = rest[1:bracket_end]
                    title = rest[bracket_end + 1:].strip()
                else:
                    title = rest
            except (ValueError, IndexError):
                title = header

        content = "\n".join(lines[1:]).strip()

        return {
            "id": obs_id,
            "type": obs_type,
            "title": title,
            "content": content,
        }

    # ------------------------------------------------------------------
    # SQLite fallback (direct access to ~/.engram/engram.db)
    # ------------------------------------------------------------------

    def _get_db(self) -> sqlite3.Connection | None:
        """Open a read/write connection to engram's SQLite DB."""
        if not _ENGRAM_DB.exists():
            logger.debug("[engram] Fallback DB not found at %s", _ENGRAM_DB)
            return None
        try:
            conn = sqlite3.connect(str(_ENGRAM_DB))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.warning("[engram] Fallback DB open failed: %s", e)
            return None

    def _save_fallback(self, title: str, content: str, type: str, project: str) -> bool:
        """Insert directly into engram's observations table."""
        conn = self._get_db()
        if not conn:
            return False
        try:
            conn.execute(
                """INSERT INTO observations (title, content, type, project, scope, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'project', datetime('now'), datetime('now'))""",
                (title, content, type, project),
            )
            conn.commit()
            logger.info(f"[engram-fallback] Saved: '{title}'")
            return True
        except Exception as e:
            logger.warning(f"[engram-fallback] Save failed: {e}")
            return False
        finally:
            conn.close()

    def _search_fallback(self, query: str, project: str, limit: int) -> list[dict]:
        """Simple LIKE search against engram's DB."""
        conn = self._get_db()
        if not conn:
            return []
        try:
            q = f"%{query}%"
            rows = conn.execute(
                """SELECT id, title, content, type FROM observations
                   WHERE project = ? AND deleted_at IS NULL
                     AND (title LIKE ? OR content LIKE ?)
                   ORDER BY updated_at DESC LIMIT ?""",
                (project, q, q, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"[engram-fallback] Search failed: {e}")
            return []
        finally:
            conn.close()

    def _context_fallback(self, project: str, limit: int) -> list[dict]:
        """Get recent observations from engram's DB."""
        conn = self._get_db()
        if not conn:
            return []
        try:
            rows = conn.execute(
                """SELECT id, title, content, type FROM observations
                   WHERE project = ? AND deleted_at IS NULL
                   ORDER BY updated_at DESC LIMIT ?""",
                (project, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"[engram-fallback] Context failed: {e}")
            return []
        finally:
            conn.close()

    def _get_observation_fallback(self, obs_id: int) -> dict | None:
        """Get a single observation by ID from engram's DB."""
        conn = self._get_db()
        if not conn:
            return None
        try:
            row = conn.execute(
                "SELECT id, title, content, type FROM observations WHERE id = ?",
                (obs_id,),
            ).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.warning(f"[engram-fallback] Get observation failed: {e}")
            return None
        finally:
            conn.close()
