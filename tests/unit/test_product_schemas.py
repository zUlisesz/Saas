import pytest
from domain.schemas.product_schemas import CreateProductRequest, UpdateProductRequest
from domain.exceptions import ValidationError


class TestCreateProductRequest:
    def _make(self, **kwargs):
        defaults = {"name": "Coca-Cola", "price": 20.0, "cost": 10.0}
        return CreateProductRequest(**{**defaults, **kwargs})

    def test_valid(self):
        self._make().validate()

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError) as exc:
            self._make(name="").validate()
        assert exc.value.field == "name"

    def test_whitespace_name_raises(self):
        with pytest.raises(ValidationError):
            self._make(name="   ").validate()

    def test_zero_price_raises(self):
        with pytest.raises(ValidationError) as exc:
            self._make(price=0).validate()
        assert exc.value.field == "price"

    def test_negative_price_raises(self):
        with pytest.raises(ValidationError):
            self._make(price=-5).validate()

    def test_negative_cost_raises(self):
        with pytest.raises(ValidationError) as exc:
            self._make(cost=-1).validate()
        assert exc.value.field == "cost"

    def test_to_db_dict_strips_name(self):
        req = self._make(name="  Cola  ")
        d = req.to_db_dict("tenant-1")
        assert d["name"] == "Cola"
        assert d["tenant_id"] == "tenant-1"

    def test_to_db_dict_empty_barcode_becomes_none(self):
        req = self._make(barcode="   ")
        d = req.to_db_dict("t")
        assert d["barcode"] is None

    def test_to_db_dict_none_category_stays_none(self):
        req = self._make(category_id=None)
        d = req.to_db_dict("t")
        assert d["category_id"] is None


class TestUpdateProductRequest:
    def test_empty_update_is_valid(self):
        UpdateProductRequest().validate()

    def test_whitespace_name_raises(self):
        with pytest.raises(ValidationError):
            UpdateProductRequest(name="   ").validate()

    def test_zero_price_raises(self):
        with pytest.raises(ValidationError):
            UpdateProductRequest(price=0.0).validate()

    def test_negative_cost_raises(self):
        with pytest.raises(ValidationError):
            UpdateProductRequest(cost=-10).validate()

    def test_to_db_dict_only_includes_set_fields(self):
        req = UpdateProductRequest(price=99.9)
        d = req.to_db_dict()
        assert "price" in d
        assert "name" not in d
        assert "cost" not in d

    def test_to_db_dict_strips_name(self):
        req = UpdateProductRequest(name="  Pepsi  ")
        d = req.to_db_dict()
        assert d["name"] == "Pepsi"
