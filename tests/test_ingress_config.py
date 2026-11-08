from pathlib import Path


CONFIG = (Path(__file__).parents[1] / "infra" / "gateway" / "portal-ingress.conf").read_text(encoding="utf-8")


def test_portal_is_root_and_auth_authority():
    assert "set $portal_backend portal:8020;" in CONFIG
    assert "proxy_pass http://$portal_backend/api/platform/v1/session?required_role=admin;" in CONFIG
    assert "location / {" in CONFIG
    assert "set $auth_backend media:8010" not in CONFIG
    assert "audience=music" in CONFIG and "audience=media" in CONFIG
    assert CONFIG.count("required_role=admin") == 3
    assert "auth_request_set $foxden_music_identity" in CONFIG
    assert "auth_request_set $foxden_media_identity" in CONFIG


def test_optional_modules_use_deferred_resolution_and_safe_failure():
    for backend in ("music:8000", "media:8010", "download-browser:5800", "jellyfin:8096"):
        assert f"set $" in CONFIG and backend in CONFIG
    assert "resolver 127.0.0.11" in CONFIG
    assert CONFIG.count("error_page 502 503 504 = @module_unavailable;") == 3
    assert 'return 503 "Module unavailable\\n";' in CONFIG
    assert 'return 503 "Jellyfin unavailable\\n";' in CONFIG


def test_jellyfin_uses_dedicated_native_auth_host_and_no_portal_auth_request():
    block = CONFIG.split("server_name __JELLYFIN_PUBLIC_HOST__;", 1)[1].split("server {", 1)[0]
    assert "listen 8080 default_server" not in block
    assert "set $jellyfin_backend jellyfin:8096;" in block
    assert "auth_request" not in block
    assert "proxy_set_header Upgrade $http_upgrade;" in block
    assert "proxy_buffering off;" in block
    assert "access_log off;" in block
    assert "foxden-theme.css" in block and "foxden-mascot.png" in block


def test_portal_is_the_default_host_when_jellyfin_name_does_not_match():
    assert "listen 8080 default_server;\n        server_name _;" in CONFIG


def test_ingress_strips_identity_headers_and_preserves_transport_controls():
    assert CONFIG.count('proxy_set_header X-FoxDen-Identity "";') == 8
    for header in ("X-Authentik-Username", "X-Authentik-Groups", "X-Authentik-Email",
                   "X-Authentik-Uid", "X-Authentik-Jwt"):
        assert CONFIG.count(f'proxy_set_header {header} "";') == 8
    assert CONFIG.count('proxy_set_header X-FoxDen-Ingress "";') == 7
    assert CONFIG.count('proxy_set_header X-FoxDen-Ingress "1";') == 3
    assert CONFIG.count('proxy_set_header X-FoxDen-Ingress-Auth "";') == 7
    assert CONFIG.count('__PORTAL_INGRESS_AUTH_SECRET__') == 3
    assert "proxy_set_header X-FoxDen-Identity $foxden_music_identity;" in CONFIG
    assert "proxy_set_header X-FoxDen-Identity $foxden_media_identity;" in CONFIG
    assert CONFIG.count("error_page 500 = @auth_unavailable;") == 3
    assert CONFIG.count("proxy_connect_timeout 2s;") == 3
    assert CONFIG.count("proxy_read_timeout 2s;") == 3
    assert CONFIG.count("proxy_send_timeout 2s;") == 3
    assert "proxy_request_buffering off;" in CONFIG
    assert "proxy_set_header Upgrade $http_upgrade;" in CONFIG
    assert "proxy_set_header Connection $connection_upgrade;" in CONFIG
    assert CONFIG.count("proxy_set_header X-Forwarded-Proto $scheme;") == 5
    assert CONFIG.count("proxy_set_header X-Forwarded-Host $http_host;") == 5


def test_server_browser_websocket_fails_closed_and_documents_idle_timeout_limit():
    block = CONFIG.split("location /server-browser/ {", 1)[1].split("\n        }", 1)[0]
    assert "auth_request /_foxden_portal_auth;" in block
    assert "error_page 500 = @auth_unavailable;" in block
    assert "proxy_set_header Upgrade $http_upgrade;" in block
    assert "proxy_set_header X-FoxDen-Identity \"\";" in block
    assert "set $browser_backend $foxden_browser_upstream;" in block
    assert "one-hour maximum" in block
    assert "inactivity, not lifetime" in block
    assert "map $http_upgrade $foxden_browser_upstream" in CONFIG
    assert "default portal:8020;" in CONFIG
    assert "'' download-browser:5800;" in CONFIG
    assert "proxy_read_timeout 3600s;" in block
    assert "86400s" not in block
