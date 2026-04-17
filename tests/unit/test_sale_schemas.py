import pytest
from domain.schemas.sale_schemas import CreateSaleRequest, SaleItemRequest
from domain.exceptions import ValidationError, EmptyCartError, InsufficientPaymentError


def _item(quantity=2, unit_price=10.0):
    return SaleItemRequest(
        product_id="p-1",
        product_name="Test",
        quantity=quantity,
        unit_price=unit_price,
    )


class TestSaleItemRequest:
    def test_valid(self):
        _item().validate()

    def test_zero_quantity_raises(self):
        with pytest.raises(ValidationError) as exc:
            _item(quantity=0).validate()
        assert exc.value.field == "quantity"

    def test_negative_quantity_raises(self):
        with pytest.raises(ValidationError):
            _item(quantity=-1).validate()

    def test_zero_price_raises(self):
        with pytest.raises(ValidationError) as exc:
            _item(unit_price=0).validate()
        assert exc.value.field == "unit_price"

    def test_subtotal(self):
        assert _item(quantity=3, unit_price=10.0).subtotal == 30.0


class TestCreateSaleRequest:
    def _make(self, items=None, method="cash", received=100.0):
        return CreateSaleRequest(
            items=items or [_item()],
            payment_method=method,
            amount_received=received,
        )

    def test_valid_cash(self):
        self._make().validate()

    def test_valid_card(self):
        self._make(method="card", received=0).validate()

    def test_empty_cart_raises(self):
        with pytest.raises(EmptyCartError):
            self._make(items=[]).validate()

    def test_invalid_payment_method_raises(self):
        with pytest.raises(ValidationError) as exc:
            self._make(method="bitcoin").validate()
        assert exc.value.field == "payment_method"

    def test_insufficient_cash_raises(self):
        with pytest.raises(InsufficientPaymentError):
            self._make(method="cash", received=1.0).validate()

    def test_total(self):
        items = [_item(quantity=2, unit_price=10.0), _item(quantity=1, unit_price=5.0)]
        req = self._make(items=items)
        assert req.total == 25.0

    def test_from_cart(self):
        cart = [{"id": "p-1", "name": "Prod", "quantity": 2, "price": 15.0}]
        req = CreateSaleRequest.from_cart(cart, "card", 0)
        assert len(req.items) == 1
        assert req.total == 30.0
