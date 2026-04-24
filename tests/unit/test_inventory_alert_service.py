# tests/unit/test_inventory_alert_service.py
#
# FASE 5 — Unit tests para InventoryAlertService
#
# COBERTURA:
#   TestGetAlerts             4   get_alerts, filtro status, aplanado de producto
#   TestCountNew              3   con alertas, vacío, excepción
#   TestAcknowledge           4   ok, idempotente, sin usuario, RPC vacía
#   TestResolve               4   ok, desde ignored falla, sin usuario, con notas
#   TestIgnore                2   ok, fallo silencioso
#   TestGenerateAlerts        3   retorno conteo, RPC vacía, excepción
#   TestGetSummary            4   crítico, warning, mixto, sin auth
#
# Total: 24 tests

import pytest
from unittest.mock import MagicMock, patch
from domain.services.inventory_alert_service import InventoryAlertService
from domain.exceptions import AuthenticationError, ValidationError


# ─── Fixtures ─────────────────────────────────────────────────────────────

TENANT  = "tenant-xyz"
ALERT_1 = "alert-001"
USER_1  = "user-001"


def _make_svc(repo=None):
    repo = repo or MagicMock()
    return InventoryAlertService(alert_repo=repo), repo


def _mock_session(tenant=TENANT, user_id=USER_1):
    return patch(
        "domain.services.inventory_alert_service.Session",
        tenant_id=tenant,
        current_user={"id": user_id} if user_id else None,
    )


def _rpc(data):
    m = MagicMock()
    m.data = data
    return m


def _alert(alert_id=ALERT_1, status="new", alert_type="low_stock",
           stock_actual=2, stock_minimo=10, product=None):
    return {
        "id":          alert_id,
        "status":      status,
        "alert_type":  alert_type,
        "stock_actual": stock_actual,
        "stock_minimo": stock_minimo,
        "products":    product or {"id": "p-1", "name": "Coca-Cola", "barcode": "200001"},
    }


# ─── TestGetAlerts ────────────────────────────────────────────────────────

class TestGetAlerts:

    def test_returns_list_with_product_name_at_root(self):
        svc, repo = _make_svc()
        repo.get_all.return_value = _rpc([_alert()])

        with _mock_session():
            result = svc.get_alerts()

        assert result[0]["product_name"] == "Coca-Cola"
        assert "products" not in result[0]

    def test_passes_status_filter_to_repo(self):
        svc, repo = _make_svc()
        repo.get_all.return_value = _rpc([])

        with _mock_session():
            svc.get_alerts(status="acknowledged")

        repo.get_all.assert_called_once_with(TENANT, status="acknowledged", limit=100)

    def test_raises_auth_error_without_session(self):
        svc, _ = _make_svc()

        with _mock_session(tenant=None): #type: ignore
            with pytest.raises(AuthenticationError):
                svc.get_alerts()

    def test_returns_empty_on_no_data(self):
        svc, repo = _make_svc()
        repo.get_all.return_value = _rpc(None)

        with _mock_session():
            result = svc.get_alerts()

        assert result == []


# ─── TestCountNew ─────────────────────────────────────────────────────────

class TestCountNew:

    def test_returns_count_from_repo(self):
        svc, repo = _make_svc()
        repo.count_new.return_value = 7

        with _mock_session():
            assert svc.count_new() == 7

    def test_returns_zero_when_no_alerts(self):
        svc, repo = _make_svc()
        repo.count_new.return_value = 0

        with _mock_session():
            assert svc.count_new() == 0

    def test_returns_zero_on_exception(self):
        svc, repo = _make_svc()
        repo.count_new.side_effect = Exception("BD error")

        with _mock_session():
            # No debe lanzar
            assert svc.count_new() == 0


# ─── TestAcknowledge ──────────────────────────────────────────────────────

class TestAcknowledge:

    def test_calls_repo_with_correct_ids(self):
        svc, repo = _make_svc()
        updated = _alert(status="acknowledged")
        repo.acknowledge.return_value = _rpc([updated])

        with _mock_session():
            result = svc.acknowledge(ALERT_1)

        repo.acknowledge.assert_called_once_with(ALERT_1, USER_1)
        assert result["status"] == "acknowledged"

    def test_idempotent_returns_empty_dict_when_already_processed(self):
        """RPC retorna lista vacía si la alerta ya no está en 'new'."""
        svc, repo = _make_svc()
        repo.acknowledge.return_value = _rpc([])

        with _mock_session():
            result = svc.acknowledge(ALERT_1)

        assert result == {}

    def test_raises_auth_error_without_user(self):
        svc, _ = _make_svc()

        with _mock_session(user_id=None): #type: ignore
            with pytest.raises(AuthenticationError):
                svc.acknowledge(ALERT_1)

    def test_raises_auth_error_when_current_user_is_none(self):
        """Session.current_user puede ser None incluso con tenant_id."""
        svc, _ = _make_svc()

        with patch("domain.services.inventory_alert_service.Session",
                   tenant_id=TENANT, current_user=None):
            with pytest.raises(AuthenticationError):
                svc.acknowledge(ALERT_1)


