# tests/unit/test_auth_service.py
#
# Unit tests para AuthService y Session — pre-Fase 7.
# Sin BD, sin red, sin Supabase real. 100% unitarios.
#
# PATRÓN: MagicMock para auth_repo y tenant_repo.
# Session es la clase real — se limpia antes y después de cada test.
#
# Total: 8 tests

import pytest
from unittest.mock import MagicMock

from session.session import Session
from domain.services.auth_service import AuthService
from domain.exceptions import AuthenticationError


def _make_svc(auth_repo=None, tenant_repo=None):
    auth_repo   = auth_repo   or MagicMock()
    tenant_repo = tenant_repo or MagicMock()
    return AuthService(auth_repo=auth_repo, tenant_repo=tenant_repo), auth_repo, tenant_repo


def _fake_user(uid="u-1", email="test@example.com"):
    return type("User", (), {"id": uid, "email": email})()


@pytest.fixture(autouse=True)
def limpiar_sesion():
    Session.end()
    yield
    Session.end()


# ── TestSession ────────────────────────────────────────────────────────────────

class TestSession:

    def test_session_es_none_antes_de_login(self):
        assert Session.tenant_id    is None
        assert Session.current_user is None

    def test_session_tiene_tenant_id_despues_de_login(self):
        user = _fake_user()
        Session.start(user, "tenant-1", "admin")
        assert Session.tenant_id    == "tenant-1"
        assert Session.current_user is user

    def test_logout_limpia_sesion(self):
        user = _fake_user()
        Session.start(user, "tenant-1", "admin")
        Session.end()
        assert Session.tenant_id    is None
        assert Session.current_user is None


# ── TestAuthService ────────────────────────────────────────────────────────────

class TestAuthService:

    def test_login_exitoso_guarda_perfil(self):
        auth_repo = MagicMock()
        user = _fake_user()
        auth_repo.sign_in.return_value    = MagicMock(user=user)
        auth_repo.get_profile.return_value = MagicMock(
            data=[{"tenant_id": "t-1", "role": "admin"}]
        )

        svc, _, _ = _make_svc(auth_repo=auth_repo)
        svc.login("test@example.com", "password123")

        assert Session.tenant_id    == "t-1"
        assert Session.current_user is user

    def test_login_fallido_lanza_auth_error(self):
        auth_repo = MagicMock()
        auth_repo.sign_in.return_value = MagicMock(user=None)

        svc, _, _ = _make_svc(auth_repo=auth_repo)

        with pytest.raises(AuthenticationError):
            svc.login("test@example.com", "wrongpassword")

    def test_registro_crea_tenant_y_perfil(self):
        auth_repo   = MagicMock()
        tenant_repo = MagicMock()
        user = _fake_user(uid="u-2", email="new@example.com")
        auth_repo.sign_up.return_value         = MagicMock(user=user)
        tenant_repo.create.return_value        = MagicMock(data=[{"id": "t-new"}])
        auth_repo.create_profile.return_value  = MagicMock(data=[{"id": "u-2"}])

        svc, _, _ = _make_svc(auth_repo=auth_repo, tenant_repo=tenant_repo)
        result = svc.register("new@example.com", "password123")

        tenant_repo.create.assert_called_once()
        auth_repo.create_profile.assert_called_once()
        assert result is user

    def test_registro_con_email_duplicado_lanza_excepcion(self):
        """Si sign_up no retorna user (email ya existe), se lanza AuthenticationError."""
        auth_repo = MagicMock()
        auth_repo.sign_up.return_value = MagicMock(user=None)

        svc, _, _ = _make_svc(auth_repo=auth_repo)

        with pytest.raises(AuthenticationError):
            svc.register("existing@example.com", "password123")

    def test_get_profile_retorna_rol_correcto(self):
        """Después del login, Session.user_role refleja el rol del perfil."""
        auth_repo = MagicMock()
        user = _fake_user(uid="u-3", email="emp@example.com")
        auth_repo.sign_in.return_value    = MagicMock(user=user)
        auth_repo.get_profile.return_value = MagicMock(
            data=[{"tenant_id": "t-3", "role": "employee"}]
        )

        svc, _, _ = _make_svc(auth_repo=auth_repo)
        svc.login("emp@example.com", "password123")

        assert Session.user_role == "employee"
