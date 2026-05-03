# tests/unit/test_sale_repo_mock.py
#
# Verifica que SaleRepository acepta un client inyectado
# y lo usa correctamente — sin tocar Supabase real.
#
# Tests: 2

from unittest.mock import MagicMock
from infrastructure.repositories.sale_repository import SaleRepository


class TestSaleRepositoryInjection:

    def test_acepta_client_mock_en_create_sale(self):
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = \
            MagicMock(data=[{"id": "sale-1", "total": 100}])

        repo   = SaleRepository(client=mock_client)
        result = repo.create_sale({"tenant_id": "t-1", "total": 100, "status": "completed"})

        mock_client.table.assert_called_with("sales")
        assert result.data[0]["id"] == "sale-1"

    def test_acepta_client_mock_en_get_all(self):
        mock_client = MagicMock()
        mock_client.table.return_value \
            .select.return_value \
            .eq.return_value \
            .order.return_value \
            .limit.return_value \
            .execute.return_value = MagicMock(data=[{"id": "sale-2"}])

        repo   = SaleRepository(client=mock_client)
        result = repo.get_all("t-1")

        mock_client.table.assert_called_with("sales")
        assert result.data[0]["id"] == "sale-2"
