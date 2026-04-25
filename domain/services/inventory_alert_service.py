# domain/services/inventory_alert_service.py
#
# NUEVA — Fase 5 (22 Abril 2026)
#
# JUSTIFICACIÓN DE SEPARACIÓN DE InventoryService:
#
#   Las alertas tienen un ciclo de vida propio:
#       new → acknowledged → resolved | ignored
#   Y sus propias reglas de negocio:
#       - No se puede resolver una alerta ignorada
#       - Reconocer es idempotente (no falla si ya está reconocida)
#       - Solo el usuario activo puede reconocer/resolver
#
#   Meter esto en InventoryService lo haría responsable de:
#       stock, thresholds, kardex, movimientos Y alertas.
#   Demasiado — viola SRP.
#
# COORDINACIÓN:
#   InventoryController orquesta ambos servicios:
#       inventory_svc.adjust_stock()  →  luego alert_svc.generate()
#       sidebar badge                 →  alert_svc.count_new()
#
# PATRÓN:
#   Mismo patrón que BarcodeService — stateless, inyectable, sin UI.

from session.session import Session
from domain.exceptions import AuthenticationError, ValidationError
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class InventoryAlertService:

    def __init__(self, alert_repo):
        """
        Args:
            alert_repo: InventoryAlertRepository (requerido).

        DECISIÓN: No recibe event_service porque las alertas no generan
        más alertas (no hay cascada de eventos). Si en Fase 8 se necesita
        loguear "alerta resuelta", event_service se añade aquí.
        """
        self.repo = alert_repo

    # ------------------------------------------------------------------ #
    # Auth helper                                                         #
    # ------------------------------------------------------------------ #

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")
        return Session.tenant_id

    def _get_user_id(self) -> str:
        """Retorna el user_id de la sesión activa o None si no hay."""
        user = getattr(Session, "current_user", None)
        if user and isinstance(user, dict):
            return user.get("id") #type: ignore
        return None #type: ignore

    # ------------------------------------------------------------------ #
    # LECTURA                                                             #
    # ------------------------------------------------------------------ #

    def get_alerts(self, status: str = None, limit: int = 100) -> list: #type: ignore
        """
        Retorna alertas del tenant con datos del producto.

        Args:
            status: None = todas | 'new' | 'acknowledged' | 'resolved' | 'ignored'
            limit:  Máx de filas. Default 100.

        Añade 'product_name' al nivel raíz para facilitar la UI:
            item["product_name"] = item["products"]["name"]
        """
        tenant_id = self._require_auth()
        res   = self.repo.get_all(tenant_id, status=status, limit=limit)
        items = res.data or []

        # Aplanar datos del producto al nivel raíz
        for item in items:
            product = item.pop("products", {}) or {}
            item.setdefault("product_name", product.get("name", "—"))
            item.setdefault("barcode",      product.get("barcode", "—"))

        return items

    def get_new_alerts(self) -> list:
        """Alertas sin revisar. Atajo de get_alerts(status='new')."""
        return self.get_alerts(status="new")

    def count_new(self) -> int:
        """
        Conteo rápido de alertas nuevas para el badge del sidebar.
        No lanza excepción — retorna 0 ante cualquier error.
        """
        try:
            tenant_id = self._require_auth()
            return self.repo.count_new(tenant_id)
        except Exception:
            return 0

    def has_new_alerts(self) -> bool:
        """Helper booleano para condicionales en la UI."""
        return self.count_new() > 0

    def get_alerts_for_product(self, product_id: str, limit: int = 20) -> list:
        """
        Historial de alertas de un producto específico.
        Para el modal de detalle en InventoryView.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_by_product(tenant_id, product_id, limit)
        return res.data or []

    # ------------------------------------------------------------------ #
    # ESCRITURA — Transiciones de estado                                 #
    # ------------------------------------------------------------------ #

    def acknowledge(self, alert_id: str) -> dict:
        """
        Reconoce una alerta (new → acknowledged).

        REGLAS DE NEGOCIO:
            - Solo desde status='new' (validado en la RPC)
            - Idempotente: si ya está acknowledged, retorna {} sin error
            - Requiere usuario activo para registrar acknowledged_by

        Retorna el alert actualizado o {} si ya estaba procesado.
        """
        user_id = self._get_user_id()
        if not user_id:
            raise AuthenticationError("No hay usuario activo para reconocer la alerta")

        res = self.repo.acknowledge(alert_id, user_id)
        items = res.data or []

        if not items:
            _log.info(f"acknowledge: alerta {alert_id} ya estaba procesada (idempotente)")
            return {}

        _log.info(f"Alerta {alert_id} reconocida por {user_id}")
        return items[0]

    def resolve(self, alert_id: str, notes: str = None) -> dict: #type: ignore
        """
        Resuelve una alerta (new|acknowledged → resolved).

        REGLAS DE NEGOCIO:
            - Acepta desde 'new' o 'acknowledged'
            - No acepta desde 'ignored' (validado en RPC)
            - notes es opcional pero recomendado para auditoría

        Retorna el alert actualizado.
        """
        user_id = self._get_user_id()
        if not user_id:
            raise AuthenticationError("No hay usuario activo para resolver la alerta")

        res = self.repo.resolve(alert_id, user_id, notes)
        items = res.data or []

        if not items:
            raise ValidationError(
                "alert_id",
                "No se pudo resolver la alerta. Puede estar en estado 'ignored' o no existe."
            )

        _log.info(f"Alerta {alert_id} resuelta por {user_id}")
        return items[0]

    def ignore(self, alert_id: str) -> bool:
        """
        Descarta una alerta sin resolverla (→ ignored).
        Útil para alertas falsas o productos discontinuados.

        Retorna True si se actualizó correctamente.
        """
        try:
            res = self.repo.ignore(alert_id)
            return bool(res.data)
        except Exception as e:
            _log.error(f"ignore alert {alert_id}: {e}")
            return False

    # ------------------------------------------------------------------ #
    # GENERACIÓN — Trigger manual de alertas                             #
    # ------------------------------------------------------------------ #

    def generate_alerts(self) -> int:
        """
        Dispara la RPC generate_inventory_alerts() en BD.
        Crea alertas para todos los productos bajo mínimo que no tengan
        una alerta 'new' reciente (dedup de 1 hora en la RPC).

        Retorna el número de alertas generadas (puede ser 0 si ya existen).

        CUÁNDO LLAMAR:
            - Al abrir InventoryView (refresh manual)
            - Desde un APScheduler job (futuro Fase 8) cada 15-30 min
            - Después de un ajuste de stock

        DECISIÓN: no se llama automáticamente en __init__ porque sería
        demasiado costoso en cada instanciación del servicio.
        """
        try:
            res = self.repo.generate_for_tenant()
            if res and res.data:
                # La RPC retorna {alerts_generated: int, ...}
                count = 0
                for row in (res.data if isinstance(res.data, list) else [res.data]):
                    count += row.get("alerts_generated", 0) if isinstance(row, dict) else 0
                _log.info(f"generate_alerts: {count} alerta(s) generada(s)")
                return count
        except Exception as e:
            _log.error(f"generate_alerts falló: {e}")
        return 0

    # ------------------------------------------------------------------ #
    # Helper para la UI — resumen ejecutivo                              #
    # ------------------------------------------------------------------ #

    def get_summary(self) -> dict:
        """
        Resumen para el banner del dashboard y header.

        Retorna:
            {
                "total_new":    int,
                "critical":     int,   # out_of_stock
                "warning":      int,   # low stock
                "top_critical": list,  # max 3 items para el banner
            }

        DECISIÓN: calcula en Python (no en BD) porque ya traemos
        los datos con get_new_alerts() y el conteo es O(n) trivial.
        """
        try:
            alerts = self.get_new_alerts()
            critical = [a for a in alerts if a.get("alert_type") == "out_of_stock"]
            warning  = [a for a in alerts if a.get("alert_type") == "low_stock"]
            return {
                "total_new":    len(alerts),
                "critical":     len(critical),
                "warning":      len(warning),
                "top_critical": critical[:3],
            }
        except Exception:
            return {"total_new": 0, "critical": 0, "warning": 0, "top_critical": []}