# application/controllers/recharge_controller.py
#
# Fase 6: Recargas Electrónicas — Controller.
#
# RESPONSABILIDAD:
#   Puente entre RechargeView y RechargeService.
#   Valida entrada vía RechargeRequest, convierte excepciones de dominio en
#   snackbars, y retorna RechargeResponse (o None si falló).
#
# MANEJO DE ERRORES:
#   ValidationError       → snackbar con el mensaje del campo inválido
#   RechargeTimeoutError  → snackbar específico de timeout
#   RechargeProviderError → snackbar de error externo
#   Exception             → snackbar genérico (fallback)

from domain.schemas.recharge_schemas import RechargeRequest
from domain.exceptions import (
    ValidationError, RechargeTimeoutError, RechargeProviderError,
)


class RechargeController:

    def __init__(self, service, app):
        self.service = service
        self.app     = app

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

    def process_recharge(self, phone: str, operator: str, amount: float):
        """
        Valida, procesa y muestra snackbar apropiado según el resultado.

        Returns:
            RechargeResponse si la recarga fue procesada (success o failed),
            None si hubo un error de validación, timeout o provider.
        """
        try:
            req = RechargeRequest(phone=phone, operator=operator, amount=amount)
            req.validate()

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

    def get_history(self) -> list:
        try:
            return self.service.get_history()
        except Exception:
            return []
