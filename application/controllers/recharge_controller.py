# application/controllers/recharge_controller.py
#
# Fase 6: Recargas Electrónicas — Controller.
#
# RESPONSABILIDAD:
#   Puente entre RechargeView y ProcessRechargeUseCase / RechargeService.
#   Valida entrada vía RechargeRequest, convierte excepciones de dominio en
#   snackbars, y retorna RechargeResponse (o None si falló).
#
# MANEJO DE ERRORES:
#   ValidationError       → snackbar con el mensaje del campo inválido
#   RechargeTimeoutError  → snackbar específico de timeout
#   RechargeProviderError → snackbar de error externo
#   Exception             → snackbar genérico (fallback)

from domain.schemas.recharge_schemas import RechargeRequest
from domain.specifications.recharge_specs import ValidPhone
from domain.exceptions import (
    ValidationError, RechargeTimeoutError, RechargeProviderError,
)


class RechargeController:

    def __init__(self, service, app, use_case=None):
        self.service  = service
        self.app      = app
        self.use_case = use_case   # ProcessRechargeUseCase — orquesta el flujo

    # ── Catálogo ──────────────────────────────────────────────────────────

    def get_operators(self) -> list:
        """Devuelve el catálogo de operadoras para poblar el Dropdown en la UI."""
        try:
            return self.service.get_operators()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_amounts_for(self, operator_id: str) -> list:
        try:
            return self.service.get_amounts_for(operator_id)
        except Exception:
            return []

    def get_commission_estimate(self, operator: str, amount: float) -> float:
        """Comisión estimada para el par operadora/monto. Retorna 0.0 si falla."""
        try:
            return self.service.estimate_commission(operator, amount)
        except Exception:
            return 0.0

    def get_history(self, limit: int = 10) -> list:
        """Historial de recargas del tenant. Retorna lista vacía si falla."""
        try:
            return self.service.get_history(limit=limit)
        except Exception:
            return []

    def is_valid_phone(self, phone: str) -> bool:
        """Validación rápida de teléfono para feedback pre-diálogo en la UI."""
        return ValidPhone().is_satisfied_by(phone)

    # ── Procesamiento ─────────────────────────────────────────────────────

    def process_recharge(self, phone: str, operator: str, amount: float):
        """
        Valida, procesa y muestra snackbar apropiado según el resultado.

        Delega la ejecución al ProcessRechargeUseCase si está disponible;
        cae al servicio directo si no (compatibilidad con tests sin use case).

        Returns:
            RechargeResponse si la recarga fue procesada (success o failed),
            None si hubo un error de validación, timeout o provider.
        """
        try:
            req = RechargeRequest(phone=phone, operator=operator, amount=amount)
            req.validate()

            if self.use_case:
                response = self.use_case.execute(req.phone, req.operator, float(req.amount))
            else:
                response = self.service.process(req.phone, req.operator, float(req.amount))

            if response.status == 'success':
                commission = self.service.estimate_commission(response.operator, response.amount)
                self.app.show_snackbar(
                    f"✓ Recarga exitosa | TX: {response.tx_id or '-'} | "
                    f"Comisión: Bs {commission:.2f}"
                )
                return response

            # status == 'failed'
            self.app.show_snackbar(response.user_message, error=True)
            return response

        except ValidationError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return None

        except RechargeTimeoutError:
            self.app.show_snackbar(
                "Tiempo de espera agotado. Verifica en el historial.", error=True
            )
            return None

        except RechargeProviderError as ex:
            self.app.show_snackbar(f"Error del proveedor: {str(ex)}", error=True)
            return None

        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return None
