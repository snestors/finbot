"""
Plugin: Web Search + Fetch
Allows KYN3D to search the web and read pages.
"""
import logging
from html2text import html2text as h2t

logger = logging.getLogger(__name__)


def register():
    return {
        "tools": {
            "web_search": {
                "description": "Search the web. params: {query: 'python asyncio tutorial', max_results: 5}",
                "handler": web_search,
            },
            "web_fetch": {
                "description": "Fetch and read a web page. params: {url: 'https://...'}",
                "handler": web_fetch,
            },
        },
        "actions": {},
    }


def web_search(params: dict) -> str:
    """Search the web using DuckDuckGo."""
    query = params.get("query", "")
    max_results = min(params.get("max_results", 5), 10)
    if not query:
        return "Error: No query provided"
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return f"No results found for: {query}"
        lines = []
        for r in results:
            lines.append(f"**{r['title']}**")
            lines.append(f"  {r['href']}")
            lines.append(f"  {r['body'][:200]}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Error searching: {e}"


def web_fetch(params: dict) -> str:
    """Fetch a web page and convert to text."""
    url = params.get("url", "")
    if not url:
        return "Error: No URL provided"
    try:
        import requests
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; KYN3D/1.0)"
        })
        resp.raise_for_status()
        text = h2t(resp.text)
        if len(text) > 10000:
            text = text[:10000] + "\n\n... (truncated)"
        return text
    except Exception as e:
        logger.error(f"Web fetch error: {e}")
        return f"Error fetching {url}: {e}"
