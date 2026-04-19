from domain.specifications.barcode_specs import (
    BarcodeNotEmpty, BarcodeNotPending, BarcodeValidType, BarcodeScanReady,
)


def _p(barcode=None, barcode_type=None):
    return {"barcode": barcode, "barcode_type": barcode_type}


class TestBarcodeNotPending:
    def test_real_barcode_satisfied(self):
        assert BarcodeNotPending().is_satisfied_by(_p("2001234567890"))

    def test_pending_not_satisfied(self):
        assert not BarcodeNotPending().is_satisfied_by(_p("PENDING-abc"))

    def test_empty_satisfied(self):
        assert BarcodeNotPending().is_satisfied_by(_p(""))


class TestBarcodeNotEmpty:
    def test_with_value_satisfied(self):
        assert BarcodeNotEmpty().is_satisfied_by(_p("1234567890123"))

    def test_none_not_satisfied(self):
        assert not BarcodeNotEmpty().is_satisfied_by(_p(None))

    def test_whitespace_not_satisfied(self):
        assert not BarcodeNotEmpty().is_satisfied_by(_p("   "))


class TestBarcodeValidType:
    def test_ean13_satisfied(self):
        assert BarcodeValidType().is_satisfied_by(_p(barcode_type="ean13"))

    def test_none_type_not_satisfied(self):
        assert not BarcodeValidType().is_satisfied_by(_p(barcode_type=None))

    def test_invalid_type_not_satisfied(self):
        assert not BarcodeValidType().is_satisfied_by(_p(barcode_type="barcode99"))


class TestBarcodeScanReady:
    def test_ready_product(self):
        spec = BarcodeScanReady()
        assert spec.is_satisfied_by(_p("2001234567890", "ean13"))

    def test_pending_not_ready(self):
        spec = BarcodeScanReady()
        assert not spec.is_satisfied_by(_p("PENDING-abc", "ean13"))

    def test_composable_with_and(self):
        # Ensure specs can be composed further
        combined = BarcodeNotEmpty().and_(BarcodeNotPending())
        assert combined.is_satisfied_by(_p("2001234567890"))
        assert not combined.is_satisfied_by(_p("PENDING-x"))
