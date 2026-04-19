import pytest
from domain.services.barcode_service import BarcodeService

svc = BarcodeService()
SEED = "550e8400-e29b-41d4-a716-446655440000"


class TestEAN13Generation:
    def test_length_is_13(self):
        assert len(svc.generate_ean13(SEED)) == 13

    def test_all_digits(self):
        assert svc.generate_ean13(SEED).isdigit()

    def test_default_prefix(self):
        assert svc.generate_ean13(SEED).startswith("200")

    def test_custom_prefix(self):
        assert svc.generate_ean13(SEED, prefix="777").startswith("777")

    def test_checksum_valid(self):
        code = svc.generate_ean13(SEED)
        ok, _ = svc.validate(code, "ean13")
        assert ok

    def test_deterministic(self):
        assert svc.generate_ean13(SEED) == svc.generate_ean13(SEED)


class TestEAN8Generation:
    def test_length_is_8(self):
        assert len(svc.generate_ean8(SEED)) == 8

    def test_checksum_valid(self):
        code = svc.generate_ean8(SEED)
        ok, _ = svc.validate(code, "ean8")
        assert ok


class TestCode128Generation:
    def test_format(self):
        code = svc.generate_code128(SEED)
        assert code.startswith("NXP-")

    def test_length(self):
        code = svc.generate_code128(SEED)
        assert len(code) == 12  # NXP- (4) + 8 hex chars


class TestGenerateForType:
    def test_ean13(self):
        code = svc.generate_for_type(SEED, "ean13")
        assert len(code) == 13

    def test_ean8(self):
        code = svc.generate_for_type(SEED, "ean8")
        assert len(code) == 8

    def test_upc(self):
        code = svc.generate_for_type(SEED, "upc")
        assert code.startswith("NXP-")

    def test_code128(self):
        code = svc.generate_for_type(SEED, "code128")
        assert code.startswith("NXP-")

    def test_qr(self):
        code = svc.generate_for_type(SEED, "qr")
        assert code.startswith("NXP-")

    def test_case_insensitive(self):
        assert svc.generate_for_type(SEED, "EAN13") == svc.generate_for_type(SEED, "ean13")

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            svc.generate_for_type(SEED, "barcode99")


class TestValidation:
    def test_valid_ean13(self):
        code = svc.generate_ean13(SEED)
        ok, err = svc.validate(code, "ean13")
        assert ok
        assert err == ""

    def test_invalid_ean13_length(self):
        ok, err = svc.validate("123456", "ean13")
        assert not ok

    def test_invalid_ean13_checksum(self):
        code = svc.generate_ean13(SEED)
        bad  = code[:-1] + str((int(code[-1]) + 1) % 10)
        ok, _ = svc.validate(bad, "ean13")
        assert not ok

    def test_valid_ean8(self):
        code = svc.generate_ean8(SEED)
        ok, _ = svc.validate(code, "ean8")
        assert ok

    def test_invalid_ean8_length(self):
        ok, _ = svc.validate("1234", "ean8")
        assert not ok

    def test_empty_barcode(self):
        ok, err = svc.validate("", "ean13")
        assert not ok
        assert "vacío" in err

    def test_whitespace_barcode(self):
        ok, _ = svc.validate("   ", "ean13")
        assert not ok

    def test_non_digit_ean13(self):
        ok, _ = svc.validate("20012345678AB", "ean13")
        assert not ok

    def test_code128_min_length(self):
        ok, _ = svc.validate("NXP-ABCD1234", "code128")
        assert ok

    def test_code128_too_short(self):
        ok, _ = svc.validate("NX", "code128")
        assert not ok

    def test_unknown_type(self):
        ok, err = svc.validate("123", "barcode99")
        assert not ok


class TestIsPending:
    def test_pending_prefix(self):
        assert svc.is_pending("PENDING-abc123")

    def test_real_barcode(self):
        assert not svc.is_pending("2001234567890")

    def test_empty_string(self):
        assert not svc.is_pending("")

    def test_none(self):
        assert not svc.is_pending(None)
