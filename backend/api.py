#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local HTTP/JSON API for the D-Changer UI

The Tauri front end talks to the Python engine over this small JSON API on
loopback only. It is deliberately stdlib-only (no web framework) and read-mostly:
the UI asks for status, the skin library, the updater's view of the world, and
the account profiles; the few write endpoints (switch profile, save profile)
delegate to the same modules the engine uses.

Security mirrors the Pengu bridge: bind 127.0.0.1, and reject any request that
carries a non-loopback Origin header. Nothing here reaches the network or the
game; it only reads and writes local state.

Run standalone for development::

    python -m api            # serves on http://127.0.0.1:56700
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from config import APP_NAME, APP_VERSION
from utils.core.logging import get_logger
from utils.core.security import cors_headers_for_origin, is_loopback_origin

log = get_logger()

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 56700


class ApiContext:
    """Live engine objects the API reads from.

    Every field is optional so the API can run before the engine is fully up
    (the UI shows "starting" until they appear).
    """

    def __init__(
        self,
        state=None,
        lcu=None,
        skin_scraper=None,
        app_status=None,
        injection_manager=None,
        startup=None,
    ):
        self.state = state
        self.lcu = lcu
        self.skin_scraper = skin_scraper
        self.app_status = app_status
        self.injection_manager = injection_manager
        self.startup = startup


# ── Route handlers ──────────────────────────────────────────────────────────
# Each returns a JSON-serialisable object. Raising KeyError/ValueError becomes a
# 400; anything else a 500.

def _status(ctx: ApiContext) -> dict:
    state = ctx.state
    status: dict[str, Any] = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "engine_ready": state is not None,
    }
    if state is not None:
        status.update({
            "phase": state.phase,
            "locked_champion_id": state.locked_champ_id,
            "selected_skin_id": state.selected_skin_id,
            "current_game_mode": state.current_game_mode,
            "historic_mode_active": state.historic_mode_active,
            "random_mode_active": state.random_mode_active,
        })
    if ctx.app_status is not None:
        status["downloads"] = ctx.app_status.get_status_summary()
    if ctx.startup is not None:
        status["startup"] = ctx.startup.snapshot()
    return status


def _skins(ctx: ApiContext) -> dict:
    if ctx.skin_scraper is None:
        return {"skins": [], "champion_id": None}
    return {
        "champion_id": ctx.skin_scraper.cached_champion_id(),
        "champion_name": ctx.skin_scraper.cached_champion_name(),
    }


def _profiles_list(ctx: ApiContext) -> dict:
    from profiles import current_profile, list_profiles

    return {
        "current": current_profile(),
        "profiles": [
            {"puuid": p.puuid, "name": p.name, "updated_at": p.updated_at}
            for p in list_profiles()
        ],
    }


def _account(ctx: ApiContext) -> dict:
    """The signed-in League account, so the UI never asks for a PUUID by hand."""
    if ctx.lcu is None:
        return {"puuid": None, "name": None}
    try:
        summoner = ctx.lcu.current_summoner
    except Exception as e:  # noqa: BLE001 - a missing client is not an error
        log.debug(f"[api] Could not read the current summoner: {e}")
        return {"puuid": None, "name": None}
    if not summoner:
        return {"puuid": None, "name": None}
    return {
        "puuid": summoner.get("puuid"),
        "name": summoner.get("displayName") or summoner.get("gameName"),
    }


def _profile_save(ctx: ApiContext, body: dict) -> dict:
    from profiles import save_profile

    puuid = str(body.get("puuid", ""))
    if not puuid:
        raise ValueError("puuid is required")
    profile = save_profile(puuid, str(body.get("name", "")))
    return {"puuid": profile.puuid, "name": profile.name}


def _profile_load(ctx: ApiContext, body: dict) -> dict:
    from profiles import load_profile

    puuid = str(body.get("puuid", ""))
    if not puuid:
        raise ValueError("puuid is required")
    return {"loaded": load_profile(puuid)}


def _profile_delete(ctx: ApiContext, body: dict) -> dict:
    from profiles import delete_profile

    puuid = str(body.get("puuid", ""))
    if not puuid:
        raise ValueError("puuid is required")
    return {"deleted": delete_profile(puuid)}


def _updates(ctx: ApiContext) -> dict:
    from updater import ltk_patcher, sources

    ltk = sources.ltk_manager_release()
    pengu = sources.pengu_loader_release()
    rose = sources.rose_release()
    return {
        "ltk_manager": ltk.tag if ltk else None,
        "league_skins_sha": sources.league_skins_sha(),
        "pengu_loader": pengu.tag if pengu else None,
        "rose": rose.tag if rose else None,
    }


def _diagnostics(ctx: ApiContext) -> dict:
    """Recent actionable problems (game-update breakage, missing files, …).

    The engine writes these to dchanger_diagnostics.txt; surfacing them here
    lets the UI show a game-update failure instead of leaving it in a log file.
    """
    from utils.core.issue_reporter import read_issues_tail

    return {"issues": read_issues_tail(max_lines=40)}

