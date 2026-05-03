# domain/services/recharge_service.py
#
# Fase 6: Servicio de Recargas Electrónicas.
#
# ARQUITECTURA — Ports & Adapters:
#   provider: RechargeProviderPort — Mock en dev, Real en prod.
#   El container decide qué implementación inyectar. Este servicio no cambia.
#
# FLUJO DE process():
#   1. Verifica sesión
#   2. Valida vía RechargeReady().enforce() — lanza excepción tipada si falla
#   3. Crea registro pending en BD (_create_pending)
#   4. Llama al provider → captura Timeout/ProviderError para persistir estado
#      antes de re-lanzar
#   5. Persiste estado final (_complete)
#   6. Emite evento fire & forget
#   7. Retorna RechargeResponse (tipado — no dict crudo)
#
# OPERADORAS: Bolivia — claves deben coincidir con CHECK constraint de BD.

from datetime import datetime

from session.session import Session
from infrastructure.logging_config import get_logger
from domain.ports.recharge_provider import RechargeProviderPort
from domain.specifications.recharge_specs import RechargeReady
from domain.exceptions import RechargeTimeoutError, RechargeProviderError
from domain.schemas.recharge_schemas import RechargeResponse

_log = get_logger(__name__)


class RechargeService:

    # ── Catálogo (Bolivia — coincide con CHECK constraint en BD) ──────────
    OPERATORS = {
        "movicel": {"name": "Movicel", "amounts": [10, 20, 30, 50, 100, 200], "commission_pct": 0.03},
        "comcel":  {"name": "Comcel",  "amounts": [10, 20, 50, 100, 200],     "commission_pct": 0.03},
        "viva":    {"name": "Viva",    "amounts": [10, 20, 30, 50, 100],      "commission_pct": 0.035},
        "entel":   {"name": "Entel",   "amounts": [20, 50, 100, 200, 300],    "commission_pct": 0.04},
        "tigo":    {"name": "Tigo",    "amounts": [10, 20, 50, 100, 200, 500],"commission_pct": 0.03},
    }

    def __init__(
        self,
        provider:      RechargeProviderPort,
        recharge_repo=None,
        event_service=None,
    ):
        self.provider      = provider
        self.recharge_repo = recharge_repo
        self.event_service = event_service
        self._memory_history: list[dict] = []

    # ── Catálogo ──────────────────────────────────────────────────────────

    def get_operators(self) -> list[dict]:
        """Lista de operadoras disponibles con sus montos para poblar la UI."""
        return [
            {"id": op_id, "name": info["name"], "amounts": info["amounts"]}
            for op_id, info in self.OPERATORS.items()
        ]

    def get_amounts_for(self, operator_id: str) -> list[int]:
        op = self.OPERATORS.get(operator_id)
        if not op:
            from domain.exceptions import InvalidOperatorError
            raise InvalidOperatorError(list(self.OPERATORS.keys()))
        return op["amounts"]

    def estimate_commission(self, operator: str, amount: float) -> float:
        """
        Comisión estimada para un operator + monto dados.
        Desacopla la UI de conocer las tasas — la vista llama este método
        y muestra "Ganancia: Bs X.XX" sin saber los porcentajes.
        """
        op  = self.OPERATORS.get(operator, {})
        pct = op.get("commission_pct", 0.03)
        return round(float(amount) * pct, 2)

    # ── Procesar recarga ──────────────────────────────────────────────────

    def process(self, phone: str, operator: str, amount: float) -> RechargeResponse:
        """
        Orquesta el flujo completo de una recarga electrónica.

        Returns:
            RechargeResponse — objeto tipado con status, tx_id, user_message, etc.

        Raises:
            InvalidPhoneError / InvalidOperatorError / InvalidAmountError
            RechargeTimeoutError   (después de persistir status='timeout')
            RechargeProviderError  (después de persistir status='failed')
        """
        tenant_id = self._require_auth()
        RechargeReady().enforce(phone, operator, amount)

        op         = self.OPERATORS[operator]
        commission = round(float(amount) * op["commission_pct"], 2)
        timestamp  = datetime.now().isoformat(timespec="seconds")

        recharge_id = self._create_pending(tenant_id, phone, operator, amount)

        try:
            result = self.provider.charge(phone, operator, float(amount))
        except RechargeTimeoutError:
            # Persistir el timeout antes de re-lanzar — el cajero puede
            # consultar el historial para saber si la recarga se procesó.
            self._complete(recharge_id, {
                "status":      "timeout",
                "tx_id":       None,
                "error":       "Tiempo de espera agotado",
                "error_code":  "TIMEOUT",
            })
            raise
        except RechargeProviderError as exc:
            self._complete(recharge_id, {
                "status":      "failed",
                "tx_id":       None,
                "error":       str(exc),
                "error_code":  "PROVIDER_ERROR",
            })
            raise

        result["commission"] = commission
        result["timestamp"]  = timestamp
        result["tenant_id"]  = tenant_id

        self._complete(recharge_id, result)

        if result.get("status") == "success" and self.event_service:
            try:
                self.event_service.emit(
                    tenant_id, "recharge_completed",
                    {"tx_id": result.get("tx_id"), "amount": amount,
                     "operator": op["name"], "commission": commission},
                )
            except Exception:
                pass

        return RechargeResponse(
            recharge_id=recharge_id or "",
            status=result.get("status", "failed"),
            amount=float(amount),
            phone=phone,
            operator=operator,
            tx_id=result.get("tx_id"),
            error=result.get("error") or result.get("error_message"),
        )

    # ── Historial ─────────────────────────────────────────────────────────

    def get_history(self, limit: int = 50) -> list:
        """Historial de recargas del tenant. Usa repo si está disponible."""
        tenant_id = self._require_auth()
        if self.recharge_repo:
            return self.recharge_repo.get_history(tenant_id=tenant_id, limit=limit)
        return list(reversed(self._memory_history[-limit:]))

    # ── Privados ──────────────────────────────────────────────────────────

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise Exception("[RechargeService] No autenticado")
        return Session.tenant_id

    def _create_pending(
        self, tenant_id: str, phone: str, operator: str, amount: float
    ) -> str | None:
        """
        Inserta la recarga en BD con status='pending'.
        Fallo silencioso — no interrumpe el flujo si la BD no está disponible.
        """
        if self.recharge_repo:
            try:
                created_by = getattr(Session.current_user, "id", "") or ""
                return self.recharge_repo.create(
                    tenant_id=tenant_id,
                    phone=phone,
                    operator=operator,
                    amount=amount,
                    created_by=created_by,
                )
            except Exception as e:
                _log.error("RechargeService._create_pending falló: %s", e)
        return None

    def _complete(self, recharge_id: str | None, result: dict) -> None:
        """
        Actualiza el estado de la recarga en BD.
        Si no hay repo o falló _create_pending, guarda en memoria como fallback.
        """
        if recharge_id and self.recharge_repo:
            try:
                self.recharge_repo.update_status(
                    recharge_id=recharge_id,
                    status=result.get("status", "failed"),
                    ext_tx_id=result.get("tx_id"),
                    ext_response={k: v for k, v in result.items()
                                  if k not in ("tenant_id",)},
                    error_code=result.get("error_code"),
                    error_message=result.get("error") or result.get("error_message"),
                )
                return
            except Exception as e:
                _log.error("RechargeService._complete falló: %s", e)
        self._memory_history.append(result)
