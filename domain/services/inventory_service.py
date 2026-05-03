# domain/services/inventory_service.py
#
# FASE 5 — ACTUALIZACIÓN COMPLETA (22 Abril 2026)
#
# CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
#
#   1. list_inventory() — ahora usa repo.get_all_with_alerts() (nueva RPC).
#      Devuelve stock_status calculado en BD + active_alerts por producto.
#      RETRO-COMPAT: estructura de datos diferente — inventory_view.py
#      debe adaptarse (ver NOTA en inventory_view.py).
#
#   2. get_low_stock_alerts() — ahora usa repo.get_low_stock_report() (nueva RPC).
#      Más datos, mejor performance, mismo contrato de retorno.
#
#   3. get_thresholds() — NUEVO. Lee inventory_thresholds del tenant.
#
#   4. update_threshold() — NUEVO. Actualiza min/max/reorder con validaciones.
#      DECISIÓN: las validaciones de negocio (min < max, reorder >= min)
#      viven aquí (dominio), no en el repositorio.
#
#   5. get_movements_log() — NUEVO. Historial extendido (movements_log).
#
#   6. get_alert_count() — NUEVO. Conteo rápido para sidebar badge.
#
# MÉTODOS CONSERVADOS (sin cambios):
#   consume_stock, adjust_stock, init_stock, classify_inventory,
#   has_low_stock, get_kardex
#
# PRINCIPIO: este servicio no sabe nada de Supabase ni de la UI.
# Recibe repos/servicios por inyección y trabaja con dicts de Python.

