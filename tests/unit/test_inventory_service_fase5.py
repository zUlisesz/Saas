# tests/unit/test_inventory_service.py
#
# FASE 5 — Unit tests para InventoryService
#
# PATRÓN SEGUIDO:
#   Idéntico al resto de tests del proyecto:
#   - pytest con clases
#   - MagicMock para repos y servicios
#   - patch("...Session") para controlar el estado de sesión
#   - Sin BD, sin red — 100% unitarios
#
# COBERTURA:
#   TestListInventory         4   list_inventory, estado vacío, sin auth
#   TestGetLowStock           4   get_low_stock_alerts, severity, has_low_stock
#   TestClassifyInventory     4   ok/low/out_of_stock/overstock
#   TestThresholds            5   get, get_defaults, update, validaciones
#   TestAdjustStock           5   ajuste normal, bajada, negativo, sin registro
#   TestConsumeStock          5   consume normal, bajo mínimo, sin registro
#   TestInitStock             2   init nuevo, kardex de inicio
#   TestGetAlertCount         2   con alertas, sin alertas
#
# Total: 31 tests

import pytest
from unittest.mock import MagicMock, patch, call
from domain.services.inventory_service import InventoryService
from domain.exceptions import AuthenticationError, ValidationError


# ─── Fixtures ─────────────────────────────────────────────────────────────

TENANT = "tenant-abc"
PRODUCT = "product-123"

def _make_service(repo=None, event_service=None):
    repo = repo or MagicMock()
    return InventoryService(inventory_repo=repo, event_service=event_service), repo

def _mock_session(tenant=TENANT):
    """Context manager: parchea Session.tenant_id."""
    return patch("domain.services.inventory_service.Session",
                 tenant_id=tenant, current_user={"id": "user-1"})

def _repo_stock(stock_actual=10, stock_minimo=5):
    """Helper: construye el objeto de retorno que simula repo.get_stock()."""
    mock = MagicMock()
    mock.data = [{"stock_actual": stock_actual, "stock_minimo": stock_minimo}]
    return mock

def _rpc_result(data: list):
    mock = MagicMock()
    mock.data = data
    return mock


# ─── TestListInventory ────────────────────────────────────────────────────

class TestListInventory:

    def test_returns_data_from_rpc(self):
        svc, repo = _make_service()
        expected = [{"product_id": "p1", "product_name": "Coca", "stock_status": "ok"}]
        repo.get_all_with_alerts.return_value = _rpc_result(expected)

        with _mock_session():
            result = svc.list_inventory()

        assert result == expected
        repo.get_all_with_alerts.assert_called_once_with(TENANT)

    def test_returns_empty_list_when_no_data(self):
        svc, repo = _make_service()
        repo.get_all_with_alerts.return_value = _rpc_result([])

        with _mock_session():
            result = svc.list_inventory()

        assert result == []

    def test_raises_auth_error_without_session(self):
        svc, _ = _make_service()

        with _mock_session(tenant=None): #type: ignore
            with pytest.raises(AuthenticationError):
                svc.list_inventory()

    def test_returns_empty_on_none_data(self):
        """repo.data puede ser None si la RPC no retorna nada."""
        svc, repo = _make_service()
        mock = MagicMock()
        mock.data = None
        repo.get_all_with_alerts.return_value = mock

        with _mock_session():
            result = svc.list_inventory()

        assert result == []


# ─── TestGetLowStock ──────────────────────────────────────────────────────

class TestGetLowStock:

    def test_adds_severity_critical_for_out_of_stock(self):
        svc, repo = _make_service()
        repo.get_low_stock_report.return_value = _rpc_result([
            {"product_name": "A", "stock_status": "out_of_stock", "stock_actual": 0}
        ])

        with _mock_session():
            result = svc.get_low_stock_alerts()

        assert result[0]["severity"] == "critical"

    def test_adds_severity_warning_for_low(self):
        svc, repo = _make_service()
        repo.get_low_stock_report.return_value = _rpc_result([
            {"product_name": "B", "stock_status": "low", "stock_actual": 3}
        ])

        with _mock_session():
            result = svc.get_low_stock_alerts()

        assert result[0]["severity"] == "warning"

    def test_has_low_stock_true_when_alerts_exist(self):
        svc, repo = _make_service()
        repo.get_low_stock_report.return_value = _rpc_result([
            {"stock_status": "low", "stock_actual": 1}
        ])

        with _mock_session():
            assert svc.has_low_stock() is True

    def test_has_low_stock_false_returns_false_on_exception(self):
        svc, repo = _make_service()
        repo.get_low_stock_report.side_effect = Exception("BD down")

        with _mock_session():
            # No debe lanzar — retorna False
            assert svc.has_low_stock() is False


