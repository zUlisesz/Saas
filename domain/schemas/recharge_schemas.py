# domain/schemas/recharge_schemas.py
#
# DTOs de entrada y salida para recargas electrónicas.
#
# DECISIONES:
#   RechargeRequest.validate() delega a las Specs del dominio (paso 3).
#   No duplica lógica — única fuente de verdad.
#
#   tenant_id NO está en RechargeRequest: lo inyecta el controller desde
#   Session. La UI nunca sabe de tenants.
#
#   operator se normaliza a lowercase en validate() para ser tolerante
#   a variaciones de la UI. El CHECK constraint en BD es lowercase.
#
#   RechargeResponse y RechargeHistoryItem son frozen=True: son respuestas
#   de solo lectura — no deben mutar después de ser construidas.
#
#   user_message y status_label son presentation helpers puros.
#   Transformaciones de datos propios del objeto, sin decisiones de dominio.
#   Evitan duplicar el mismo formateo en la vista.

from dataclasses import dataclass
from typing import Optional

from domain.specifications.recharge_specs import ValidPhone, ValidAmount, ValidOperator


@dataclass
class RechargeRequest:
    """DTO de entrada para solicitar una recarga. tenant_id lo inyecta el controller."""
    phone:    str
    operator: str
    amount:   float

    def validate(self) -> None:
        """
        Normaliza y valida los campos usando las Specs del dominio.
        Lanza excepción tipada en el primer campo inválido.
        Orden deliberado: phone → operator → amount (más probable → más técnico).
        """
        self.phone    = self.phone.strip()
        self.operator = self.operator.lower().strip()

        ValidPhone().enforce(self.phone)
        ValidOperator().enforce(self.operator)
        ValidAmount().enforce(float(self.amount))


@dataclass(frozen=True)
class RechargeResponse:
    """DTO de salida tras procesar una recarga. Inmutable."""
    recharge_id: str
    status:      str           # success | failed | pending | timeout
    amount:      float
    phone:       str
    operator:    str
    tx_id:       Optional[str] = None
    error:       Optional[str] = None

    @property
    def user_message(self) -> str:
        """Mensaje listo para mostrar en la UI según el status."""
        if self.status == 'success':
            return f"Recarga exitosa de Bs {self.amount:.2f} a {self.phone}"
        if self.status == 'failed':
            return f"Recarga fallida: {self.error or 'Error desconocido'}"
        if self.status == 'timeout':
            return "Tiempo de espera agotado. Verifica en el historial."
        return f"Recarga en proceso (ID: {self.recharge_id[:8]}...)"


@dataclass(frozen=True)
class RechargeHistoryItem:
    """DTO de historial — combina datos de recarga y nombre del cajero."""
    id:          str
    phone:       str
    operator:    str
    amount:      float
    status:      str
    created_at:  str
    cajero_name: str

    @property
    def status_label(self) -> str:
        """Etiqueta legible para la UI con indicador visual."""
        labels = {
            'success':    '✓ Exitosa',
            'failed':     '✗ Fallida',
            'pending':    '… Pendiente',
            'timeout':    '⏱ Timeout',
            'processing': '⏳ Procesando',
        }
        return labels.get(self.status, self.status)