def _failed_skins(ctx: ApiContext) -> dict:
    """Skins that failed to download or extract during the last sync.

    The downloader writes them to failed_skins.json next to the skins; the UI
    lists them and can retry each one instead of only logging the failure.
    """
    from utils.core.paths import get_skins_dir

    state_file = get_skins_dir() / "failed_skins.json"
    if not state_file.exists():
        return {"files": []}
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning(f"[api] Could not read the failed-skins state: {e}")
        return {"files": []}
    files = data.get("files", []) if isinstance(data, dict) else []
    return {"files": files}

def _retry_skin(ctx: ApiContext, body: dict) -> dict:
    """Re-download one failed skin by its repository path."""
    from utils.download.repo_downloader import RepoDownloader

    path = str(body.get("path", "")).strip()
    if not path:
        raise ValueError("path is required")
    ok = RepoDownloader().retry_failed_file(path)
    return {"retried": ok, "path": path}


def _shutdown(ctx: ApiContext, body: dict) -> dict:
    """Ask the engine to stop, so the UI can close it cleanly.

    Setting ``state.stop`` makes the main loop leave and run its cleanup
    (resume the game, deactivate Pengu, kill mod-tools). The UI calls this
    before it exits instead of killing the process, which skipped cleanup and
    left the tray icon and Pengu running.
    """
    if ctx.state is None:
        return {"stopping": False}
    log.info("[api] Shutdown requested by the UI")
    ctx.state.stop = True
    return {"stopping": True}


# (method, path) -> handler. Handlers take (ctx) or (ctx, body).
_GET_ROUTES: dict[str, Callable[[ApiContext], Any]] = {
    "/api/status": _status,
    "/api/skins": _skins,
    "/api/profiles": _profiles_list,
    "/api/account": _account,
    "/api/updates": _updates,
    "/api/diagnostics": _diagnostics,
    "/api/skins/failed": _failed_skins,
}

_POST_ROUTES: dict[str, Callable[[ApiContext, dict], Any]] = {
    "/api/profiles/save": _profile_save,
    "/api/profiles/load": _profile_load,
    "/api/profiles/delete": _profile_delete,
    "/api/skins/retry": _retry_skin,
    "/api/shutdown": _shutdown,
}


class _Handler(BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}-api/{APP_VERSION}"
    context: ApiContext  # set on the server class below

    def log_message(self, fmt, *args):  # quieter than the default stderr spam
        log.debug(f"[api] {fmt % args}")

    def _origin(self) -> Optional[str]:
        return self.headers.get("Origin") or self.headers.get("origin")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in cors_headers_for_origin(self._origin()).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _guard_origin(self) -> bool:
        origin = self._origin()
        if origin and not is_loopback_origin(origin):
            log.warning(f"[api] Blocked request from origin: {origin}")
            self._send_json({"error": "forbidden origin"}, status=403)
            return False
        return True

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError(f"invalid JSON body: {e}")
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if not self._guard_origin():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        handler = _GET_ROUTES.get(path)
        if handler is None:
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            self._send_json(handler(self.context))
        except Exception as e:  # noqa: BLE001 - report, do not crash the server
            log.warning(f"[api] GET {path} failed: {e}")
            self._send_json({"error": str(e)}, status=500)

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Answer the CORS preflight a browser sends before a JSON POST.

        The UI runs on a different loopback origin (localhost:1420) than the
        API (127.0.0.1:56700), so every POST with a JSON body is preceded by an
        OPTIONS request. Without this the browser blocks the call.
        """
        origin = self._origin()
        if origin and not is_loopback_origin(origin):
            self._send_json({"error": "forbidden origin"}, status=403)
            return
        self.send_response(204)
        for key, value in cors_headers_for_origin(origin).items():
            self.send_header(key, value)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard_origin():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        handler = _POST_ROUTES.get(path)
        if handler is None:
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            body = self._read_body()
            self._send_json(handler(self.context, body))
        except (ValueError, KeyError) as e:
            self._send_json({"error": str(e)}, status=400)
        except Exception as e:  # noqa: BLE001
            log.warning(f"[api] POST {path} failed: {e}")
            self._send_json({"error": str(e)}, status=500)


class ApiServer:
    """A loopback JSON API server running on its own thread."""

    def __init__(self, context: ApiContext, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.context = context
        # Keep the bound handler class so the context can be swapped later
        # (the server starts before the engine state exists).
        self._handler_cls = type("_BoundHandler", (_Handler,), {"context": context})
        self._httpd = ThreadingHTTPServer((host, port), self._handler_cls)
        self._thread: Optional[threading.Thread] = None
        self.host, self.port = host, self._httpd.server_address[1]

    def set_context(self, context: ApiContext) -> None:
        """Replace the context the running server serves from."""
        self.context = context
        self._handler_cls.context = context

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="ApiServer", daemon=True)
        self._thread.start()
        log.info(f"[api] Listening on http://{self.host}:{self.port}")

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)


def main() -> None:
    """Run the API alone, without the engine (development helper)."""
    server = ApiServer(ApiContext())
    server.start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
