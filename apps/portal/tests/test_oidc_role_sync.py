"""OIDC external role synchronization: one bug, one patch release (#57)."""
from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from foxden_portal.app import create_app
from foxden_portal.oidc import OIDCClient, OIDCUnavailable
from conftest import bootstrap_admin, settings


class MutableOIDC:
    """Simulate *verified* token claims at the callback boundary.

    Cryptographic signature, nonce, state, audience and expiry checks are covered
    independently by test_oidc_protocol.py.
    """
    def __init__(self, configured):
        self.configured = configured
        self.claims = {
            "sub": "external-stable-subject",
            "preferred_username": "oidc-operator",
            "name": "External Operator",
            "groups": ["foxden-admins"],
        }
        self.offline = False

    async def finish(self, state, code):
        if self.offline:
            raise OIDCUnavailable("The identity provider could not complete login.")
        return dict(self.claims), {"return_to": "/"}

    def authorize_claims(self, claims):
        return OIDCClient(self.configured, None).authorize_claims(claims)


def configured_fixture(tmp_path, *, allowed_groups=()):
    configured = replace(
        settings(tmp_path, auth_mode="hybrid"),
        oidc_allowed_groups=allowed_groups,
        ingress_auth_secret="test-ingress-secret-12345678901234567890",
    )
    return configured, MutableOIDC(configured)


def callback(client):
    return client.get("/auth/oidc/callback?state=valid&code=valid", follow_redirects=False)


def admin_ingress(client, configured):
    return client.get(
        "/api/platform/v1/session?required_role=admin",
        headers={
            "X-FoxDen-Ingress": "1",
            "X-FoxDen-Ingress-Auth": configured.ingress_auth_secret,
        },
    )


def test_admin_promotion_and_demotion_revoke_prior_sessions(tmp_path):
    configured, idp = configured_fixture(tmp_path)
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        store = client.app.state.store
        local_token = client.cookies.get("foxden_portal_session")

        idp.claims["groups"] = []
        assert callback(client).status_code == 303
        external = store.user_by_username("oidc-operator")
        assert external["role"] == "user"
        viewer_token = client.cookies.get("foxden_portal_session")
        assert client.get("/api/platform/v1/status").status_code == 403
        assert admin_ingress(client, configured).status_code == 403

        idp.claims["groups"] = ["foxden-admins"]
        assert callback(client).status_code == 303
        assert store.user_by_id(external["id"])["role"] == "admin"
        assert store.session(viewer_token) is None
        admin_token = client.cookies.get("foxden_portal_session")
        assert admin_ingress(client, configured).status_code == 204
        assert client.get("/api/platform/v1/status").status_code == 200

        idp.claims["groups"] = ["ordinary-users"]
        assert callback(client).status_code == 303
        assert store.user_by_id(external["id"])["role"] == "user"
        assert store.session(admin_token) is None
        assert client.get("/admin/users").status_code == 403
        assert client.get("/api/platform/v1/status").status_code == 403
        assert admin_ingress(client, configured).status_code == 403
        # This emergency local administrator is an independent account.
        assert store.session(local_token)["role"] == "admin"


@pytest.mark.parametrize("groups", [None, "foxden-admins", {"group": "foxden-admins"}, []])
def test_missing_or_malformed_group_claim_demotes_admin(tmp_path, groups):
    configured, idp = configured_fixture(tmp_path)
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        assert callback(client).status_code == 303
        store = client.app.state.store
        admin_token = client.cookies.get("foxden_portal_session")
        if groups is None:
            idp.claims.pop("groups")
        else:
            idp.claims["groups"] = groups
        assert callback(client).status_code == 303
        assert store.user_by_username("oidc-operator")["role"] == "user"
        assert store.session(admin_token) is None
        assert admin_ingress(client, configured).status_code == 403


def test_allowlist_removal_revokes_sessions_and_downgrades_external_user(tmp_path):
    configured, idp = configured_fixture(tmp_path, allowed_groups=("foxden-users",))
    idp.claims["groups"] = ["foxden-users", "foxden-admins"]
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        assert callback(client).status_code == 303
        store = client.app.state.store
        admin_token = client.cookies.get("foxden_portal_session")
        assert admin_ingress(client, configured).status_code == 204
        # Authentik still emits an admin group, but access group was removed.
        idp.claims["groups"] = ["foxden-admins"]
        rejected = callback(client)
        assert rejected.status_code == 401
        assert "not authorized" in rejected.text
        assert store.session(admin_token) is None
        assert store.user_by_username("oidc-operator")["role"] == "user"
        assert client.get("/api/platform/v1/status").status_code == 401
        assert admin_ingress(client, configured).status_code == 401

        # Valid membership can be reinstated by a subsequent verified login.
        idp.claims["groups"] = ["foxden-users", "foxden-admins"]
        assert callback(client).status_code == 303
        assert admin_ingress(client, configured).status_code == 204


