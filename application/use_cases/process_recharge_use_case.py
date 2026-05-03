# application/use_cases/process_recharge_use_case.py
#
# Fase 6: Caso de uso — procesar una recarga electrónica.
#
# DECISIÓN — thin wrapper vs lógica en el servicio:
#   RechargeService ya orquesta el flujo completo (pending → provider →
#   complete → evento). Este use case existe por consistencia con el resto del
#   proyecto (CreateSaleUseCase, CreateProductUseCase) y como punto de
#   extensión para Fase 8: billing por tenant, cuotas diarias, audit log.
#   NO duplica lógica del servicio.
#
# FLUJO:
#   1. Loguea la intención (trazabilidad en logs)
#   2. Delega a RechargeService.process()
#   3. Retorna RechargeResponse tal cual

from domain.schemas.recharge_schemas import RechargeResponse
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class ProcessRechargeUseCase:
    """
    Caso de uso: procesar una recarga electrónica.

    Punto de extensión para Fase 8:
        - Verificar cuota diaria del tenant antes de llamar al servicio.
        - Registrar en audit log con tenant_id, user_id, monto.
        - Cobrar comisión al tenant (billing).
    """

    def __init__(self, recharge_service, event_service=None):
        self.service       = recharge_service
        self.event_service = event_service   # reservado para Fase 8

    def execute(self, phone: str, operator: str, amount: float) -> RechargeResponse:
        """
        Ejecuta la recarga completa.

        Args:
            phone, operator, amount: validados previamente por el controller
            vía RechargeRequest.validate() antes de llamar aquí.

        Returns:
            RechargeResponse (tipado, inmutable).

        Raises:
            Las mismas excepciones que RechargeService.process():
                InvalidPhoneError / InvalidOperatorError / InvalidAmountError
                RechargeTimeoutError
                RechargeProviderError
        """
        _log.info(
            "ProcessRechargeUseCase: iniciando recarga %s %s Bs %.2f",
            operator, phone, float(amount),
        )
        return self.service.process(phone, operator, float(amount))
