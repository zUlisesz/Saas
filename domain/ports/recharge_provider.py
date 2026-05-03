# domain/ports/recharge_provider.py
#
# Puerto formal del proveedor de recargas (Patrón Ports & Adapters).
#
# PROPÓSITO:
#   Formaliza el contrato que MockRechargeProvider y RealRechargeProvider
#   deben cumplir. El servicio depende de este Port, no de las implementaciones.
#
# DECISIÓN — Protocol en vez de ABC:
#   Python 3.8+ permite duck typing estructural con Protocol.
#   Mock y Real no necesitan heredar ni importar este archivo para cumplirlo.
#   runtime_checkable habilita isinstance(mock, RechargeProviderPort) en tests.
#
# BENEFICIO INMEDIATO:
#   Si alguien cambia la firma de charge() en el Mock, mypy/pyright lo detecta
#   en import time, no en runtime. Los tests de compliance son la red de seguridad.

from typing import Protocol, runtime_checkable


@runtime_checkable
class RechargeProviderPort(Protocol):
    """
    Contrato formal de cualquier proveedor de recargas electrónicas.

    Implementaciones:
        infrastructure.external.recharge_provider_mock.MockRechargeProvider
        infrastructure.external.recharge_provider_real.RealRechargeProvider
    """

    def charge(self, phone: str, operator: str, amount: float) -> dict:
        """
        Procesa una recarga y retorna un dict con esta estructura exacta:

            {
                "status":   str,         # "success" | "failed"
                "tx_id":    str | None,  # UUID del proveedor si exitoso, None si falla
                "phone":    str,
                "operator": str,
                "amount":   float,
                "message":  str,
                "error":    str | None,  # descripción del error si status == "failed"
            }

        Raises:
            RechargeTimeoutError:   la operación excedió el tiempo límite.
            RechargeProviderError:  el proveedor falló definitivamente.
        """
        ...
