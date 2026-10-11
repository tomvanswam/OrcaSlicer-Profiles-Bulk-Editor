"""A small local HTTP server: serves the single-page UI and a read-only JSON API.

Endpoints
    GET /                       the UI
    GET /api/profiles           all profiles (summary)
    GET /api/chain?name=&type=  resolved chain for one profile
    POST /api/edit              preview (``apply: false``) or write setting changes

New features (matrix, bulk edit) add their endpoints to ``ROUTES``.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import parse_qs, urlparse

from orca_profiles.core.editor import EditError, apply, plan
from orca_profiles.core.model import ProfileType
from orca_profiles.core.repository import ProfileRepository
from orca_profiles.core.resolver import resolve
from orca_profiles.core.serialize import edit_to_json, profile_ref, resolved_to_json

log = logging.getLogger(__name__)

Query = dict[str, list[str]]


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


def api_profiles(repo: ProfileRepository, _q: Query) -> Any:
    return {
        "profiles": [
            profile_ref(p) | {"instantiable": p.is_instantiable}
            for p in sorted(repo, key=lambda p: (p.type, p.origin, p.name.casefold()))
        ],
        "errors": repo.errors,
    }


def api_chain(repo: ProfileRepository, q: Query) -> Any:
    name = q.get("name", [""])[0]
    type_ = q.get("type", [""])[0]
    try:
        ptype = ProfileType(type_) if type_ else None
    except ValueError:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"unknown type '{type_}'") from None
    matches = repo.find(name, ptype)
    if not matches:
        raise ApiError(HTTPStatus.NOT_FOUND, f"profile '{name}' not found")
    path = q.get("path", [""])[0]
    profile = next((p for p in matches if str(p.path) == path), matches[0])
    return resolved_to_json(resolve(profile, repo))


def api_edit(repo: ProfileRepository, body: Any) -> Any:
    """Body: ``{"edits": [{"path": str, "set": {key: value}, "inherit": [key]}],
    "apply": bool}``. String values are parsed like the CLI does (``220`` becomes
    ``["220"]`` for list settings)."""
    if not isinstance(body, dict) or not isinstance(body.get("edits"), list):
        raise ApiError(HTTPStatus.BAD_REQUEST, "expected {'edits': [...]}")
    edits = []
    try:
        for item in body["edits"]:
            profile = repo.find_by_path(item.get("path", ""))
            if profile is None:
                raise ApiError(HTTPStatus.NOT_FOUND, f"no profile at {item.get('path')!r}")
            edits.append(plan(profile, repo, item.get("set") or {}, item.get("inherit") or []))
    except EditError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from None
    result: dict[str, Any] = {"edits": [edit_to_json(e) for e in edits], "applied": False}
    if body.get("apply"):
        written = apply([e for e in edits if e.changes], repo)
        result |= {"applied": True, "backups": [str(b) for _, b in written]}
    return result


ROUTES: dict[str, Callable[[ProfileRepository, Query], Any]] = {
    "/api/profiles": api_profiles,
    "/api/chain": api_chain,
}
POST_ROUTES: dict[str, Callable[[ProfileRepository, Any], Any]] = {
    "/api/edit": api_edit,
}


def make_handler(repo: ProfileRepository) -> type[BaseHTTPRequestHandler]:
    lock = threading.Lock()
    index = files("orca_profiles.gui").joinpath("static/index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, index, "text/html; charset=utf-8")
                return
            route = ROUTES.get(url.path)
            if route is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                self._json(HTTPStatus.OK, route(repo, parse_qs(url.query)))
            except ApiError as exc:
                self._json(exc.status, {"error": str(exc)})

        def do_POST(self) -> None:
            route = POST_ROUTES.get(urlparse(self.path).path)
            if route is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            # Only accept JSON from our own page (blocks cross-site form posts).
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "expected JSON"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"null")
            except (ValueError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"})
                return
            try:
                with lock:
                    self._json(HTTPStatus.OK, route(repo, body))
            except ApiError as exc:
                self._json(exc.status, {"error": str(exc)})

        def _json(self, status: HTTPStatus, body: Any) -> None:
            data = json.dumps(body, ensure_ascii=False).encode()
            self._send(status, data, "application/json; charset=utf-8")

        def _send(self, status: HTTPStatus, data: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            log.info("%s - %s", self.address_string(), format % args)

    return Handler


def create_server(repo: ProfileRepository, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(repo))
