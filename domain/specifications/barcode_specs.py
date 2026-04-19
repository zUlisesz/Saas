from domain.specifications.base import Specification

VALID_BARCODE_TYPES = {"ean13", "ean8", "upc", "code128", "qr"}


class BarcodeNotEmpty(Specification[dict]):
    def is_satisfied_by(self, candidate: dict) -> bool:
        barcode = candidate.get("barcode")
        return bool(barcode and barcode.strip())


class BarcodeNotPending(Specification[dict]):
    def is_satisfied_by(self, candidate: dict) -> bool:
        barcode = candidate.get("barcode") or ""
        return not barcode.startswith("PENDING-")


class BarcodeValidType(Specification[dict]):
    def is_satisfied_by(self, candidate: dict) -> bool:
        bt = candidate.get("barcode_type")
        return bt in VALID_BARCODE_TYPES


class BarcodeScanReady(Specification[dict]):
    """Composición: el producto tiene barcode real, no PENDING, y tipo válido."""

    def __init__(self):
        self._inner = BarcodeNotEmpty().and_(BarcodeNotPending()).and_(BarcodeValidType())

    def is_satisfied_by(self, candidate: dict) -> bool:
        return self._inner.is_satisfied_by(candidate)
