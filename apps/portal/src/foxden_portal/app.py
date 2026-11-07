from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import json
import os
import uuid
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from foxden_identity import IdentityError, SigningKey

from . import __version__
from .auth import AuthError, AuthService, RateLimited
from .browser_ws import register_browser_websockets
from .config import ConfigError, Settings
from .contracts import CONTRACT_VERSION, IDENTITY_HEADER
from .database import PortalStore
from .jellyfin import (JellyfinAdapter, JellyfinAuthenticationError, JellyfinError, JellyfinInputError,
                       JellyfinUnavailable)
from .modules import ModuleClient, ModuleRegistry
from .oidc import OIDCClient, OIDCError, OIDCUnavailable
from .watch import WatchSessionError, WatchSessionStore


SESSION_COOKIE = "foxden_portal_session"
CSRF_COOKIE = "foxden_portal_csrf"
PREAUTH_COOKIE = "foxden_portal_preauth"
ROOT = Path(__file__).parent


def create_app(settings: Settings | None = None, module_client: ModuleClient | None = None,
               oidc_client: OIDCClient | None = None,
               jellyfin_adapter: JellyfinAdapter | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = PortalStore(settings.database_path)
    auth = AuthService(settings, store)
    signer = None
    if settings.identity_private_key_path:
        signer = SigningKey.from_file(
            settings.identity_private_key_path, kid=settings.identity_signing_kid,
            issuer=settings.identity_issuer, lifetime=settings.identity_lifetime_seconds,
        )

    def service_assertion(audience: str) -> str:
        if not signer:
            raise IdentityError("Internal identity signing is not configured.")
        return signer.issue(audience=audience, subject="portal-activity", username="portal-activity",
                            roles=[], scopes=["activity:read"], token_use="service")

    client = module_client or ModuleClient(
        settings.module_timeout_seconds,
        service_assertion=service_assertion if signer else None,
    )
    registry = ModuleRegistry(settings.modules, client)
    watch_store = WatchSessionStore(store, settings.jellyfin_token_secret) if settings.watch_enabled else None
    jellyfin = jellyfin_adapter
    if settings.watch_enabled and jellyfin is None:
        jellyfin = JellyfinAdapter(
            settings.jellyfin_internal_url or "", settings.jellyfin_public_url or "",
            settings.jellyfin_timeout_seconds,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        store.initialize()
        yield

    app = FastAPI(title="Fox Den Media Portal", version=__version__, docs_url=None,
                  redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.auth = auth
    app.state.registry = registry
    app.state.oidc = oidc_client or OIDCClient(settings, store)
    app.state.identity_signer = signer
    app.state.watch_store = watch_store
    app.state.jellyfin = jellyfin
    register_browser_websockets(app, store, settings.public_url)
    templates = Jinja2Templates(directory=ROOT / "templates")
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        if IDENTITY_HEADER.lower() in {key.lower() for key in request.headers}:
            return JSONResponse({"detail": "Internal identity headers are not accepted from clients."}, status_code=400)
        request.state.session_token = request.cookies.get(SESSION_COOKIE)
        request.state.session = store.session(request.state.session_token)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self' data:; "
            "script-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
        user = request.state.session
        values = {
            "version": __version__, "user": user,
            "navigation_modules": settings.modules if user and user["role"] == "admin" else (),
            "jellyfin_url": settings.jellyfin_public_url,
            "watch_enabled": settings.watch_enabled,
            "csrf": request.cookies.get(CSRF_COOKIE, ""),
            **(context or {}),
        }
        return templates.TemplateResponse(request=request, name=name, context=values, status_code=status_code)

    def require_user(request: Request) -> dict:
        if not request.state.session:
            raise HTTPException(401, "Authentication required.")
        return request.state.session

    def require_admin(request: Request) -> dict:
        user = require_user(request)
        if user["role"] != "admin":
            raise HTTPException(403, "Administrator access required.")
        return user

    def watch_session(request: Request):
        user = require_user(request)
        if not settings.watch_enabled or not watch_store or not jellyfin:
            raise HTTPException(404, "Watch & Listen is disabled.")
        try:
            return user, watch_store.load(user["user_id"], settings.jellyfin_internal_url or "")
        except WatchSessionError as exc:
            raise HTTPException(409, str(exc)) from None

    def form_csrf(request: Request, supplied: str | None) -> None:
        cookie = request.cookies.get(CSRF_COOKIE)
        if not cookie or not supplied or not secrets_equal(cookie, supplied):
            raise HTTPException(403, "CSRF validation failed.")
        if not store.verify_csrf(request.state.session_token, supplied):
            raise HTTPException(403, "CSRF validation failed.")

    def preauth_csrf(request: Request, supplied: str) -> None:
        cookie = request.cookies.get(PREAUTH_COOKIE)
        if not cookie or not supplied or not secrets_equal(cookie, supplied) or not auth.verify_preauth_csrf(cookie):
            raise HTTPException(403, "CSRF validation failed.")

    def set_preauth(response, token: str) -> None:
        response.set_cookie(PREAUTH_COOKIE, token, max_age=600, httponly=True,
                            secure=settings.cookie_secure, samesite="strict", path="/")

    def set_session(response, user: dict, source: str) -> None:
        token, csrf = store.create_session(user["id"], source, settings.session_seconds)
        response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_seconds, httponly=True,
                            secure=settings.cookie_secure, samesite="strict", path="/")
        response.set_cookie(CSRF_COOKIE, csrf, max_age=settings.session_seconds, httponly=False,
                            secure=settings.cookie_secure, samesite="strict", path="/")
        response.delete_cookie(PREAUTH_COOKIE, path="/")

    @app.get("/health")
    def health():
        return {"status": "healthy", "version": __version__,
                "setup_required": settings.local_enabled and not store.has_admin()}

    @app.get("/api/platform/v1/session")
    def ingress_session(request: Request, audience: str | None = None, required_role: str | None = None):
        """Private Nginx auth_request target; never returns assertions to browsers."""
        supplied = request.headers.get("X-FoxDen-Ingress-Auth", "")
        if (request.headers.get("X-FoxDen-Ingress") != "1"
                or not settings.ingress_auth_secret
                or not secrets_equal(supplied, settings.ingress_auth_secret)):
            raise HTTPException(404)
        if not request.state.session:
            return Response(status_code=401)
        if required_role is not None:
            if required_role != "admin":
                return Response(status_code=503)
            if request.state.session["role"] != "admin":
                return Response(status_code=403)
        headers = {}
        if audience is not None:
            if audience not in {"music", "media"} or not signer:
                return Response(status_code=503)
            session = request.state.session
            headers[IDENTITY_HEADER] = signer.issue(
                audience=audience, subject=session["user_id"], username=session["username"],
                roles=[session["role"]], scopes=["module:access"], token_use="user",
            )
        return Response(status_code=204, headers=headers)

    @app.get("/setup", response_class=HTMLResponse)
    def setup_page(request: Request):
        if not settings.local_enabled:
            return RedirectResponse("/login", status_code=303)
        if store.has_admin() or store.bootstrap_used():
            return RedirectResponse("/login", status_code=303)
        token = auth.preauth_csrf()
        response = render(request, "setup.html", {"csrf": token, "error": None})
        set_preauth(response, token)
        return response

    @app.post("/setup", response_class=HTMLResponse)
    def setup_submit(request: Request, csrf: Annotated[str, Form()], bootstrap_secret: Annotated[str, Form()],
                     username: Annotated[str, Form()], display_name: Annotated[str, Form()],
                     password: Annotated[str, Form()]):
        preauth_csrf(request, csrf)
        try:
            user = auth.create_initial_admin(bootstrap_secret, username, display_name, password)
        except AuthError as exc:
            token = auth.preauth_csrf()
            response = render(request, "setup.html", {"csrf": token, "error": str(exc)}, 400)
            set_preauth(response, token)
            return response
        response = RedirectResponse("/", status_code=303)
        set_session(response, user, "local")
        return response

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        if request.state.session:
            return RedirectResponse("/", status_code=303)
        if settings.local_enabled and not store.has_admin():
            return RedirectResponse("/setup", status_code=303)
        token = auth.preauth_csrf()
        response = render(request, "login.html", {
            "csrf": token, "error": None, "local_enabled": settings.local_enabled,
            "oidc_enabled": settings.oidc_enabled,
        })
        set_preauth(response, token)
        return response

    @app.post("/login", response_class=HTMLResponse)
    def login_submit(request: Request, csrf: Annotated[str, Form()], username: Annotated[str, Form()],
                     password: Annotated[str, Form()]):
        if not settings.local_enabled:
            raise HTTPException(404)
        preauth_csrf(request, csrf)
        client = request.client.host if request.client else "unknown"
        key = hashlib.sha256(f"{client}|{username.lower()}".encode()).hexdigest()
        try:
            user = auth.login(username, password, key)
        except RateLimited as exc:
            token = auth.preauth_csrf()
            response = render(request, "login.html", {"csrf": token, "error": str(exc),
                              "local_enabled": True, "oidc_enabled": settings.oidc_enabled}, 429)
            response.headers["Retry-After"] = str(exc.retry_after)
            set_preauth(response, token)
            return response
        except AuthError as exc:
            token = auth.preauth_csrf()
            response = render(request, "login.html", {"csrf": token, "error": str(exc),
                              "local_enabled": True, "oidc_enabled": settings.oidc_enabled}, 401)
            set_preauth(response, token)
            return response
        response = RedirectResponse("/", status_code=303)
        set_session(response, user, "local")
        return response

    @app.get("/auth/oidc/login")
    async def oidc_login():
        if not settings.oidc_enabled:
            raise HTTPException(404)
        try:
            target = await app.state.oidc.begin("/")
        except OIDCUnavailable:
            return render_error_without_request(templates, 503)
        except OIDCError:
            return render_error_without_request(templates, 400)
        return RedirectResponse(target, status_code=302)

    @app.get("/auth/oidc/callback")
    async def oidc_callback(request: Request, state: str = "", code: str = "", error: str = ""):
        if not settings.oidc_enabled:
            raise HTTPException(404)
        if error or not state or not code:
            return render(request, "error.html", {"message": "The identity provider did not complete login."}, 401)
        try:
            claims, flow = await app.state.oidc.finish(state, code)
            subject, username, display_name, _groups, role = app.state.oidc.authorize_claims(claims)
            user = store.map_external_identity(settings.oidc_issuer or "oidc", subject, username,
                                               display_name, claims, role)
        except OIDCUnavailable as exc:
            return render(request, "error.html", {"message": str(exc)}, 503)
        except (OIDCError, ValueError) as exc:
            return render(request, "error.html", {"message": str(exc)}, 401)
        response = RedirectResponse(flow["return_to"], status_code=303)
        set_session(response, user, "oidc")
        return response

    @app.post("/logout")
    async def logout(request: Request, csrf: Annotated[str, Form()]):
        user = require_user(request)
        form_csrf(request, csrf)
        store.revoke_session(request.state.session_token)
        target = "/login"
        if user["auth_source"] == "oidc" and settings.oidc_logout == "provider" and settings.oidc_enabled:
            try:
                document = await app.state.oidc.discovery()
                endpoint = document.get("end_session_endpoint")
                if endpoint:
                    from urllib.parse import urlencode, urlsplit
                    parsed = urlsplit(endpoint)
                    if parsed.scheme == "https" and parsed.hostname:
                        target = endpoint + "?" + urlencode({"post_logout_redirect_uri": settings.public_url + "/login",
                                                               "client_id": settings.oidc_client_id})
            except OIDCError:
                # Local logout must still succeed when the provider is unavailable.
                pass
        response = RedirectResponse(target, status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return response

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        if settings.local_enabled and not store.has_admin():
            return RedirectResponse("/setup", status_code=303)
        if not request.state.session:
            return RedirectResponse("/login", status_code=303)
        is_admin = request.state.session["role"] == "admin"
        snapshots = await registry.snapshots() if is_admin else []
        csrf = request.cookies.get(CSRF_COOKIE, "")
        return render(request, "dashboard.html", {
            "modules": snapshots, "activity": registry.combined_activity(snapshots), "csrf": csrf,
            "is_admin": is_admin,
        })

    @app.get("/watch/", response_class=HTMLResponse)
    async def watch_home(request: Request):
        user = require_user(request)
        csrf = request.cookies.get(CSRF_COOKIE, "")
        if not settings.watch_enabled or not watch_store or not jellyfin:
            return render(request, "watch.html", {
                "state": "disabled", "csrf": csrf, "home": None, "error": None,
            })
        try:
            session = watch_store.load(user["user_id"], settings.jellyfin_internal_url or "")
        except WatchSessionError as exc:
            return render(request, "watch.html", {
                "state": "reconnect", "csrf": csrf, "home": None, "error": str(exc),
            }, 409)
        if session is None:
            return render(request, "watch.html", {
                "state": "connect", "csrf": csrf, "home": None, "error": None,
            })
        try:
            home = await jellyfin.home(session)
        except JellyfinAuthenticationError as exc:
            return render(request, "watch.html", {
                "state": "reconnect", "csrf": csrf, "home": None, "error": str(exc),
            }, 401)
        except JellyfinUnavailable as exc:
            return render(request, "watch.html", {
                "state": "offline", "csrf": csrf, "home": None, "error": str(exc),
            }, 503)
        except JellyfinError as exc:
            return render(request, "watch.html", {
                "state": "error", "csrf": csrf, "home": None, "error": str(exc),
            }, 502)
        return render(request, "watch.html", {
            "state": "ready", "csrf": csrf, "home": home, "error": None,
        })

    @app.post("/watch/connect", response_class=HTMLResponse)
    async def watch_connect(request: Request, username: Annotated[str, Form()],
                            password: Annotated[str, Form()], csrf: Annotated[str | None, Form()] = None):
        user = require_user(request)
        form_csrf(request, csrf)
        if not settings.watch_enabled or not watch_store or not jellyfin:
            raise HTTPException(404, "Watch & Listen is disabled.")
        client = request.client.host if request.client else "unknown"
        key = hashlib.sha256(f"jellyfin|{client}|{user['user_id']}".encode()).hexdigest()
        retry_after = store.rate_limited(key)
        if retry_after:
            return render(request, "watch.html", {
                "state": "connect", "csrf": csrf, "home": None,
                "error": f"Too many attempts. Try again in {retry_after} seconds.",
            }, 429)
        try:
            session = await jellyfin.authenticate(username.strip(), password, f"foxden-{uuid.uuid4()}")
        except JellyfinAuthenticationError as exc:
            store.record_failure(key, settings.login_max_attempts,
                                 settings.login_window_seconds, settings.login_lock_seconds)
            return render(request, "watch.html", {
                "state": "connect", "csrf": csrf, "home": None, "error": str(exc),
            }, 401)
        except JellyfinError as exc:
            return render(request, "watch.html", {
                "state": "offline", "csrf": csrf, "home": None, "error": str(exc),
            }, 503)
        store.clear_failures(key)
        watch_store.save(user["user_id"], settings.jellyfin_internal_url or "", session)
        return RedirectResponse("/watch/", status_code=303)

    @app.post("/watch/disconnect")
    async def watch_disconnect(request: Request, csrf: Annotated[str | None, Form()] = None):
        user = require_user(request)
        form_csrf(request, csrf)
        if settings.watch_enabled and watch_store and jellyfin:
            try:
                session = watch_store.load(user["user_id"], settings.jellyfin_internal_url or "")
                if session:
                    await jellyfin.logout(session)
            except WatchSessionError:
                pass
            watch_store.delete(user["user_id"])
        return RedirectResponse("/watch/", status_code=303)

    @app.get("/watch/search", response_class=HTMLResponse)
    async def watch_search(request: Request, q: str = ""):
        _user, session = watch_session(request)
        if session is None:
            return RedirectResponse("/watch/", status_code=303)
        try:
            results = await jellyfin.search(session, q)
        except JellyfinInputError as exc:
            return render(request, "watch_search.html", {"query": q, "items": [], "error": str(exc)}, 400)
        except JellyfinError as exc:
            return render(request, "watch_search.html", {"query": q, "items": [], "error": str(exc)}, 502)
        return render(request, "watch_search.html", {
            "query": results["query"], "items": results["items"], "error": None,
        })

    @app.get("/watch/item/{item_id}", response_class=HTMLResponse)
    async def watch_item(request: Request, item_id: str):
        _user, session = watch_session(request)
        if session is None:
            return RedirectResponse("/watch/", status_code=303)
        try:
            result = await jellyfin.item(session, item_id)
        except JellyfinInputError as exc:
            return render(request, "error.html", {"message": str(exc)}, 400)
        except JellyfinError as exc:
            return render(request, "error.html", {"message": str(exc)}, 502)
        return render(request, "watch_item.html", {"item": result["item"]})

    @app.get("/watch/browse/{kind}", response_class=HTMLResponse)
    async def watch_browse(request: Request, kind: str, start: int = 0):
        _user, session = watch_session(request)
        if session is None:
            return RedirectResponse("/watch/", status_code=303)
        try:
            result = await jellyfin.browse(session, kind, start=start)
        except JellyfinInputError as exc:
            return render(request, "error.html", {"message": str(exc)}, 400)
        except JellyfinError as exc:
            return render(request, "error.html", {"message": str(exc)}, 502)
        return render(request, "watch_browse.html", result)

    @app.get("/api/watch/v1/session")
    async def watch_api_session(request: Request):
        user = require_user(request)
        if not settings.watch_enabled or not watch_store:
            return {"contract_version": "1.0", "state": "disabled", "connected": False}
        try:
            session = watch_store.load(user["user_id"], settings.jellyfin_internal_url or "")
        except WatchSessionError:
            return {"contract_version": "1.0", "state": "reconnect", "connected": False}
        return {"contract_version": "1.0", "state": "ready" if session else "connect",
                "connected": bool(session), "user": session.username if session else None}

    @app.get("/api/watch/v1/home")
    async def watch_api_home(request: Request):
        _user, session = watch_session(request)
        if session is None:
            raise HTTPException(409, "Connect a Jellyfin account first.")
        try:
            return await jellyfin.home(session)
        except JellyfinAuthenticationError as exc:
            raise HTTPException(401, str(exc)) from None
        except JellyfinUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        except JellyfinError as exc:
            raise HTTPException(502, str(exc)) from None

    @app.get("/api/watch/v1/search")
    async def watch_api_search(request: Request, q: str = ""):
        _user, session = watch_session(request)
        if session is None:
            raise HTTPException(409, "Connect a Jellyfin account first.")
        try:
            return await jellyfin.search(session, q)
        except JellyfinInputError as exc:
            raise HTTPException(400, str(exc)) from None
        except JellyfinError as exc:
            raise HTTPException(502, str(exc)) from None

    @app.get("/api/watch/v1/browse/{kind}")
    async def watch_api_browse(request: Request, kind: str, start: int = 0, limit: int = 60):
        _user, session = watch_session(request)
        if session is None:
            raise HTTPException(409, "Connect a Jellyfin account first.")
        try:
            return await jellyfin.browse(session, kind, start=start, limit=limit)
        except JellyfinInputError as exc:
            raise HTTPException(400, str(exc)) from None
        except JellyfinError as exc:
            raise HTTPException(502, str(exc)) from None

    @app.get("/api/watch/v1/items/{item_id}")
    async def watch_api_item(request: Request, item_id: str):
        _user, session = watch_session(request)
        if session is None:
            raise HTTPException(409, "Connect a Jellyfin account first.")
        try:
            return await jellyfin.item(session, item_id)
        except JellyfinInputError as exc:
            raise HTTPException(400, str(exc)) from None
        except JellyfinError as exc:
            raise HTTPException(502, str(exc)) from None

    @app.get("/api/watch/v1/artwork/{item_id}")
    async def watch_artwork(request: Request, item_id: str, width: int = 640):
        _user, session = watch_session(request)
        if session is None:
            raise HTTPException(409, "Connect a Jellyfin account first.")
        try:
            content, content_type = await jellyfin.artwork(session, item_id, width)
        except JellyfinInputError as exc:
            raise HTTPException(400, str(exc)) from None
        except JellyfinAuthenticationError as exc:
            raise HTTPException(401, str(exc)) from None
        except JellyfinUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        except JellyfinError as exc:
            raise HTTPException(502, str(exc)) from None
        return Response(content=content, media_type=content_type,
                        headers={"Cache-Control": "private, max-age=300"})

    @app.get("/admin/users", response_class=HTMLResponse)
    def users_page(request: Request):
        require_admin(request)
        return render(request, "users.html", {"users": store.users(), "csrf": request.cookies.get(CSRF_COOKIE, ""),
                                               "error": None, "success": None})

    @app.post("/admin/users", response_class=HTMLResponse)
    def create_user(request: Request, csrf: Annotated[str, Form()], username: Annotated[str, Form()],
                    display_name: Annotated[str, Form()], password: Annotated[str, Form()],
                    role: Annotated[str, Form()] = "user"):
        require_admin(request)
        form_csrf(request, csrf)
        try:
            auth.create_user(username, display_name, password, role)
            message, error, status = "Account created.", None, 200
        except (AuthError, ValueError) as exc:
            message, error, status = None, str(exc), 400
        return render(request, "users.html", {"users": store.users(), "csrf": csrf,
                                               "error": error, "success": message}, status)

    @app.post("/admin/users/reset-password", response_class=HTMLResponse)
    def reset_password(request: Request, csrf: Annotated[str, Form()], username: Annotated[str, Form()],
                       password: Annotated[str, Form()]):
        require_admin(request)
        form_csrf(request, csrf)
        try:
            auth.set_password(username, password)
            message, error, status = "Password reset and existing sessions revoked.", None, 200
        except (AuthError, ValueError) as exc:
            message, error, status = None, str(exc), 400
        return render(request, "users.html", {"users": store.users(), "csrf": csrf,
                                               "error": error, "success": message}, status)

    @app.get("/api/platform/v1/status")
    async def platform_status(request: Request):
        require_admin(request)
        snapshots = await registry.snapshots()
        return {
            "contract_version": CONTRACT_VERSION,
            "platform_version": __version__,
            "modules": [{
                "id": item.module_id, "name": item.name, "state": item.state,
                "summary": item.summary, "version": item.version,
                "capabilities": item.capabilities,
            } for item in snapshots],
            "activity": registry.combined_activity(snapshots),
        }

    @app.get("/api/platform/v1/config")
    def redacted_config(request: Request):
        require_admin(request)
        return settings.redacted()

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code,
                                headers=exc.headers)
        if exc.status_code == 401:
            return RedirectResponse("/login", status_code=303)
        return render(request, "error.html", {"message": str(exc.detail)}, exc.status_code)

    return app


def secrets_equal(left: str, right: str) -> bool:
    import secrets
    return secrets.compare_digest(left.encode(), right.encode())


def render_error_without_request(_templates, status_code: int):
    # OIDC begin has no request-specific data; keep failure output minimal and safe.
    message = ("The identity provider is currently unavailable."
               if status_code == 503 else "External login could not be started.")
    return HTMLResponse(f"<!doctype html><title>Fox Den Media</title><h1>Login unavailable</h1><p>{html_escape(message)}</p>",
                        status_code=status_code)


def html_escape(value: str) -> str:
    import html
    return html.escape(value, quote=True)


def run() -> None:
    import uvicorn
    # Container listener; Compose publishes only ingress and keeps this port private.
    uvicorn.run("foxden_portal.app:create_app", factory=True, host="0.0.0.0", port=8020,  # nosec B104
                workers=1, proxy_headers=False)
