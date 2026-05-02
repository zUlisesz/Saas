# domain/specifications/recharge_specs.py
#
# Especificaciones de dominio para recargas electrónicas.
#
# DECISIÓN: las specs viven aquí, no en el controller ni en la UI.
# La UI puede instanciar cualquier spec y llamar is_satisfied_by() para
# validación en vivo (ej: deshabilitar botón si el número es inválido)
# sin duplicar la lógica de dominio.
#
# RechargeReady agrupa las tres specs para validación completa antes de
# enviar al servicio. Como cada spec opera sobre un tipo distinto (str vs
# float), la composición se implementa por delegación interna en lugar de
# usar and_() de la base (que requiere candidatos del mismo tipo).

from domain.specifications.base import Specification


class ValidPhone(Specification[str]):
    """El teléfono debe ser solo dígitos, entre 8 y 12 caracteres."""

    failure_reason = "El número debe tener entre 8 y 12 dígitos"

    def is_satisfied_by(self, phone: str) -> bool:
        return phone.isdigit() and 8 <= len(phone) <= 12


class ValidAmount(Specification[float]):
    """El monto debe estar dentro del rango permitido en Bs."""

    MIN = 10.0
    MAX = 1000.0
    failure_reason = f"El monto debe estar entre Bs {MIN} y Bs {MAX}"

    def is_satisfied_by(self, amount: float) -> bool:
        return self.MIN <= amount <= self.MAX


class ValidOperator(Specification[str]):
    """El operador debe pertenecer al catálogo válido."""

    OPERATORS = ['movicel', 'comcel', 'viva', 'entel', 'tigo']
    failure_reason = f"Operador no válido. Opciones: {['movicel', 'comcel', 'viva', 'entel', 'tigo']}"

    def is_satisfied_by(self, operator: str) -> bool:
        return operator in self.OPERATORS


class RechargeReady:
    """
    Composición de ValidPhone, ValidAmount y ValidOperator.

    Recibe un dict con claves 'phone', 'amount', 'operator' y verifica
    que los tres campos sean válidos simultáneamente.

    Uso:
        spec = RechargeReady()
        if not spec.is_satisfied_by({"phone": p, "amount": a, "operator": o}):
            errors = spec.failure_reasons({"phone": p, "amount": a, "operator": o})
    """

    def __init__(self):
        self._phone_spec    = ValidPhone()
        self._amount_spec   = ValidAmount()
        self._operator_spec = ValidOperator()

    def is_satisfied_by(self, candidate: dict) -> bool:
        return (
            self._phone_spec.is_satisfied_by(candidate.get("phone", ""))
            and self._amount_spec.is_satisfied_by(candidate.get("amount", 0.0))
            and self._operator_spec.is_satisfied_by(candidate.get("operator", ""))
        )

    def failure_reasons(self, candidate: dict) -> list[str]:
        """Devuelve la lista de razones de fallo (vacía si todo es válido)."""
        reasons = []
        if not self._phone_spec.is_satisfied_by(candidate.get("phone", "")):
            reasons.append(ValidPhone.failure_reason)
        if not self._amount_spec.is_satisfied_by(candidate.get("amount", 0.0)):
            reasons.append(ValidAmount.failure_reason)
        if not self._operator_spec.is_satisfied_by(candidate.get("operator", "")):
            reasons.append(ValidOperator.failure_reason)
        return reasons
