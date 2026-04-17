import pytest
from domain.specifications.low_stock_spec import LowStockSpec, OutOfStockSpec, HealthyStockSpec


def _item(stock_actual, stock_minimo=5):
    return {"stock_actual": stock_actual, "stock_minimo": stock_minimo}


class TestLowStockSpec:
    def test_at_minimum_is_satisfied(self):
        assert LowStockSpec().is_satisfied_by(_item(5, 5))

    def test_below_minimum_is_satisfied(self):
        assert LowStockSpec().is_satisfied_by(_item(2, 5))

    def test_above_minimum_not_satisfied(self):
        assert not LowStockSpec().is_satisfied_by(_item(6, 5))

    def test_factor_2(self):
        spec = LowStockSpec(threshold_factor=2.0)
        assert spec.is_satisfied_by(_item(9, 5))
        assert not spec.is_satisfied_by(_item(11, 5))


class TestOutOfStockSpec:
    def test_zero_stock_satisfied(self):
        assert OutOfStockSpec().is_satisfied_by(_item(0))

    def test_positive_stock_not_satisfied(self):
        assert not OutOfStockSpec().is_satisfied_by(_item(1))


class TestHealthyStockSpec:
    def test_well_above_minimum_satisfied(self):
        assert HealthyStockSpec().is_satisfied_by(_item(11, 5))

    def test_exactly_twice_not_satisfied(self):
        assert not HealthyStockSpec().is_satisfied_by(_item(10, 5))

    def test_low_stock_not_satisfied(self):
        assert not HealthyStockSpec().is_satisfied_by(_item(3, 5))


class TestComposedSpecs:
    def test_and_composition(self):
        low = LowStockSpec()
        out = OutOfStockSpec()
        low_not_zero = low.and_(out.not_())
        assert low_not_zero.is_satisfied_by(_item(3, 5))
        assert not low_not_zero.is_satisfied_by(_item(0, 5))

    def test_or_composition(self):
        low = LowStockSpec()
        out = OutOfStockSpec()
        alert = low.or_(out)
        assert alert.is_satisfied_by(_item(0))
        assert alert.is_satisfied_by(_item(4, 5))
        assert not alert.is_satisfied_by(_item(10, 5))

    def test_filter(self):
        items = [_item(0), _item(3, 5), _item(10, 5)]
        result = OutOfStockSpec().filter(items)
        assert len(result) == 1
        assert result[0]["stock_actual"] == 0

    def test_count(self):
        items = [_item(0), _item(2, 5), _item(10, 5)]
        assert LowStockSpec().count(items) == 2