# ─── TestClassifyInventory ────────────────────────────────────────────────

class TestClassifyInventory:

    def _make_items(self):
        return [
            {"stock_status": "ok"},
            {"stock_status": "low"},
            {"stock_status": "out_of_stock"},
            {"stock_status": "overstock"},
        ]

    def test_groups_into_correct_buckets(self):
        svc, _ = _make_service()
        result = svc.classify_inventory(self._make_items())
        assert len(result["ok"])       == 1
        assert len(result["warning"])  == 1
        assert len(result["critical"]) == 1
        assert len(result["overstock"])== 1

    def test_empty_list_returns_empty_buckets(self):
        svc, _ = _make_service()
        result = svc.classify_inventory([])
        assert all(len(v) == 0 for v in result.values())

    def test_unknown_status_goes_to_ok(self):
        svc, _ = _make_service()
        result = svc.classify_inventory([{"stock_status": "unknown"}])
        assert len(result["ok"]) == 1

    def test_multiple_items_same_status(self):
        svc, _ = _make_service()
        items = [{"stock_status": "low"}] * 5
        result = svc.classify_inventory(items)
        assert len(result["warning"]) == 5


# ─── TestThresholds ───────────────────────────────────────────────────────

class TestThresholds:

    def test_get_thresholds_delegates_to_repo(self):
        svc, repo = _make_service()
        expected = [{"product_id": PRODUCT, "stock_minimo": 5}]
        repo.get_thresholds.return_value = _rpc_result(expected)

        with _mock_session():
            result = svc.get_thresholds()

        assert result == expected
        repo.get_thresholds.assert_called_once_with(TENANT)

    def test_get_threshold_returns_defaults_when_not_found(self):
        svc, repo = _make_service()
        repo.get_threshold_by_product.return_value = _rpc_result([])

        with _mock_session():
            result = svc.get_threshold_for_product(PRODUCT)

        assert result["stock_minimo"] == 5
        assert result["stock_maximo"] == 100

    def test_update_threshold_calls_upsert_with_correct_data(self):
        svc, repo = _make_service()
        repo.upsert_threshold.return_value = _rpc_result([{"id": "th-1"}])

        with _mock_session():
            svc.update_threshold(PRODUCT, 10, 200, 20, 50, True, False)

        call_data = repo.upsert_threshold.call_args[0][0]
        assert call_data["tenant_id"]    == TENANT
        assert call_data["product_id"]   == PRODUCT
        assert call_data["stock_minimo"] == 10
        assert call_data["stock_maximo"] == 200

    def test_update_threshold_raises_when_max_lte_min(self):
        svc, _ = _make_service()

        with _mock_session():
            with pytest.raises(ValidationError) as exc:
                svc.update_threshold(PRODUCT, 50, 50)
            assert "stock_maximo" in exc.value.field

    def test_update_threshold_raises_when_reorder_below_min(self):
        svc, _ = _make_service()

        with _mock_session():
            with pytest.raises(ValidationError) as exc:
                svc.update_threshold(PRODUCT, 10, 100, reorder_point=5)
            assert "reorder_point" in exc.value.field


# ─── TestAdjustStock ─────────────────────────────────────────────────────

class TestAdjustStock:

    def test_normal_adjustment_updates_repo_and_kardex(self):
        svc, repo = _make_service()
        repo.get_stock.return_value = _repo_stock(stock_actual=20)
        repo.upsert.return_value = MagicMock()
        repo.add_kardex_entry.return_value = None

        with _mock_session():
            result = svc.adjust_stock(PRODUCT, 30)

        assert result["stock_anterior"]  == 20
        assert result["stock_posterior"] == 30
        repo.upsert.assert_called_once()
        repo.add_kardex_entry.assert_called_once()

    def test_adjustment_down_records_negative_delta(self):
        svc, repo = _make_service()
        repo.get_stock.return_value = _repo_stock(stock_actual=50)

        with _mock_session():
            result = svc.adjust_stock(PRODUCT, 10)

        entry = repo.add_kardex_entry.call_args[0][0]
        assert entry["saldo_anterior"]  == 50
        assert entry["saldo_posterior"] == 10
        assert entry["tipo"]            == "ajuste"

    def test_negative_stock_raises_validation_error(self):
        svc, repo = _make_service()
        repo.get_stock.return_value = _repo_stock()

        with _mock_session():
            with pytest.raises(ValidationError):
                svc.adjust_stock(PRODUCT, -1)

    def test_init_called_when_no_inventory_record(self):
        """Si no hay fila en inventory, init_stock() crea una."""
        svc, repo = _make_service()
        no_data = MagicMock()
        no_data.data = []
        repo.get_stock.return_value = no_data

        with _mock_session():
            result = svc.adjust_stock(PRODUCT, 15)

        assert result["stock_anterior"]  == 0
        assert result["stock_posterior"] == 15

    def test_emits_low_stock_event_when_below_minimum(self):
        event_svc = MagicMock()
        svc, repo = _make_service(event_service=event_svc)
        # stock_minimo = 10, nuevo_stock = 5 → bajo mínimo → emite evento
        repo.get_stock.return_value = _repo_stock(stock_actual=20, stock_minimo=10)

        with _mock_session():
            svc.adjust_stock(PRODUCT, 5)

        event_svc.emit.assert_called_once()
        args = event_svc.emit.call_args[0]
        assert args[0] == "low_stock"


