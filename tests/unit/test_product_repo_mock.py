# tests/unit/test_product_repo_mock.py
#
# Verifica que ProductRepository acepta un client inyectado
# y lo usa correctamente — sin tocar Supabase real.
#
# Tests: 2

from unittest.mock import MagicMock
from infrastructure.repositories.product_repository import ProductRepository


class TestProductRepositoryInjection:

    def test_acepta_client_mock_en_create(self):
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = \
            MagicMock(data=[{"id": "prod-1", "name": "Arroz", "price": 10.0}])

        repo   = ProductRepository(client=mock_client)
        result = repo.create({"tenant_id": "t-1", "name": "Arroz", "price": 10.0})

        mock_client.table.assert_called_with("products")
        assert result.data[0]["id"] == "prod-1"

    def test_acepta_client_mock_en_get_all(self):
        mock_client = MagicMock()
        mock_client.table.return_value \
            .select.return_value \
            .eq.return_value \
            .eq.return_value \
            .order.return_value \
            .execute.return_value = MagicMock(data=[{"id": "prod-2"}])

        repo   = ProductRepository(client=mock_client)
        result = repo.get_all("t-1")

        mock_client.table.assert_called_with("products")
        assert result.data is not None