@pytest.mark.parametrize("groups", [None, "foxden-users"])
def test_missing_or_invalid_allowed_groups_revoke_instead_of_trusting_old_role(tmp_path, groups):
    configured, idp = configured_fixture(tmp_path, allowed_groups=("foxden-users",))
    idp.claims["groups"] = ["foxden-users", "foxden-admins"]
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        assert callback(client).status_code == 303
        store = client.app.state.store
        admin_token = client.cookies.get("foxden_portal_session")
        if groups is None:
            idp.claims.pop("groups")
        else:
            idp.claims["groups"] = [groups]
        rejected = callback(client) if groups is None else None
        if groups is None:
            assert rejected.status_code == 401
            assert store.session(admin_token) is None
        else:
            # An allowed but non-admin group explicitly demotes, without denying login.
            assert callback(client).status_code == 303
            assert store.session(admin_token) is None
        assert store.user_by_username("oidc-operator")["role"] == "user"
        assert admin_ingress(client, configured).status_code in {401, 403}


def test_locally_disabled_external_user_cannot_log_in_or_reuse_session(tmp_path):
    configured, idp = configured_fixture(tmp_path)
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        local_token = client.cookies.get("foxden_portal_session")
        assert callback(client).status_code == 303
        store = client.app.state.store
        external = store.user_by_username("oidc-operator")
        external_token = client.cookies.get("foxden_portal_session")
        with store.connection() as db:
            db.execute("UPDATE users SET active=0 WHERE id=?", (external["id"],))
        assert store.session(external_token) is None
        denied = callback(client)
        assert denied.status_code == 401
        assert "disabled" in denied.text
        assert client.get("/api/platform/v1/status").status_code == 401
        assert store.session(local_token)["role"] == "admin"


def test_idp_outage_does_not_invent_role_changes_or_destroy_existing_session(tmp_path):
    configured, idp = configured_fixture(tmp_path)
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        assert callback(client).status_code == 303
        token = client.cookies.get("foxden_portal_session")
        idp.offline = True
        idp.claims["groups"] = []
        assert callback(client).status_code == 503
        # No new trusted claims: prior Portal session remains until its own
        # expiry/revocation. This test does not claim upstream instant revocation.
        assert client.app.state.store.session(token)["role"] == "admin"
        assert admin_ingress(client, configured).status_code == 204


def test_emergency_local_account_and_username_collision_are_unchanged(tmp_path):
    configured, idp = configured_fixture(tmp_path)
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client, username="oidc-operator")
        store = client.app.state.store
        local = store.user_by_username("oidc-operator")
        local_token = client.cookies.get("foxden_portal_session")
        assert callback(client).status_code == 303
        external = store.user_by_username("oidc-operator-2")
        assert external and external["id"] != local["id"]
        idp.claims["groups"] = []
        assert callback(client).status_code == 303
        assert store.user_by_id(external["id"])["role"] == "user"
        assert store.user_by_id(local["id"])["role"] == "admin"
        assert store.session(local_token)["role"] == "admin"
        client.cookies.set("foxden_portal_session", local_token)
        assert client.get("/admin/users").status_code == 200


def test_unlinked_subject_denial_cannot_change_other_or_local_users(tmp_path):
    configured, idp = configured_fixture(tmp_path, allowed_groups=("foxden-users",))
    idp.claims["groups"] = ["foxden-users", "foxden-admins"]
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        local_token = client.cookies.get("foxden_portal_session")
        assert callback(client).status_code == 303
        store = client.app.state.store
        prior_external_token = client.cookies.get("foxden_portal_session")
        idp.claims["sub"] = "different-unlinked-subject"
        idp.claims["groups"] = []
        assert callback(client).status_code == 401
        assert store.session(prior_external_token)["role"] == "admin"
        assert store.session(local_token)["role"] == "admin"


def test_invalid_external_role_is_rejected_before_any_write(tmp_path):
    configured, idp = configured_fixture(tmp_path)
    with TestClient(create_app(configured, oidc_client=idp)) as client:
        bootstrap_admin(client)
        store = client.app.state.store
        with pytest.raises(ValueError, match="Unsupported external identity role"):
            store.map_external_identity(configured.oidc_issuer, "subject", "user", "User", {}, "owner")
        with store.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM external_identities").fetchone()[0] == 0
