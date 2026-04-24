# domain/schemas/inventory_schemas.py
#
# NUEVA — Fase 5 (22 Abril 2026)
#
# DECISIÓN SOBRE REFACTOR INPUT/OUTPUT:
#   El roadmap (Bonus) sugiere separar schemas en input/ y output/.
#   No se hace ese refactor completo ahora porque:
#     1. Rompería todos los imports existentes en tests y servicios.
#     2. Los archivos existentes (product_schemas, sale_schemas, auth_schemas)
#        ya mezclan input/output sin causar problemas reales.
#     3. Una migración de carpetas cuesta más de lo que aporta en esta fase.
#
#   ALTERNATIVA adoptada: nuevos schemas siguen el mismo patrón plano
#   del proyecto, con comentarios que marcan qué DTOs son de entrada
#   y cuáles de salida. Cuando el proyecto llegue a Fase 8 y tenga
#   tests de integración, se puede hacer el refactor sin riesgo.
#
# PATRÓN:
#   @dataclass con validate() que lanza ValidationError con campo nombrado.
#   to_db_dict() para los DTOs de entrada (solo en CreateX/UpdateX).
#   Idéntico a product_schemas.py y sale_schemas.py.

from dataclasses import dataclass, field
from typing import Optional
from domain.exceptions import ValidationError

VALID_ALERT_TYPES = ("low_stock", "overstock", "expiring", "out_of_stock")
VALID_ALERT_STATUSES = ("new", "acknowledged", "resolved", "ignored")


# ============================================================
# INPUT DTOs — entrada del usuario / controlador → servicio
# ============================================================

@dataclass
class AdjustStockRequest:
    """
    DTO para ajuste manual de stock desde InventoryView.
    INPUT.
    """
    product_id:   str
    nuevo_stock:  int
    stock_minimo: Optional[int] = None
    notas:        str = ""

    def validate(self) -> None:
        if not self.product_id or not self.product_id.strip():
            raise ValidationError("product_id", "El ID del producto es requerido")
        if self.nuevo_stock < 0:
            raise ValidationError("nuevo_stock", "El stock no puede ser negativo")
        if self.stock_minimo is not None and self.stock_minimo < 0:
            raise ValidationError("stock_minimo", "El stock mínimo no puede ser negativo")


@dataclass
class UpdateThresholdRequest:
    """
    DTO para actualizar umbrales de inventario.
    INPUT.
    """
    product_id:         str
    stock_minimo:       int
    stock_maximo:       int
    reorder_point:      Optional[int]  = None
    reorder_quantity:   Optional[int]  = None
    alert_on_low_stock: bool = True
    alert_on_overstock: bool = False

    def validate(self) -> None:
        if not self.product_id or not self.product_id.strip():
            raise ValidationError("product_id", "El ID del producto es requerido")
        if self.stock_minimo < 0:
            raise ValidationError("stock_minimo", "El stock mínimo no puede ser negativo")
        if self.stock_maximo <= self.stock_minimo:
            raise ValidationError(
                "stock_maximo",
                f"Stock máximo ({self.stock_maximo}) debe ser mayor que el mínimo ({self.stock_minimo})",
            )
        rp = self.reorder_point
        if rp is not None and rp < self.stock_minimo:
            raise ValidationError(
                "reorder_point",
                f"Punto de reorden ({rp}) debe ser ≥ stock mínimo ({self.stock_minimo})",
            )
        rq = self.reorder_quantity
        if rq is not None and rq <= 0:
            raise ValidationError("reorder_quantity", "La cantidad de reorden debe ser mayor a 0")

    def to_db_dict(self, tenant_id: str) -> dict:
        """Genera el dict listo para upsert en inventory_thresholds."""
        return {
            "tenant_id":          tenant_id,
            "product_id":         self.product_id,
            "stock_minimo":       self.stock_minimo,
            "stock_maximo":       self.stock_maximo,
            "reorder_point":      self.reorder_point if self.reorder_point is not None else self.stock_minimo,
            "reorder_quantity":   self.reorder_quantity if self.reorder_quantity is not None else 50,
            "alert_on_low_stock": self.alert_on_low_stock,
            "alert_on_overstock": self.alert_on_overstock,
        }


@dataclass
class ResolveAlertRequest:
    """
    DTO para resolver o reconocer una alerta.
    INPUT.
    """
    alert_id: str
    action:   str          # 'acknowledge' | 'resolve' | 'ignore'
    notes:    Optional[str] = None

    VALID_ACTIONS = ("acknowledge", "resolve", "ignore")

    def validate(self) -> None:
        if not self.alert_id or not self.alert_id.strip():
            raise ValidationError("alert_id", "El ID de la alerta es requerido")
        if self.action not in self.VALID_ACTIONS:
            raise ValidationError(
                "action",
                f"Acción inválida. Válidas: {', '.join(self.VALID_ACTIONS)}",
            )


# ============================================================
# OUTPUT DTOs — servicio → controlador → vista
# Estos son dataclasses de lectura (sin validate, sin to_db_dict).
# Documentan la estructura de datos que retorna cada operación.
# ============================================================

@dataclass
class InventoryItemDTO:
    """
    Estructura aplanada que retorna InventoryService.list_inventory().
    Campos calculados en BD por RPC get_inventory_with_alerts.
    OUTPUT.
    """
    product_id:       str
    product_name:     str
    barcode:          str
    category_name:    str
    stock_actual:     int
    stock_minimo:     int
    stock_maximo:     int
    reorder_point:    int
    reorder_quantity: int
    stock_status:     str   # 'ok' | 'low' | 'out_of_stock' | 'overstock'
    active_alerts:    int
    updated_at:       Optional[str] = None

    @classmethod
    def from_rpc(cls, row: dict) -> "InventoryItemDTO":
        """Construye el DTO desde el dict que devuelve la RPC."""
        return cls(
            product_id       = row.get("product_id", ""),
            product_name     = row.get("product_name", "—"),
            barcode          = row.get("barcode", "—"),
            category_name    = row.get("category_name", "Sin categoría"),
            stock_actual     = row.get("stock_actual", 0),
            stock_minimo     = row.get("stock_minimo", 5),
            stock_maximo     = row.get("stock_maximo", 100),
            reorder_point    = row.get("reorder_point", 20),
            reorder_quantity = row.get("reorder_quantity", 50),
            stock_status     = row.get("stock_status", "ok"),
            active_alerts    = row.get("active_alerts", 0),
            updated_at       = row.get("updated_at"),
        )


@dataclass
class AlertSummaryDTO:
    """
    Resumen de alertas para el banner del dashboard.
    OUTPUT. Retornado por InventoryAlertService.get_summary().
    """
    total_new:    int
    critical:     int
    warning:      int
    top_critical: list = field(default_factory=list)

    @property
    def has_alerts(self) -> bool:
        return self.total_new > 0

    @property
    def badge_text(self) -> str:
        """Texto para el badge del sidebar."""
        if self.total_new == 0:
            return ""
        return str(self.total_new) if self.total_new < 100 else "99+"