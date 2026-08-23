"""OAuth for remote (Streamable HTTP) MCP servers, e.g. IBKR's hosted connector.

Stdio servers (Google Calendar) handle their own OAuth internally and cache
their own tokens — see mcp_client.py. A remote server has no such wrapper;
Jarvis itself is the OAuth client. build_oauth_provider() wires up token
persistence (_FileTokenStorage) and the one-time browser consent flow (a
local callback listener) that mcp.client.auth.OAuthClientProvider needs.
Only runs on first connect() for a given server — after that, the cached
token is reused silently.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import mcp.client.auth.oauth2 as _oauth2
from mcp.client.auth import OAuthClientProvider
from mcp.client.auth.oauth2 import OAuthClientInformationFull, OAuthToken
from mcp.shared.auth import AuthorizationCodeResult, OAuthClientMetadata, OAuthMetadata

_TOKEN_DIR = Path.home() / ".jarvis" / "mcp_oauth"
# Deliberately not 8765 — voice-server/server.py already owns that port, and
# IBKR's OAuth redirect landing there instead of this callback listener
# fails silently (Flask 404, not a bind error, since this server just never
# gets to claim the port first).
_CALLBACK_PORT = 8766
_REDIRECT_URI = f"http://localhost:{_CALLBACK_PORT}/callback"

# IBKR's own metadata fails RFC 8414's issuer-match check: it's referenced as
# ".../oauth2" but declares issuer="https://api.ibkr.com" (no /oauth2) — a
# mismatch in what IBKR publishes, confirmed against the real domain, not a
# spoofed one. Waved through by exact pair only; anything else still raises.
_KNOWN_ISSUER_QUIRKS = {
    "https://api.ibkr.com/oauth2": "https://api.ibkr.com",
}

_original_validate_metadata_issuer = _oauth2.validate_metadata_issuer


def _patched_validate_metadata_issuer(oauth_metadata: object, expected_issuer: str) -> None:
    if _KNOWN_ISSUER_QUIRKS.get(expected_issuer) == str(oauth_metadata.issuer):
        return
    _original_validate_metadata_issuer(oauth_metadata, expected_issuer)


_oauth2.validate_metadata_issuer = _patched_validate_metadata_issuer

# Per the MCP spec, the SDK always requests every scope the server advertises
# — it ignores a narrower OAuthClientMetadata.scope set ahead of time. IBKR
# advertises both mcp.read and mcp.write, so the unpatched SDK always got
# granted write/trading access too. Strip mcp.write specifically rather than
# overriding scope selection generally.
_original_get_client_metadata_scopes = _oauth2.get_client_metadata_scopes


def _patched_get_client_metadata_scopes(*args: object, **kwargs: object) -> str | None:
    scope = _original_get_client_metadata_scopes(*args, **kwargs)
    if scope and "mcp.write" in scope.split():
        scope = " ".join(s for s in scope.split() if s != "mcp.write")
    return scope


_oauth2.get_client_metadata_scopes = _patched_get_client_metadata_scopes

# Two SDK gaps that broke silent refresh on a fresh process, both confirmed
# live via tracing:
# 1. _initialize() loads a cached token from storage but never computes its
#    expiry, so is_token_valid() wrongly treats a genuinely-expired token as
#    valid forever — refresh never gets a chance to run.
# 2. Even when refresh does run, it only uses the real token endpoint if
#    oauth_metadata is already populated; on a cold start it isn't, so it
#    guesses ".../token" instead of the real ".../oauth2/api/v1/token" (404).
# _patched_initialize below fixes both: sets expiry from our own recorded
# save time (can't reuse the SDK's own helper — it assumes "just issued"),
# and seeds the known-good token endpoint. Only token_endpoint's value
# matters here; issuer/authorization_endpoint are required to construct the
# object but always get overwritten by real discovery before being read.
_KNOWN_TOKEN_ENDPOINTS: dict[str, dict[str, str]] = {
    "https://api.ibkr.com/v1/api/mcp-public": {
        "issuer": "https://api.ibkr.com",
        "authorization_endpoint": "https://api.ibkr.com/oauth2/authorize",
        "token_endpoint": "https://api.ibkr.com/oauth2/api/v1/token",
    },
}

_original_initialize = OAuthClientProvider._initialize


async def _patched_initialize(self: OAuthClientProvider) -> None:
    await _original_initialize(self)
    storage = self.context.storage
    if self.context.current_tokens and isinstance(storage, _FileTokenStorage):
        expiry = storage.get_token_expiry_time()
        if expiry is not None:
            self.context.token_expiry_time = expiry

    if not self.context.oauth_metadata:
        known = _KNOWN_TOKEN_ENDPOINTS.get(self.context.server_url)
        if known:
            self.context.oauth_metadata = OAuthMetadata(**known)


OAuthClientProvider._initialize = _patched_initialize


class _FileTokenStorage:
    """Persists one server's OAuth tokens + client registration to a JSON file."""

    def __init__(self, server_name: str) -> None:
        self._path = _TOKEN_DIR / f"{server_name}.json"

    def _read(self) -> dict:
        try:
            return json.loads(self._path.read_text())
        except FileNotFoundError:
            return {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data))

    async def get_tokens(self) -> OAuthToken | None:
        raw = self._read().get("tokens")
        return OAuthToken.model_validate(raw) if raw else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._read()
        data["tokens"] = tokens.model_dump(mode="json")
        # OAuthToken only carries expires_in (seconds, relative to issuance) —
        # meaningless once reloaded in a later process without knowing how much
        # time has actually passed. Record our own absolute reference point at
        # save time so we can tell later whether it's genuinely still fresh.
        data["tokens_saved_at"] = time.time()
        self._write(data)

    def get_token_expiry_time(self) -> float | None:
        """Absolute epoch expiry, computed from our own recorded save time —
        see the SDK-bug comment on _patched_initialize below for why this
        can't just be recomputed from expires_in relative to "now"."""
        data = self._read()
        saved_at = data.get("tokens_saved_at")
        tokens = data.get("tokens")
        if saved_at is None or not tokens or tokens.get("expires_in") is None:
            return None
        return saved_at + tokens["expires_in"]

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        raw = self._read().get("client_info")
        return OAuthClientInformationFull.model_validate(raw) if raw else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._read()
        data["client_info"] = client_info.model_dump(mode="json")
        self._write(data)


