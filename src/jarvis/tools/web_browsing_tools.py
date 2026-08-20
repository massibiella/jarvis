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

_SEARCH_URL = "https://api.tavily.com/search"
_EXTRACT_URL = "https://api.tavily.com/extract"
_MAX_FETCH_CHARS = 4000


def _auth_header() -> str | None:
    api_key = os.environ.get("TAVILY_API_KEY")
    return f"Bearer {api_key}" if api_key else None


def register_web_browsing_tools(tools: ToolRegistry) -> None:
    @tools.register()
    async def web_search(query: str, count: int = 5) -> str:
        """Search the web. Use this for current events, facts outside your
        training data, or anything you need to look up. Returns a numbered
        list of results (title, URL, snippet) — use fetch_webpage on one of
        the URLs to read the full page. count: how many results (default 5,
        max 20)."""
        auth = _auth_header()
        if not auth:
            return (
                "Web search is not configured: set the TAVILY_API_KEY "
                "environment variable (see .env.example)."
            )

        try:
            async with httpx2.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _SEARCH_URL,
                    headers={"Authorization": auth},
                    json={"query": query, "max_results": max(1, min(count, 20))},
                )
                response.raise_for_status()
                data = response.json()
        except httpx2.HTTPError as e:
            logger.error("Web search failed for %r: %s", query, e)
            return f"Sorry, the web search for '{query}' failed right now."

        results = data.get("results", [])
        if not results:
            return f"No web results found for '{query}'."

        return "\n".join(
            f"{i}. {r['title']}\n   {r['url']}\n   {r['content']}"
            for i, r in enumerate(results, start=1)
        )

    @tools.register()
    async def fetch_webpage(url: str) -> str:
        """Fetch a webpage and return its text content, for reading an
        article or page (e.g. one found via web_search). Truncated to a
        few thousand characters — for reading one page, not crawling a site."""
        auth = _auth_header()
        if not auth:
            return (
                "Web browsing is not configured: set the TAVILY_API_KEY "
                "environment variable (see .env.example)."
            )

        try:
            async with httpx2.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _EXTRACT_URL,
                    headers={"Authorization": auth},
                    json={"urls": url, "format": "text"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx2.HTTPError as e:
            logger.error("Failed to fetch %r: %s", url, e)
            return f"Sorry, couldn't fetch '{url}' right now."

        results = data.get("results", [])
        if not results:
            return f"Sorry, couldn't extract content from '{url}'."

        text = results[0].get("raw_content") or ""
        if len(text) > _MAX_FETCH_CHARS:
            text = text[:_MAX_FETCH_CHARS] + "\n...[truncated]"
        return text or "(page had no readable text content)"