# ─── TestConsumeStock ─────────────────────────────────────────────────────

class TestConsumeStock:

    def test_decrements_stock_and_records_kardex(self):
        svc, repo = _make_service()
        repo.get_stock.return_value = _repo_stock(stock_actual=20)

        with _mock_session():
            svc.consume_stock(PRODUCT, 3, sale_id="sale-1")

        entry = repo.add_kardex_entry.call_args[0][0]
        assert entry["tipo"]            == "salida"
        assert entry["cantidad"]        == 3
        assert entry["saldo_anterior"]  == 20
        assert entry["saldo_posterior"] == 17
        assert entry["referencia_id"]   == "sale-1"

    def test_stock_never_goes_below_zero(self):
        svc, repo = _make_service()
        repo.get_stock.return_value = _repo_stock(stock_actual=2)

        with _mock_session():
            svc.consume_stock(PRODUCT, 10)

        call_args = repo.upsert.call_args[0]
        assert call_args[1] == 0  # max(0, 2 - 10) = 0

    def test_no_op_when_product_not_in_inventory(self):
        svc, repo = _make_service()
        no_data = MagicMock()
        no_data.data = []
        repo.get_stock.return_value = no_data

        with _mock_session():
            svc.consume_stock(PRODUCT, 5)  # No debe lanzar

        repo.upsert.assert_not_called()
        repo.add_kardex_entry.assert_not_called()

    def test_emits_low_stock_event_after_consume(self):
        event_svc = MagicMock()
        svc, repo = _make_service(event_service=event_svc)
        # stock 3, minimo 5 → quedará en 0, bajo mínimo
        repo.get_stock.return_value = _repo_stock(stock_actual=3, stock_minimo=5)

        with _mock_session():
            svc.consume_stock(PRODUCT, 3)

        event_svc.emit.assert_called_once()

    def test_uses_tenant_id_param_over_session(self):
        """consume_stock acepta tenant_id explícito — útil en contextos sin sesión."""
        svc, repo = _make_service()
        repo.get_stock.return_value = _repo_stock()

        svc.consume_stock(PRODUCT, 1, tenant_id="explicit-tenant")

        entry = repo.add_kardex_entry.call_args[0][0]
        assert entry["tenant_id"] == "explicit-tenant"


# ─── TestInitStock ────────────────────────────────────────────────────────

class TestInitStock:

    def test_creates_inventory_and_kardex_entry(self):
        svc, repo = _make_service()

        with _mock_session():
            svc.init_stock(PRODUCT, stock_inicial=10, stock_minimo=3)

        repo.upsert.assert_called_once_with(PRODUCT, 10, 3)
        entry = repo.add_kardex_entry.call_args[0][0]
        assert entry["tipo"]            == "inicio"
        assert entry["saldo_posterior"] == 10

    def test_defaults_to_zero_stock(self):
        svc, repo = _make_service()

        with _mock_session():
            svc.init_stock(PRODUCT)

        call_args = repo.upsert.call_args[0]
        assert call_args[1] == 0  # stock_inicial default


# ─── TestGetAlertCount ────────────────────────────────────────────────────

class TestGetAlertCount:

    def test_returns_count_from_rpc(self):
        svc, repo = _make_service()
        data = [{"product_id": "p1"}, {"product_id": "p2"}]
        repo.get_low_stock_report.return_value = _rpc_result(data)

        with _mock_session():
            count = svc.get_alert_count()

        assert count == 2

    def test_returns_zero_on_exception(self):
        svc, repo = _make_service()
        repo.get_low_stock_report.side_effect = Exception("error")

        with _mock_session(tenant=None): #type: ignore
            count = svc.get_alert_count()

        assert count == 0