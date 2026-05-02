# infrastructure/external/recharge_provider_real.py
#
# PLACEHOLDER — Fase 6: Proveedor real para producción.
#
# ESTADO: NotImplementedError en todos los métodos.
#         Implementar cuando se tengan credenciales del proveedor.
#
# ARQUITECTURA PREVISTA:
#   • HTTP POST al endpoint del proveedor con autenticación por API key.
#   • Timeout de 30s por intento.
#   • 3 reintentos con backoff exponencial: 1s → 2s → 4s.
#   • Mapeo de la respuesta raw al formato interno estándar.
#   • Lanza RechargeProviderError si el proveedor falla definitivamente
#     (agotados los reintentos o error HTTP no recuperable).
#   • Lanza RechargeTimeoutError si todos los intentos expiran.
#
# PARA IMPLEMENTAR:
#   1. Instalar dependencia: pip install httpx   (o requests, ya está en proyecto)
#   2. Añadir RECHARGE_API_URL y RECHARGE_API_KEY al .env
#   3. Completar _post_to_provider() y _map_response()
#   4. En container.py, reemplazar MockRechargeProvider por RealRechargeProvider
#
# REEMPLAZO SIN IMPACTO:
#   El servicio recibe el proveedor por inyección. Solo cambia el container.

import time

from domain.exceptions import RechargeProviderError, RechargeTimeoutError


class RealRechargeProvider:
    """Proveedor de recargas para producción. STUB — pendiente de implementación."""

    TIMEOUT_SECONDS = 30
    MAX_RETRIES     = 3
    RETRY_BASE_DELAY = 1  # segundos; el backoff es 1s, 2s, 4s

    def __init__(self, api_url: str, api_key: str):
        """
        Args:
            api_url: URL base del endpoint del proveedor (del .env).
            api_key: Clave de autenticación (del .env).
        """
        self._api_url = api_url
        self._api_key = api_key

    # ------------------------------------------------------------------ #
    # API pública                                                         #
    # ------------------------------------------------------------------ #

    def charge(self, phone: str, operator: str, amount: float) -> dict:
        """
        Envía la recarga al proveedor con reintentos y backoff exponencial.

        Args:
            phone:    Número de teléfono destino.
            operator: Operadora destino.
            amount:   Monto en Bs.

        Returns:
            Respuesta estándar interna (ver MockRechargeProvider.charge).

        Raises:
            RechargeTimeoutError:   Todos los intentos expiraron.
            RechargeProviderError:  Proveedor devolvió error definitivo
                                    o se agotaron los reintentos.
        """
        raise NotImplementedError(
            "RealRechargeProvider.charge() no está implementado. "
            "Agrega las credenciales al .env y completa _post_to_provider()."
        )

    # ------------------------------------------------------------------ #
    # Privados (stubs documentados para la implementación futura)         #
    # ------------------------------------------------------------------ #

    def _post_to_provider(self, payload: dict) -> dict:
        """
        HTTP POST al endpoint del proveedor.
        Debe respetar TIMEOUT_SECONDS y propagar HTTPError / TimeoutError
        para que charge() pueda decidir si reintentar.

        Implementación sugerida con httpx:
            import httpx
            response = httpx.post(
                self._api_url,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        """
        raise NotImplementedError

    def _map_response(self, raw: dict, phone: str, operator: str, amount: float) -> dict:
        """
        Traduce la respuesta del proveedor al formato interno estándar:
            {
                "status":   "success" | "failed",
                "tx_id":    str | None,
                "phone":    str,
                "operator": str,
                "amount":   float,
                "message":  str,
                "error":    str | None,
            }

        El mapeo depende del contrato de la API del proveedor.
        Consultar la documentación cuando se tengan credenciales.
        """
        raise NotImplementedError

    def _should_retry(self, error: Exception) -> bool:
        """
        Decide si un error es recuperable (vale la pena reintentar).
        Errores de red y timeouts → True.
        Errores 4xx (datos inválidos) → False.
        """
        raise NotImplementedError
