import hashlib

VALID_BARCODE_TYPES = {"ean13", "ean8", "upc", "code128", "qr"}


class BarcodeService:
    """
    Genera y valida códigos de barras. Stateless, sin dependencias externas.
    Prefijo EAN-13 '200' = rango GS1 para uso interno (no colisiona con proveedores).
    """

    EAN13_PREFIX = "200"

    # ─── Generadores ──────────────────────────────────────────────

    def generate_ean13(self, seed: str, prefix: str = EAN13_PREFIX) -> str:
        """EAN-13 determinístico: mismo seed → mismo barcode."""
        digest = hashlib.md5(seed.encode()).hexdigest()
        digits = "".join(c for c in digest if c.isdigit())
        while len(digits) < 9:
            digits += "0"
        body  = (prefix + digits)[:12]
        check = self._ean13_check(body)
        return body + str(check)

    def generate_ean8(self, seed: str) -> str:
        digest = hashlib.md5(seed.encode()).hexdigest()
        digits = "".join(c for c in digest if c.isdigit())
        while len(digits) < 7:
            digits += "0"
        body  = digits[:7]
        check = self._ean8_check(body)
        return body + str(check)

    def generate_code128(self, product_id: str) -> str:
        short = hashlib.md5(product_id.encode()).hexdigest()[:8].upper()
        return f"NXP-{short}"

    def generate_for_type(
        self, product_id: str, barcode_type: str = "ean13", prefix: str = EAN13_PREFIX
    ) -> str:
        t = (barcode_type or "ean13").lower()
        if t == "ean13":
            return self.generate_ean13(product_id, prefix)
        if t == "ean8":
            return self.generate_ean8(product_id)
        if t in ("upc", "code128", "qr"):
            return self.generate_code128(product_id)
        raise ValueError(f"Tipo de código no soportado: {barcode_type}")

    # ─── Validación ───────────────────────────────────────────────

    def validate(self, barcode: str, barcode_type: str = "ean13") -> tuple[bool, str]:
        if not barcode or not barcode.strip():
            return False, "El código de barras está vacío"
        t = (barcode_type or "ean13").lower()
        if t == "ean13":
            if len(barcode) != 13 or not barcode.isdigit():
                return False, "EAN-13 debe tener exactamente 13 dígitos"
            if int(barcode[-1]) != self._ean13_check(barcode[:12]):
                return False, "Dígito de control EAN-13 inválido"
        elif t == "ean8":
            if len(barcode) != 8 or not barcode.isdigit():
                return False, "EAN-8 debe tener exactamente 8 dígitos"
            if int(barcode[-1]) != self._ean8_check(barcode[:7]):
                return False, "Dígito de control EAN-8 inválido"
        elif t in ("upc", "code128", "qr"):
            if len(barcode) < 4:
                return False, "Código demasiado corto"
        else:
            return False, f"Tipo '{barcode_type}' no reconocido"
        return True, ""

    def is_pending(self, barcode: str | None) -> bool:
        if not barcode:
            return False
        return barcode.startswith("PENDING-")

    # ─── Interno ──────────────────────────────────────────────────

    def _ean13_check(self, body: str) -> int:
        # Pesos: posiciones impares (0-indexed par) → 1, pares → 3
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
        return (10 - (total % 10)) % 10

    def _ean8_check(self, body: str) -> int:
        # Pesos EAN-8: posiciones impares → 3, pares → 1
        total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(body))
        return (10 - (total % 10)) % 10
