# tests/unit/test_product_service.py
#
# Unit tests para ProductService — pre-Fase 7.
# Sin BD, sin red, sin Session real. 100% unitarios.
#
# PATRÓN: idéntico a test_recharge_service.py
#   - MagicMock para repo
#   - patch("domain.services.product_service.Session")
#   - pytest con clases
#
# Total: 12 tests

import pytest
from unittest.mock import MagicMock, patch

from domain.services.product_service import ProductService
from domain.exceptions import AuthenticationError, RepositoryError


TENANT     = "tenant-xyz"
PRODUCT_ID = "prod-001"


def _make_svc(repo=None, barcode_svc=None):
    repo = repo or MagicMock()
    return ProductService(repo=repo, barcode_service=barcode_svc), repo


def _mock_session(tenant=TENANT):
    return patch("domain.services.product_service.Session", tenant_id=tenant)


# ── TestCreateProduct ──────────────────────────────────────────────────────────

class TestCreateProduct:

    def test_crea_producto_con_datos_validos(self):
        repo = MagicMock()
        repo.create.return_value = MagicMock(
            data=[{"id": PRODUCT_ID, "name": "Arroz", "price": 10.0}]
        )
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.create_product({"name": "Arroz", "price": 10.0, "cost": 5.0})

        repo.create.assert_called_once()
        assert result["id"] == PRODUCT_ID

    def test_barcode_pendiente_si_no_se_provee(self):
        """Sin barcode en data, repo.create es llamado igual — BD asignará PENDING-*."""
        repo = MagicMock()
        repo.create.return_value = MagicMock(
            data=[{"id": PRODUCT_ID, "name": "Arroz", "barcode": None}]
        )
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.create_product({"name": "Arroz", "price": 10.0, "cost": 5.0})

        repo.create.assert_called_once()
        assert result["id"] == PRODUCT_ID

    def test_barcode_custom_se_almacena(self):
        """Con barcode en data, el dict pasado al repo lo incluye."""
        repo = MagicMock()
        repo.create.return_value = MagicMock(
            data=[{"id": PRODUCT_ID, "barcode": "7501234567890"}]
        )
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            svc.create_product({
                "name": "Arroz", "price": 10.0, "cost": 5.0,
                "barcode": "7501234567890",
            })

        call_data = repo.create.call_args[0][0]
        assert call_data.get("barcode") == "7501234567890"

    def test_sin_tenant_lanza_auth_error(self):
        svc, _ = _make_svc()
        with _mock_session(tenant=None):
            with pytest.raises(AuthenticationError):
                svc.create_product({"name": "Arroz", "price": 10.0, "cost": 5.0})

    def test_nombre_duplicado_lanza_excepcion(self):
        """Si el repo lanza excepción (ej. constraint), se propaga."""
        repo = MagicMock()
        repo.create.side_effect = Exception("duplicate key violates unique constraint")
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            with pytest.raises(Exception):
                svc.create_product({"name": "Arroz", "price": 10.0, "cost": 5.0})


# ── TestUpdateProduct ──────────────────────────────────────────────────────────

class TestUpdateProduct:

    def test_update_precio_ok(self):
        repo = MagicMock()
        repo.update.return_value = MagicMock(
            data=[{"id": PRODUCT_ID, "name": "Arroz", "price": 20.0}]
        )
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.update_product(
                PRODUCT_ID, {"name": "Arroz", "price": 20.0, "cost": 8.0, "is_active": True}
            )

        repo.update.assert_called_once()
        assert result["price"] == 20.0

    def test_update_barcode_registra_historial(self):
        """assign_barcode actualiza el producto Y llama a add_barcode_history."""
        repo = MagicMock()
        repo.update.return_value = MagicMock(
            data=[{"id": PRODUCT_ID, "barcode": "7501234567890"}]
        )
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            svc.assign_barcode(PRODUCT_ID, "7501234567890")

        repo.add_barcode_history.assert_called_once()


# ── TestSearchProduct ──────────────────────────────────────────────────────────

class TestSearchProduct:

    def test_busqueda_por_nombre(self):
        repo = MagicMock()
        repo.search.return_value = MagicMock(data=[{"id": "p-1", "name": "Arroz"}])
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.search_products("Arroz")

        repo.search.assert_called_once_with(TENANT, "Arroz")
        assert len(result) == 1

    def test_busqueda_por_barcode(self):
        repo = MagicMock()
        repo.search.return_value = MagicMock(data=[{"id": "p-1", "barcode": "7501234567890"}])
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.search_products("7501234567890")

        repo.search.assert_called_once_with(TENANT, "7501234567890")
        assert len(result) == 1

    def test_sin_resultados_retorna_lista_vacia(self):
        repo = MagicMock()
        repo.search.return_value = MagicMock(data=None)
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.search_products("xyz_inexistente")

        assert result == []


# ── TestFindByBarcode ──────────────────────────────────────────────────────────

class TestFindByBarcode:

    def test_barcode_exacto_retorna_producto(self):
        producto = {"id": "p-1", "barcode": "7501234567890"}
        repo = MagicMock()
        repo.get_by_barcode.return_value = MagicMock(data=[producto])
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.find_by_barcode("7501234567890")

        assert result == producto

    def test_barcode_inexistente_retorna_none(self):
        repo = MagicMock()
        repo.get_by_barcode.return_value = MagicMock(data=[])
        svc, _ = _make_svc(repo=repo)

        with _mock_session():
            result = svc.find_by_barcode("0000000000000")

        assert result is None
