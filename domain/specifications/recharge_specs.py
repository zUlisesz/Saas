# domain/specifications/recharge_specs.py
#
# Especificaciones de dominio para recargas electrónicas.
#
# DOS FLUJOS DE VALIDACIÓN:
#   is_satisfied_by() → UI, validación en vivo, retorna bool sin excepción.
#   enforce()         → Service, lanza la excepción tipada correspondiente.
#
# DECISIÓN: enforce() vive en la spec, no en el servicio. Así hay un único
# lugar donde se define qué excepción corresponde a cada regla de dominio.
# El servicio delega, no duplica.

from domain.specifications.base import Specification
from domain.exceptions import (
    InvalidPhoneError, InvalidAmountError, InvalidOperatorError,
)

OPERATORS  = ['movicel', 'comcel', 'viva', 'entel', 'tigo']
AMOUNT_MIN = 10.0
AMOUNT_MAX = 1000.0


class ValidPhone(Specification[str]):
    """El teléfono debe ser solo dígitos, entre 8 y 12 caracteres."""

    def is_satisfied_by(self, phone: str) -> bool:
        return isinstance(phone, str) and phone.isdigit() and 8 <= len(phone) <= 12

    def enforce(self, phone: str) -> None:
        if not self.is_satisfied_by(phone):
            raise InvalidPhoneError()


class ValidAmount(Specification[float]):
    """El monto debe estar dentro del rango Bs 10 – Bs 1000."""

    def is_satisfied_by(self, amount) -> bool:
        try:
            return AMOUNT_MIN <= float(amount) <= AMOUNT_MAX
        except (TypeError, ValueError):
            return False

    def enforce(self, amount) -> None:
        if not self.is_satisfied_by(amount):
            raise InvalidAmountError(AMOUNT_MIN, AMOUNT_MAX)


class ValidOperator(Specification[str]):
    """El operador debe pertenecer al catálogo de operadoras bolivianas."""

    def is_satisfied_by(self, operator: str) -> bool:
        return operator in OPERATORS

    def enforce(self, operator: str) -> None:
        if not self.is_satisfied_by(operator):
            raise InvalidOperatorError(OPERATORS)


class RechargeReady:
    """
    Composición de ValidPhone, ValidAmount y ValidOperator.
    Punto de entrada único para validar una recarga completa.

    Uso en servicio (lanza excepción tipada):
        RechargeReady().enforce(phone, operator, amount)

    Uso en UI (sin excepción, para feedback en vivo):
        ok, msg = RechargeReady().validate(phone, operator, amount)
    """

    def __init__(self):
        self._phone    = ValidPhone()
        self._amount   = ValidAmount()
        self._operator = ValidOperator()

    def enforce(self, phone: str, operator: str, amount) -> None:
        """Lanza la primera excepción tipada que encuentre."""
        self._phone.enforce(phone)
        self._operator.enforce(operator)
        self._amount.enforce(amount)

    def validate(self, phone: str, operator: str, amount) -> tuple[bool, str]:
        """Retorna (True, '') o (False, 'mensaje') sin lanzar excepción."""
        for spec, val in [
            (self._phone,    phone),
            (self._operator, operator),
            (self._amount,   amount),
        ]:
            if not spec.is_satisfied_by(val):
                try:
                    spec.enforce(val)
                except Exception as ex:
                    return False, str(ex)
        return True, ""
