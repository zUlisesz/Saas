# domain/services/recharge_service.py
#
# Fase 6: Servicio de Recargas Electrónicas.
#
# ARQUITECTURA — Patrón Adapter para el proveedor:
#   El servicio recibe `provider` por inyección (MockRechargeProvider o
#   RealRechargeProvider). Para pasar a producción solo cambia el container —
#   este servicio, la vista y el controller no cambian.
#
# FLUJO DE process():
#   1. Verifica sesión activa
#   2. Delega validación a RechargeReady().enforce() → lanza excepción tipada si falla
#   3. Crea registro en BD en estado 'pending' (_create_pending)
#   4. Llama al proveedor (Mock o Real)
#   5. Actualiza estado en BD (_complete)
#   6. Emite evento recharge_completed (fire & forget)
#   7. Retorna el resultado estándar
#
# OPERADORAS (Bolivia — deben coincidir con CHECK constraint de la BD):
#   movicel, comcel, viva, entel, tigo

from datetime import datetime
from session.session import Session
from domain.specifications.recharge_specs import RechargeReady
from domain.exceptions import RechargeTimeoutError, RechargeProviderError


class RechargeService:

    # ------------------------------------------------------------------ #
    # Catálogo de operadoras y montos (Bolivia)                          #
    # IMPORTANTE: las claves deben coincidir con el CHECK constraint BD  #
    # ------------------------------------------------------------------ #
    OPERATORS = {
        "movicel": {"name": "Movicel", "amounts": [10, 20, 30, 50, 100, 200], "commission_pct": 0.03},
        "comcel":  {"name": "Comcel",  "amounts": [10, 20, 50, 100, 200],     "commission_pct": 0.03},
        "viva":    {"name": "Viva",    "amounts": [10, 20, 30, 50, 100],      "commission_pct": 0.035},
        "entel":   {"name": "Entel",   "amounts": [20, 50, 100, 200, 300],    "commission_pct": 0.04},
        "tigo":    {"name": "Tigo",    "amounts": [10, 20, 50, 100, 200, 500],"commission_pct": 0.03},
    }

    def __init__(self, provider, recharge_repo=None, event_service=None):
        """
        Args:
            provider:      MockRechargeProvider o RealRechargeProvider.
                           Inyectado desde el container — no hardcodeado aquí.
            recharge_repo: RechargeRepository (opcional). Sin él, el historial
                           se guarda solo en memoria (útil para tests aislados).
            event_service: EventService (opcional). Emite recharge_completed.
        """
        self.provider      = provider
        self.recharge_repo = recharge_repo
        self.event_service = event_service
        self._memory_history: list[dict] = []

    # ------------------------------------------------------------------ #
    # Catálogo                                                            #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Procesar recarga                                                    #
    # ------------------------------------------------------------------ #

    def process(self, phone: str, operator: str, amount: float) -> dict:
        """
        Orquesta el flujo completo de una recarga electrónica.

        Raises:
            InvalidPhoneError:     número inválido (ValidationError → UI resalta campo)
            InvalidOperatorError:  operadora no válida (ValidationError)
            InvalidAmountError:    monto fuera de rango (ValidationError)
            RechargeTimeoutError:  proveedor no respondió a tiempo
            RechargeProviderError: fallo definitivo del proveedor externo
        """
        tenant_id = self._require_auth()

        # Validación delegada — lanza excepción tipada si algún campo falla
        RechargeReady().enforce(phone, operator, amount)

        op          = self.OPERATORS[operator]
        commission  = round(float(amount) * op["commission_pct"], 2)
        timestamp   = datetime.now().isoformat(timespec="seconds")

        # Registra pending en BD para trazabilidad incluso si el proveedor falla
        recharge_id = self._create_pending(tenant_id, phone, operator, amount)

        # Llama al proveedor (Mock o Real según lo inyectado)
        result = self.provider.charge(phone, operator, float(amount))

        # Añade campos calculados al resultado
        result["commission"] = commission
        result["timestamp"]  = timestamp
        result["tenant_id"]  = tenant_id

        # Persiste el estado final
        self._complete(recharge_id, result)

        # Evento fire & forget — fallo aquí no interrumpe al cajero
        if result.get("status") == "success" and self.event_service:
            try:
                self.event_service.emit(
                    tenant_id, "recharge_completed",
                    {"tx_id": result.get("tx_id"), "amount": amount,
                     "operator": op["name"], "commission": commission},
                )
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------ #
    # Historial                                                           #
    # ------------------------------------------------------------------ #

    def get_history(self, limit: int = 50) -> list:
        """Historial de recargas del tenant. Usa repo si está disponible."""
        tenant_id = self._require_auth()
        if self.recharge_repo:
            return self.recharge_repo.get_history(tenant_id=tenant_id, limit=limit)
        return list(reversed(self._memory_history[-limit:]))

    # ------------------------------------------------------------------ #
    # Privados                                                            #
    # ------------------------------------------------------------------ #

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise Exception("[RechargeService] No autenticado")
        return Session.tenant_id

    def _create_pending(
        self, tenant_id: str, phone: str, operator: str, amount: float
    ) -> str | None:
        """
        Inserta la recarga en BD con status='pending'.
        Retorna el UUID para que _complete() pueda actualizar el estado.
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
                print(f"[RechargeService] _create_pending falló: {e}")
        return None

    def _complete(self, recharge_id: str | None, result: dict) -> None:
        """
        Actualiza el estado de la recarga tras recibir la respuesta del proveedor.
        Si no hay repo (o falló _create_pending), guarda en memoria como fallback.
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
                print(f"[RechargeService] _complete falló: {e}")
        # Fallback a memoria
        self._memory_history.append(result)