# ─── TestResolve ──────────────────────────────────────────────────────────

class TestResolve:

    def test_resolves_alert_with_notes(self):
        svc, repo = _make_svc()
        updated = _alert(status="resolved")
        repo.resolve.return_value = _rpc([updated])

        with _mock_session():
            result = svc.resolve(ALERT_1, notes="Restock realizado")

        repo.resolve.assert_called_once_with(ALERT_1, USER_1, "Restock realizado")
        assert result["status"] == "resolved"

    def test_raises_validation_error_when_rpc_returns_empty(self):
        """La RPC retorna [] si la alerta estaba en 'ignored'."""
        svc, repo = _make_svc()
        repo.resolve.return_value = _rpc([])

        with _mock_session():
            with pytest.raises(ValidationError):
                svc.resolve(ALERT_1)

    def test_raises_auth_error_without_user(self):
        svc, _ = _make_svc()

        with _mock_session(user_id=None): #type: ignore
            with pytest.raises(AuthenticationError):
                svc.resolve(ALERT_1)

    def test_resolve_without_notes_passes_none(self):
        svc, repo = _make_svc()
        repo.resolve.return_value = _rpc([_alert(status="resolved")])

        with _mock_session():
            svc.resolve(ALERT_1)

        repo.resolve.assert_called_once_with(ALERT_1, USER_1, None)


# ─── TestIgnore ───────────────────────────────────────────────────────────

class TestIgnore:

    def test_ignore_returns_true_on_success(self):
        svc, repo = _make_svc()
        repo.ignore.return_value = _rpc([{"id": ALERT_1, "status": "ignored"}])

        result = svc.ignore(ALERT_1)

        assert result is True
        repo.ignore.assert_called_once_with(ALERT_1)

    def test_ignore_returns_false_on_exception(self):
        svc, repo = _make_svc()
        repo.ignore.side_effect = Exception("BD error")

        result = svc.ignore(ALERT_1)

        # No debe lanzar — falla silenciosamente
        assert result is False


# ─── TestGenerateAlerts ───────────────────────────────────────────────────

class TestGenerateAlerts:

    def test_returns_count_from_rpc(self):
        svc, repo = _make_svc()
        repo.generate_for_tenant.return_value = _rpc(
            [{"alerts_generated": 5}]
        )

        result = svc.generate_alerts()

        assert result == 5

    def test_returns_zero_when_rpc_returns_empty(self):
        svc, repo = _make_svc()
        repo.generate_for_tenant.return_value = _rpc([])

        result = svc.generate_alerts()

        assert result == 0

    def test_returns_zero_on_exception(self):
        svc, repo = _make_svc()
        repo.generate_for_tenant.side_effect = Exception("RPC error")

        result = svc.generate_alerts()

        assert result == 0


# ─── TestGetSummary ───────────────────────────────────────────────────────

class TestGetSummary:

    def test_counts_critical_and_warning_correctly(self):
        svc, repo = _make_svc()
        repo.get_all.return_value = _rpc([
            _alert(alert_type="out_of_stock"),
            _alert(alert_type="out_of_stock"),
            _alert(alert_type="low_stock"),
        ])

        with _mock_session():
            summary = svc.get_summary()

        assert summary["total_new"] == 3
        assert summary["critical"]  == 2
        assert summary["warning"]   == 1

    def test_top_critical_limited_to_3(self):
        svc, repo = _make_svc()
        alerts = [_alert(alert_type="out_of_stock") for _ in range(5)]
        repo.get_all.return_value = _rpc(alerts)

        with _mock_session():
            summary = svc.get_summary()

        assert len(summary["top_critical"]) == 3

    def test_returns_zeros_on_exception(self):
        svc, repo = _make_svc()
        repo.get_all.side_effect = Exception("error")

        with _mock_session():
            summary = svc.get_summary()

        assert summary == {"total_new": 0, "critical": 0,
                           "warning": 0, "top_critical": []}

    def test_empty_alerts_returns_all_zeros(self):
        svc, repo = _make_svc()
        repo.get_all.return_value = _rpc([])

        with _mock_session():
            summary = svc.get_summary()

        assert summary["total_new"] == 0
        assert summary["top_critical"] == []