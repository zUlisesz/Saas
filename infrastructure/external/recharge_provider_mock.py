# infrastructure/external/recharge_provider_mock.py
#
# NUEVA — Fase 6: Proveedor mock para desarrollo y testing.
#
# PROPÓSITO:
#   Simula la API de un proveedor de recargas real sin hacer llamadas
#   de red. Permite que la UI se integre por completo antes de tener
#   credenciales de producción.
#
# DISTRIBUCIÓN DE RESULTADOS:
#   85% éxito  → status 'success' + tx_id UUID
#   10% fallo  → status 'failed'  + error de negocio (saldo insuficiente)
#    5% timeout → lanza RechargeTimeoutError (simula red lenta)
#
# DETERMINISMO EN TESTS:
#   MockRechargeProvider(seed=42) fija el random — la misma secuencia de
#   resultados en cada ejecución del test suite.
#
# REEMPLAZO A PRODUCCIÓN:
#   El servicio recibe el proveedor por inyección. Para pasar a producción
#   solo se cambia el provider registrado en el container — el servicio,
#   la vista y los tests no cambian.

import time
import uuid
import random

from domain.exceptions import RechargeTimeoutError


class MockRechargeProvider:
    """Proveedor de recargas simulado para desarrollo y testing."""

    DELAY_SECONDS = 0.5   # Latencia artificial — simula round-trip de red

    # Umbrales de la distribución probabilística
    _SUCCESS_THRESHOLD = 0.85   # 0.00 – 0.85 → éxito
    _TIMEOUT_THRESHOLD = 0.95   # 0.85 – 0.95 → fallo de negocio
                                # 0.95 – 1.00 → timeout

    def __init__(self, seed: int | None = None):
        """
        Args:
            seed: Semilla para random.Random. Si es None, usa la entropía
                  del sistema (comportamiento no-determinista). Pasar un int
                  fija la secuencia de resultados para tests.
        """
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ #
    # API pública                                                         #
    # ------------------------------------------------------------------ #

    def charge(self, phone: str, operator: str, amount: float) -> dict:
        """
        Simula el procesamiento de una recarga electrónica.

        Args:
            phone:    Número de teléfono destino (ya validado por la spec).
            operator: Nombre de la operadora ('tigo', 'viva', etc.)
            amount:   Monto de la recarga en Bs.

        Returns:
            {
                "status":   "success" | "failed",
                "tx_id":    str | None,
                "phone":    str,
                "operator": str,
                "amount":   float,
                "message":  str,
                "error":    str | None,
            }

        Raises:
            RechargeTimeoutError: 5% de las llamadas — simula red lenta.
        """
        time.sleep(self.DELAY_SECONDS)

        roll = self._rng.random()

        if roll < self._SUCCESS_THRESHOLD:
            return self._success_response(phone, operator, amount)
        elif roll < self._TIMEOUT_THRESHOLD:
            return self._failure_response(phone, operator, amount)
        else:
            raise RechargeTimeoutError(
                f"Timeout al contactar operador '{operator}' para {phone} "
                f"(simulado — ocurre ~5% de las veces)"
            )

    # ------------------------------------------------------------------ #
    # Privados                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _success_response(phone: str, operator: str, amount: float) -> dict:
        return {
            "status":   "success",
            "tx_id":    str(uuid.uuid4()),
            "phone":    phone,
            "operator": operator,
            "amount":   amount,
            "message":  f"Recarga de Bs {amount:.2f} aplicada exitosamente",
            "error":    None,
        }

    @staticmethod
    def _failure_response(phone: str, operator: str, amount: float) -> dict:
        return {
            "status":   "failed",
            "tx_id":    None,
            "phone":    phone,
            "operator": operator,
            "amount":   amount,
            "message":  "Recarga rechazada por el operador",
            "error":    "Saldo insuficiente en cuenta del operador",
        }