async def _wait_for_callback() -> AuthorizationCodeResult:
    """Run a one-shot local HTTP server, block until the OAuth redirect lands."""
    result: dict[str, str | None] = {}
    done = asyncio.Event()
    loop = asyncio.get_running_loop()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not self.path.startswith("/callback"):
                # Ignore stray requests (e.g. the browser's own /favicon.ico) —
                # only the real redirect should ever complete this wait.
                self.send_response(404)
                self.end_headers()
                return

            query = parse_qs(urlparse(self.path).query)
            result["code"] = query.get("code", [None])[0]
            result["state"] = query.get("state", [None])[0]
            result["error"] = query.get("error", [None])[0]
            result["error_description"] = query.get("error_description", [None])[0]
            self.send_response(200)
            self.end_headers()
            if result["error"]:
                self.wfile.write(f"Authorization failed: {result['error']}".encode())
            else:
                self.wfile.write(b"Authorized - you can close this tab.")
            loop.call_soon_threadsafe(done.set)

        def log_message(self, *args: object) -> None:
            pass  # silence default per-request stderr logging

    server = HTTPServer(("localhost", _CALLBACK_PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        await done.wait()
    finally:
        server.shutdown()
    if result.get("error"):
        raise RuntimeError(
            f"IBKR denied authorization: {result['error']} — {result.get('error_description')}"
        )
    return AuthorizationCodeResult(code=result["code"], state=result["state"])


async def _open_browser(url: str) -> None:
    webbrowser.open(url)


def build_oauth_provider(server_name: str, server_url: str) -> OAuthClientProvider:
    """OAuth client for one remote MCP server, identified by its config name.

    No `scope` set here — it wouldn't matter. The SDK overwrites it from
    server-advertised metadata regardless; read-only enforcement is entirely
    the _patched_get_client_metadata_scopes patch above.
    """
    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=OAuthClientMetadata(
            client_name="jarvis",
            redirect_uris=[_REDIRECT_URI],
            # public client: PKCE + loopback redirect, no client secret
            token_endpoint_auth_method="none",
        ),
        storage=_FileTokenStorage(server_name),
        redirect_handler=_open_browser,
        callback_handler=_wait_for_callback,
    )