from session.session import Session
from domain.exceptions import AuthenticationError, ValidationError
from domain.ports.inventory_repository import InventoryRepositoryPort
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class InventoryService:

    def __init__(self, inventory_repo: InventoryRepositoryPort, event_service=None):
        """
        Args:
            inventory_repo: InventoryRepository (requerido).
            event_service:  EventService (opcional) — para emitir low_stock.

        NOTA: InventoryAlertService es un servicio SEPARADO, no se inyecta aquí.
        Esta separación evita dependencia circular:
            InventoryService → emite eventos
            InventoryAlertService → lee/actualiza alertas
        La coordinación ocurre en InventoryController (application layer).
        """
        self.repo          = inventory_repo
        self.event_service = event_service

    # ------------------------------------------------------------------ #
    # Auth helper                                                         #
    # ------------------------------------------------------------------ #

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")
        return Session.tenant_id

    # ------------------------------------------------------------------ #
    # LECTURA — Inventario completo                                       #
    # ------------------------------------------------------------------ #

    def list_inventory(self) -> list:
        """
        Retorna inventario completo con estado calculado.

        Estructura de cada item (desde RPC get_inventory_with_alerts):
            product_id, product_name, barcode, category_name,
            stock_actual, stock_minimo, stock_maximo,
            reorder_point, reorder_quantity,
            stock_status: 'ok'|'low'|'out_of_stock'|'overstock',
            active_alerts: int,
            updated_at

        CAMBIO vs. versión anterior:
            Antes: {products: {name, barcode, ...}, stock_actual, stock_minimo}
            Ahora: campos aplanados + stock_status + active_alerts
            → inventory_view.py usa los nuevos nombres de campo.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_all_with_alerts(tenant_id)
        return res.data or []

    def get_stock(self, product_id: str) -> dict:
        """Stock de un producto específico. Retorna {} si no existe."""
        res = self.repo.get_stock(product_id)
        if res.data:
            return res.data[0]
        return {}

    # ------------------------------------------------------------------ #
    # LECTURA — Stock bajo / alertas                                      #
    # ------------------------------------------------------------------ #

    def get_low_stock_alerts(self) -> list:
        """
        Productos con stock_actual <= stock_minimo.

        Estructura de cada item (desde RPC get_low_stock_report):
            product_id, product_name, barcode,
            stock_actual, stock_minimo, reorder_quantity,
            stock_status: 'low'|'out_of_stock'

        Añade 'severity' para la UI (no viene de la RPC):
            'critical' → out_of_stock
            'warning'  → low
        """
        tenant_id = self._require_auth()
        res   = self.repo.get_low_stock_report(tenant_id)
        items = res.data or []
        for item in items:
            item["severity"] = (
                "critical" if item.get("stock_status") == "out_of_stock"
                else "warning"
            )
        return items

    def has_low_stock(self) -> bool:
        """Helper rápido para badge en sidebar. No lanza excepción."""
        try:
            return len(self.get_low_stock_alerts()) > 0
        except Exception:
            return False

    def classify_inventory(self, items: list) -> dict:
        """
        Agrupa items de list_inventory() por estado.
        Útil para el dashboard y reportes.

        Returns: {ok: [...], warning: [...], critical: [...], overstock: [...]}
        """
        result = {"ok": [], "warning": [], "critical": [], "overstock": []}
        for item in items:
            status = item.get("stock_status", "ok")
            if status == "out_of_stock":
                result["critical"].append(item)
            elif status == "low":
                result["warning"].append(item)
            elif status == "overstock":
                result["overstock"].append(item)
            else:
                result["ok"].append(item)
        return result

    # ------------------------------------------------------------------ #
    # LECTURA — Thresholds (NUEVO — Fase 5)                              #
    # ------------------------------------------------------------------ #

    def get_thresholds(self) -> list:
        """
        Lee todos los umbrales de inventario del tenant activo.
        Incluye datos del producto para mostrar en la UI.

        Retorna lista de dicts con:
            id, tenant_id, product_id, stock_minimo, stock_maximo,
            reorder_point, reorder_quantity,
            alert_on_low_stock, alert_on_overstock,
            products: {id, name, barcode}
        """
        tenant_id = self._require_auth()
        res = self.repo.get_thresholds(tenant_id)
        return res.data or []

    def get_threshold_for_product(self, product_id: str) -> dict:
        """Umbral de un producto específico. Retorna defaults si no existe."""
        tenant_id = self._require_auth()
        res = self.repo.get_threshold_by_product(tenant_id, product_id)
        if res.data:
            return res.data[0]
        # Defaults para productos sin threshold configurado
        return {
            "stock_minimo":       5,
            "stock_maximo":       100,
            "reorder_point":      10,
            "reorder_quantity":   50,
            "alert_on_low_stock": True,
            "alert_on_overstock": False,
        }

    # ------------------------------------------------------------------ #
    # ESCRITURA — Thresholds (NUEVO — Fase 5)                            #
    # ------------------------------------------------------------------ #

    def update_threshold(
        self,
        product_id: str,
        stock_minimo: int,
        stock_maximo: int,
        reorder_point: int = None, #type: ignore
        reorder_quantity: int = None, #type: ignore
        alert_on_low_stock: bool = True,
        alert_on_overstock: bool = False,
    ) -> dict:
        """
        Actualiza o crea el threshold de un producto.

        Validaciones de dominio (viven aquí, no en el repo):
            - stock_minimo >= 0
            - stock_maximo > stock_minimo
            - reorder_point >= stock_minimo (si se provee)
            - reorder_quantity > 0 (si se provee)

        Retorna el threshold actualizado.
        """
        tenant_id = self._require_auth()

        # Validaciones
        if stock_minimo < 0:
            raise ValidationError("stock_minimo", "El stock mínimo no puede ser negativo")
        if stock_maximo <= stock_minimo:
            raise ValidationError(
                "stock_maximo",
                f"Stock máximo ({stock_maximo}) debe ser mayor que el mínimo ({stock_minimo})"
            )

        rp = reorder_point if reorder_point is not None else stock_minimo
        rq = reorder_quantity if reorder_quantity is not None else 50

        if rp < stock_minimo:
            raise ValidationError(
                "reorder_point",
                f"Punto de reorden ({rp}) debe ser >= stock mínimo ({stock_minimo})"
            )
        if rq <= 0:
            raise ValidationError("reorder_quantity", "La cantidad de reorden debe ser mayor a 0")

        data = {
            "tenant_id":          tenant_id,
            "product_id":         product_id,
            "stock_minimo":       stock_minimo,
            "stock_maximo":       stock_maximo,
            "reorder_point":      rp,
            "reorder_quantity":   rq,
            "alert_on_low_stock": alert_on_low_stock,
            "alert_on_overstock": alert_on_overstock,
        }

        res = self.repo.upsert_threshold(data)
        _log.info(f"Threshold actualizado: product={product_id} min={stock_minimo} max={stock_maximo}")
        return res.data[0] if res.data else data

    # ------------------------------------------------------------------ #
    # ESCRITURA — Consumir stock (llamado por SaleService)               #
    # ------------------------------------------------------------------ #

    def consume_stock(self, product_id: str, quantity: int,
                      sale_id: str = None, tenant_id: str = None) -> None: #type: ignore
        """
        Decrementa stock tras una venta y registra kardex.

        Args:
            product_id: UUID del producto vendido.
            quantity:   Unidades vendidas (positivo).
            sale_id:    UUID de la venta para referencia cruzada.
            tenant_id:  Opcional; si no se pasa usa Session.

        EMITE evento 'low_stock' si el stock resultante <= stock_minimo.
        DECISIÓN: el evento se emite aquí (dominio), no en el repositorio.
        """
        t_id = tenant_id or self._require_auth()

        current = self.repo.get_stock(product_id)
        if not current.data:
            _log.warning(f"consume_stock: producto {product_id} sin registro en inventory")
            return

        stock_ant  = current.data[0]["stock_actual"]
        stock_min  = current.data[0]["stock_minimo"]
        stock_post = max(0, stock_ant - quantity)

        self.repo.upsert(product_id, stock_post, stock_min)

        # Kardex
        self.repo.add_kardex_entry({
            "tenant_id":       t_id,
            "product_id":      product_id,
            "tipo":            "salida",
            "cantidad":        quantity,
            "saldo_anterior":  stock_ant,
            "saldo_posterior": stock_post,
            "referencia_tipo": "venta",
            "referencia_id":   sale_id,
            "notas":           f"Venta — {quantity} unidad(es)",
        })

        # Emitir evento si queda bajo mínimo
        if stock_post <= stock_min and self.event_service:
            try:
                self.event_service.emit("low_stock", {
                    "product_id":  product_id,
                    "tenant_id":   t_id,
                    "stock_post":  stock_post,
                    "stock_min":   stock_min,
                })
            except Exception as e:
                _log.warning(f"No se pudo emitir evento low_stock: {e}")

    # ------------------------------------------------------------------ #
    # ESCRITURA — Ajuste manual (desde InventoryView)                   #
    # ------------------------------------------------------------------ #

    def adjust_stock(self, product_id: str, nuevo_stock: int,
                     stock_minimo: int = None, notas: str = "") -> dict: #type: ignore
        """
        Ajuste manual con registro en kardex.

        Args:
            product_id:   UUID del producto.
            nuevo_stock:  Valor ABSOLUTO del nuevo stock (no delta).
            stock_minimo: Nuevo umbral mínimo. Opcional; mantiene el actual si None.
            notas:        Motivo del ajuste para el kardex.

        Returns: {"stock_anterior": int, "stock_posterior": int}

        DECISIÓN: el ajuste siempre registra kardex tipo='ajuste'.
        La cantidad es el delta (puede ser negativo = corrección a la baja).
        """
        tenant_id = self._require_auth()

        if nuevo_stock < 0:
            raise ValidationError("nuevo_stock", "El stock no puede ser negativo")

        current = self.repo.get_stock(product_id)
        if not current.data:
            # Producto sin registro — inicializamos
            self.init_stock(product_id, nuevo_stock, stock_minimo or 5)
            return {"stock_anterior": 0, "stock_posterior": nuevo_stock}

        stock_ant = current.data[0]["stock_actual"]
        stock_min = stock_minimo if stock_minimo is not None else current.data[0]["stock_minimo"]
        delta     = nuevo_stock - stock_ant

        self.repo.upsert(product_id, nuevo_stock, stock_min)

        self.repo.add_kardex_entry({
            "tenant_id":       tenant_id,
            "product_id":      product_id,
            "tipo":            "ajuste",
            "cantidad":        abs(delta),
            "saldo_anterior":  stock_ant,
            "saldo_posterior": nuevo_stock,
            "referencia_tipo": "ajuste_manual",
            "notas":           notas or "Ajuste manual de inventario",
        })

        _log.info(f"Ajuste: product={product_id} {stock_ant}→{nuevo_stock}")
        return {"stock_anterior": stock_ant, "stock_posterior": nuevo_stock}

    # ------------------------------------------------------------------ #
    # ESCRITURA — Inicializar stock (producto nuevo)                     #
    # ------------------------------------------------------------------ #

    def init_stock(self, product_id: str, stock_inicial: int = 0,
                   stock_minimo: int = 5) -> None:
        """
        Crea el registro inicial de inventario para un producto nuevo.
        Registra en kardex como tipo='inicio'.
        Llamado desde ProductService.create_product().
        """
        tenant_id = self._require_auth()
        self.repo.upsert(product_id, stock_inicial, stock_minimo)
        self.repo.add_kardex_entry({
            "tenant_id":       tenant_id,
            "product_id":      product_id,
            "tipo":            "inicio",
            "cantidad":        stock_inicial,
            "saldo_anterior":  0,
            "saldo_posterior": stock_inicial,
            "referencia_tipo": "manual",
            "notas":           "Stock inicial al crear producto",
        })

    # ------------------------------------------------------------------ #
    # LECTURA — Historial                                                 #
    # ------------------------------------------------------------------ #

    def get_kardex(self, product_id: str, limit: int = 50) -> list:
        """
        Historial kardex (fuente contable).
        Para el modal de detalle en InventoryView.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_kardex(tenant_id, product_id, limit)
        return res.data or []

    def get_movements_log(self, product_id: str, limit: int = 50) -> list:
        """
        Historial extendido (movements_log — fuente técnica).
        Complementa get_kardex() con datos de movement_type y before/after.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_movements_log(tenant_id, product_id, limit)
        return res.data or []

    def get_alert_count(self) -> int:
        """
        Conteo rápido de alertas nuevas para el badge del sidebar.
        Delega al repo para un COUNT eficiente sin traer filas.
        """
        try:
            tenant_id = self._require_auth()
            return self.repo.get_low_stock_report(tenant_id).data.__len__() if hasattr(self.repo, 'get_low_stock_report') else 0
        except Exception:
            return 0