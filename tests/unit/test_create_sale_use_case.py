import pytest
from unittest.mock import MagicMock, patch
from application.use_cases.create_sale_use_case import CreateSaleUseCase
from domain.schemas.sale_schemas import CreateSaleRequest, SaleItemRequest
from domain.exceptions import AuthenticationError, RepositoryError


def _make_request(method="cash", received=100.0):
    return CreateSaleRequest(
        items=[SaleItemRequest("p-1", "Producto", 2, 10.0)],
        payment_method=method,
        amount_received=received,
    )


def _mock_session(tenant="t-1", user_id="u-1"):
    user = MagicMock()
    user.id = user_id
    return tenant, user


@pytest.fixture
def sale_repo():
    repo = MagicMock()
    repo.create_sale.return_value = MagicMock(data=[{"id": "sale-1"}])
    repo.create_sale_items.return_value = MagicMock()
    repo.create_payment.return_value = MagicMock()
    return repo


@pytest.fixture
def use_case(sale_repo):
    return CreateSaleUseCase(sale_repo=sale_repo)


class TestCreateSaleUseCase:
    def test_raises_auth_error_without_session(self, use_case):
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = None
            mock_sess.current_user = None
            with pytest.raises(AuthenticationError):
                use_case.execute(_make_request())

    def test_successful_cash_sale(self, use_case, sale_repo):
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            result = use_case.execute(_make_request())
        assert result["total"] == 20.0
        assert result["change"] == 80.0
        sale_repo.create_sale.assert_called_once()
        sale_repo.create_sale_items.assert_called_once()
        sale_repo.create_payment.assert_called_once()

    def test_card_sale_change_is_zero(self, use_case):
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            result = use_case.execute(_make_request(method="card", received=0))
        assert result["change"] == 0

    def test_cleanup_on_items_failure(self, sale_repo):
        sale_repo.create_sale_items.side_effect = Exception("DB error")
        uc = CreateSaleUseCase(sale_repo=sale_repo)
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            with pytest.raises(RepositoryError):
                uc.execute(_make_request())
        sale_repo.delete_sale.assert_called_once_with("sale-1")

    def test_cleanup_on_payment_failure(self, sale_repo):
        sale_repo.create_payment.side_effect = Exception("payment error")
        uc = CreateSaleUseCase(sale_repo=sale_repo)
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            with pytest.raises(RepositoryError):
                uc.execute(_make_request())
        sale_repo.delete_sale.assert_called_once_with("sale-1")

    def test_inventory_failure_does_not_raise(self, sale_repo):
        inv = MagicMock()
        inv.consume_stock.side_effect = Exception("inv error")
        uc = CreateSaleUseCase(sale_repo=sale_repo, inventory_service=inv)
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            result = uc.execute(_make_request())
        assert result["total"] == 20.0

    def test_event_failure_does_not_raise(self, sale_repo):
        ev = MagicMock()
        ev.emit.side_effect = Exception("event error")
        uc = CreateSaleUseCase(sale_repo=sale_repo, event_service=ev)
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            result = uc.execute(_make_request())
        assert result["total"] == 20.0

    def test_result_items_format(self, use_case):
        with patch("application.use_cases.create_sale_use_case.Session") as mock_sess:
            mock_sess.tenant_id = "t-1"
            mock_sess.current_user = MagicMock(id="u-1")
            result = use_case.execute(_make_request())
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["id"] == "p-1"
        assert item["quantity"] == 2
        assert item["price"] == 10.0
