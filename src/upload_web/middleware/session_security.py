from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any, TypedDict, cast
from urllib.parse import urlencode

from fastapi import Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.auth.entra import (
    LEGACY_ID_TOKEN_HEADER,
    AuthenticatedUser,
    EntraAuthError,
    build_authenticated_user_from_easy_auth_headers,
)
from src.upload_web.config import UploadWebSettings

SESSION_COOKIE_NAME = "upload_web_session"
IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_SESSION_TIMEOUT = timedelta(hours=8)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self' https://login.microsoftonline.com"
    ),
}
EXEMPT_PATH_PREFIXES = ("/static", "/.auth")
EXEMPT_PATHS = {"/", "/login", "/healthz", "/readyz", "/logout"}


class SessionSecurityError(ValueError):
    """Raised when the signed Upload Web session cannot be trusted."""


class SessionCookiePayload(TypedDict):
    oid: str
    name: str
    groups: list[str]
    exp: int
    last_activity: int
    csrf_token: str


class SessionSecurityManager:
    def __init__(self, settings: UploadWebSettings) -> None:
        self._settings = settings
        self._serializer = URLSafeSerializer(settings.session_signing_key, salt="upload-web-session")

    def dumps(self, payload: SessionCookiePayload) -> str:
        return self._serializer.dumps(payload)

    def loads(self, value: str) -> SessionCookiePayload:
        try:
            data = self._serializer.loads(value)
        except BadSignature as exc:
            raise SessionSecurityError("Invalid signed session cookie.") from exc

        if not isinstance(data, dict):
            raise SessionSecurityError("Signed session cookie payload is invalid.")

        oid = data.get("oid")
        name = data.get("name")
        exp = data.get("exp")
        last_activity = data.get("last_activity")
        csrf_token = data.get("csrf_token")
        raw_groups = data.get("groups", [])

        if not isinstance(oid, str) or not oid.strip():
            raise SessionSecurityError("Signed session cookie is missing oid.")
        if not isinstance(name, str) or not name.strip():
            raise SessionSecurityError("Signed session cookie is missing name.")
        if not isinstance(exp, int):
            raise SessionSecurityError("Signed session cookie is missing exp.")
        if not isinstance(last_activity, int):
            raise SessionSecurityError("Signed session cookie is missing last_activity.")
        if not isinstance(csrf_token, str) or not csrf_token.strip():
            raise SessionSecurityError("Signed session cookie is missing csrf_token.")
        if not isinstance(raw_groups, list):
            raise SessionSecurityError("Signed session cookie groups are invalid.")

        groups = [str(group).strip() for group in raw_groups if str(group).strip()]
        return {
            "oid": oid.strip(),
            "name": name.strip(),
            "groups": groups,
            "exp": exp,
            "last_activity": last_activity,
            "csrf_token": csrf_token.strip(),
        }

    def build_payload(
        self,
        user: AuthenticatedUser,
        now: datetime,
        *,
        token_expiry: int | None,
        existing_payload: SessionCookiePayload | None = None,
    ) -> SessionCookiePayload:
        absolute_expiry = int((now + ABSOLUTE_SESSION_TIMEOUT).timestamp())
        exp = min(token_expiry or absolute_expiry, absolute_expiry)
        csrf_token = (
            existing_payload["csrf_token"]
            if existing_payload is not None and existing_payload["oid"] == user.oid
            else token_urlsafe(32)
        )
        return {
            "oid": user.oid,
            "name": user.name,
            "groups": list(user.groups),
            "exp": exp,
            "last_activity": int(now.timestamp()),
            "csrf_token": csrf_token,
        }

    @staticmethod
    def build_user(payload: SessionCookiePayload) -> AuthenticatedUser:
        return AuthenticatedUser(
            oid=payload["oid"],
            name=payload["name"],
            groups=tuple(payload["groups"]),
            claims={"exp": payload["exp"]},
        )

    @staticmethod
    def is_idle(payload: SessionCookiePayload, now: datetime) -> bool:
        last_activity = datetime.fromtimestamp(payload["last_activity"], tz=UTC)
        return now - last_activity > IDLE_TIMEOUT

    @staticmethod
    def is_expired(payload: SessionCookiePayload, now: datetime) -> bool:
        return now.timestamp() >= payload["exp"]

    def set_session_cookie(self, response: Response, payload: SessionCookiePayload) -> None:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=self.dumps(payload),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=int(ABSOLUTE_SESSION_TIMEOUT.total_seconds()),
            path="/",
        )

    @staticmethod
    def clear_session_cookie(response: Response) -> None:
        response.delete_cookie(
            key=SESSION_COOKIE_NAME,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )


class SessionSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, settings: UploadWebSettings) -> None:
        super().__init__(app)
        self._manager = SessionSecurityManager(settings)

    async def dispatch(  # noqa: C901
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        now = datetime.now(UTC)
        path = request.url.path
        session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        existing_payload: SessionCookiePayload | None = None

        if session_cookie is not None:
            try:
                existing_payload = self._manager.loads(session_cookie)
            except SessionSecurityError:
                existing_payload = None

        if existing_payload is not None:
            if self._manager.is_expired(existing_payload, now):
                return _apply_security_headers(RedirectResponse(url="/logout?reason=expired", status_code=307))
            if not _is_exempt_path(path) and self._manager.is_idle(existing_payload, now):
                return _apply_security_headers(RedirectResponse(url="/logout?reason=idle", status_code=307))

        resolved_payload: SessionCookiePayload | None = None
        resolved_user: AuthenticatedUser | None = None

        resolved_user, token_expiry = _resolve_authenticated_user(request)
        if resolved_user is not None:
            if token_expiry is not None and now.timestamp() >= token_expiry:
                return _apply_security_headers(RedirectResponse(url="/logout?reason=expired", status_code=307))
            resolved_payload = self._manager.build_payload(
                resolved_user,
                now,
                token_expiry=token_expiry,
                existing_payload=existing_payload,
            )
        elif existing_payload is not None:
            resolved_payload = dict(existing_payload)
            resolved_payload["last_activity"] = int(now.timestamp())
            resolved_user = self._manager.build_user(existing_payload)

        if resolved_payload is not None and resolved_user is not None:
            request.state.authenticated_user = resolved_user
            request.state.csrf_token = resolved_payload["csrf_token"]

        if resolved_payload is not None and request.method.upper() not in SAFE_METHODS and not _is_exempt_path(path):
            if not await _validate_csrf_token(request, resolved_payload["csrf_token"]):
                response = JSONResponse(
                    {"detail": "CSRF token validation failed."}, status_code=status.HTTP_403_FORBIDDEN
                )
                return _apply_security_headers(response)

        response = await call_next(request)

        if resolved_payload is not None:
            self._manager.set_session_cookie(response, resolved_payload)

        return _apply_security_headers(response)


async def get_upload_current_user(
    request: Request,
    _legacy_id_token: str | None = Header(default=None, alias=LEGACY_ID_TOKEN_HEADER),
) -> AuthenticatedUser:
    user = cast(AuthenticatedUser | None, getattr(request.state, "authenticated_user", None))
    if user is not None:
        return user

    resolved_user, _ = _resolve_authenticated_user(request)
    if resolved_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")

    return resolved_user


def security_template_context(request: Request) -> dict[str, Any]:
    notice = None
    if request.query_params.get("session_ended") == "idle":
        notice = "Sesión cerrada por inactividad tras 30 minutos sin uso."

    return {
        "csrf_token": getattr(request.state, "csrf_token", ""),
        "current_user": getattr(request.state, "authenticated_user", None),
        "session_notice": notice,
    }


def build_logout_redirect(reason: str | None = None) -> str:
    redirect_target = "/"
    if reason == "idle":
        redirect_target = "/?session_ended=idle"
    query = urlencode({"post_logout_redirect_uri": redirect_target})
    return f"/.auth/logout?{query}"


def _apply_security_headers(response: Response) -> Response:
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers[header_name] = header_value
    return response


def _extract_expiry(claims: dict[str, Any]) -> int | None:
    raw_exp = claims.get("exp")
    if isinstance(raw_exp, int):
        return raw_exp
    if isinstance(raw_exp, str) and raw_exp.isdigit():
        return int(raw_exp)
    return None


def _resolve_authenticated_user(request: Request) -> tuple[AuthenticatedUser | None, int | None]:
    try:
        user = build_authenticated_user_from_easy_auth_headers(request.headers)
    except EntraAuthError:
        return None, None

    return user, _extract_expiry(user.claims)


def _is_exempt_path(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)


async def _validate_csrf_token(request: Request, expected_token: str) -> bool:
    submitted_token = request.headers.get("X-CSRF-Token")
    if submitted_token is None or not submitted_token.strip():
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded") or content_type.startswith(
            "multipart/form-data"
        ):
            form = await request.form()
            raw_form_token = form.get("csrf_token") or form.get("_csrf_token")
            if raw_form_token is not None:
                submitted_token = str(raw_form_token)

    return submitted_token == expected_token
