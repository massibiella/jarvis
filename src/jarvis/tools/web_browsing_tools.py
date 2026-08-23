"""Native web-browsing/research tools: search the web and read a page.

Same shape as weather_tools.py — a plain native tool hitting an HTTP API
directly, no MCP subprocess. Backend is Tavily (TAVILY_API_KEY): /search for
web_search, /extract for fetch_webpage — one API key covers both, and
/extract returns page content pre-cleaned to text server-side, so no local
HTML-stripping is needed.

web_search finds pages; fetch_webpage reads one found by search (or
mentioned by the user) in full. Together they cover "research" (find +
read) without needing a headless browser or an MCP server.
"""

from __future__ import annotations

import logging
import os

import httpx2

from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.tavily.com"
_MAX_FETCH_CHARS = 4000
_MAX_SNIPPET_CHARS = 300  # per web_search result — Tavily's own snippet length isn't bounded


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


async def _tavily_request(endpoint: str, payload: dict, error_context: str) -> dict | str:
    """POST to a Tavily endpoint. Returns the parsed JSON on success, or a
    user-facing error string (unconfigured key / HTTP failure) on failure —
    callers check `isinstance(result, str)` to tell the two apart."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return (
            "Web browsing is not configured: set the TAVILY_API_KEY "
            "environment variable (see .env.example)."
        )

    try:
        async with httpx2.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx2.HTTPError as e:
        logger.error("Tavily %s failed for %s: %s", endpoint, error_context, e)
        return f"Sorry, {error_context} failed right now."


def register_web_browsing_tools(tools: ToolRegistry) -> None:
    @tools.register()
    async def web_search(query: str, count: int = 5) -> str:
        """Search the web. Use this for current events, facts outside your
        training data, or anything you need to look up. Returns a numbered
        list of results (title, URL, snippet) — use fetch_webpage on one of
        the URLs to read the full page. count: how many results (default 5,
        max 20)."""
        data = await _tavily_request(
            "/search",
            {"query": query, "max_results": max(1, min(count, 20))},
            f"the web search for '{query}'",
        )
        if isinstance(data, str):
            return data

        results = data.get("results", [])
        if not results:
            return f"No web results found for '{query}'."

        return "\n".join(
            f"{i}. {r['title']}\n   {r['url']}\n   {_truncate(r['content'], _MAX_SNIPPET_CHARS)}"
            for i, r in enumerate(results, start=1)
        )

    @tools.register()
    async def fetch_webpage(url: str) -> str:
        """Fetch a webpage and return its text content, for reading an
        article or page (e.g. one found via web_search). Truncated to a
        few thousand characters — for reading one page, not crawling a site."""
        data = await _tavily_request(
            "/extract", {"urls": url, "format": "text"}, f"fetching '{url}'"
        )
        if isinstance(data, str):
            return data

        results = data.get("results", [])
        if not results:
            return f"Sorry, couldn't extract content from '{url}'."

        text = results[0].get("raw_content") or ""
        return _truncate(text, _MAX_FETCH_CHARS) or "(page had no readable text content)"
