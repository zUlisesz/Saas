# domain/services/inventory_service.py
#
# ============================================================================
# FASE 5 — Inventario Inteligente: cambios y adiciones
# ============================================================================
#
# MÉTODOS NUEVOS:
#   get_inventory_full()         — RPC enriquecida con stock_status + thresholds
#   get_thresholds()             — Leer thresholds del tenant completo
#   get_threshold()              — Leer threshold de un producto individual
#   set_threshold()              — Crear/actualizar threshold (mínimo, máximo, reorder)
#   get_alerts()                 — Listar alertas por status
#   get_alerts_count()           — Badge rápido de alertas sin revisar
#   acknowledge_alert()          — Marcar una alerta como vista
#   resolve_alert()              — Marcar una alerta como resuelta
#   ignore_alert()               — Descartar una alerta
#   acknowledge_all_alerts()     — Marcar todas 'new' como acknowledged en batch
#   get_reorder_list()           — Productos que necesitan reorden (stock ≤ reorder_point)
#   trigger_alert_generation()   — Llamar a generate_inventory_alerts() RPC
#
# MÉTODOS MODIFICADOS:
#   adjust_stock()               — Ahora usa register_movement() RPC (atómica).
#                                  ANTES: upsert() + add_kardex_entry() separados.
#                                  AHORA: una sola llamada RPC que hace todo.
#                                  MOTIVO: elimina riesgo de inconsistencia si
#                                  un paso falla a mitad de la operación.
#
#   consume_stock()              — Idem. Usa register_movement(movement_type='sale').
#                                  RETRO-COMPAT: acepta tenant_id opcional igual que antes.
#
# MÉTODOS CONSERVADOS (sin cambios):
#   list_inventory(), get_low_stock_alerts(), classify_inventory(),
#   has_low_stock(), initialize_stock(), get_kardex()
#
# INYECCIÓN:
#   __init__ no cambia. BarcodeService no aplica aquí.
#   La Session sigue siendo la fuente de tenant_id.

from session.session import Session
from domain.exceptions import AuthenticationError, ValidationError
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)

# Tipos de movimiento válidos (espejados del CHECK en BD)
MOVEMENT_TYPES = ("sale", "purchase", "adjustment", "return", "damage", "inventory_count")

# Status válidos para alertas
ALERT_STATUSES = ("new", "acknowledged", "resolved", "ignored")


class InventoryService:

    def __init__(self, inventory_repo, event_service=None):
        """
        Args:
            inventory_repo: InventoryRepository (requerido)
            event_service:  EventService        (opcional) — fire & forget
        """
        self.repo          = inventory_repo
        self.event_service = event_service

    # ------------------------------------------------------------------ #
    # Auth guard                                                         #
    # ------------------------------------------------------------------ #

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")
        return Session.tenant_id

    def _current_user_id(self) -> str | None:
        try:
            return Session.current_user.id if Session.current_user else None
        except Exception:
            return None

    # ================================================================== #
    # INVENTARIO — consultas                                             #
    # ================================================================== #

    def list_inventory(self) -> list:
        """
        Inventario básico con JOIN a products.
        Conservado para retro-compatibilidad con DashboardView.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_all(tenant_id)
        return res.data or []

    def get_inventory_full(self) -> list:
        """
        NUEVO F5 — Vista enriquecida vía RPC get_inventory_with_status.

        Retorna por producto:
          product_id, product_name, sku, barcode,
          stock_actual, stock_minimo, stock_maximo,
          reorder_point, reorder_quantity, threshold_id,
          stock_status (ok | warning | critical | out_of_stock)

        DECISIÓN: usa la RPC en lugar de clasificar en Python para que
        la lógica de categorización sea consistente con generate_inventory_alerts().
        """
        tenant_id = self._require_auth()
        try:
            res = self.repo.get_inventory_with_status(tenant_id)
            return res.data or []
        except Exception as e:
            _log.warning("get_inventory_full falló, fallback a list_inventory: %s", e)
            # Fallback: convierte list_inventory al mismo formato
            items = self.list_inventory()
            classified = self.classify_inventory(items)
            result = []
            for status_key, group in classified.items():
                for item in group:
                    p = item.get("products", {})
                    result.append({
                        "product_id":       p.get("id", item.get("product_id")),
                        "product_name":     p.get("name", ""),
                        "sku":              p.get("sku", ""),
                        "barcode":          p.get("barcode", ""),
                        "stock_actual":     item.get("stock_actual", 0),
                        "stock_minimo":     item.get("stock_minimo", 5),
                        "stock_maximo":     100,
                        "reorder_point":    20,
                        "reorder_quantity": 50,
                        "threshold_id":     None,
                        "stock_status":     status_key,
                    })
            return result

    # ================================================================== #
    # ALERTAS LEGACY (mantenidas sin cambios)                           #
    # ================================================================== #

    def get_low_stock_alerts(self) -> list:
        """
        Retro-compat: usa RPC low_stock_products (pre-F5).
        Devuelve items con severity: 'critical' (stock=0) o 'warning'.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_low_stock(tenant_id)
        items = res.data or []
        for item in items:
            stock = item.get("stock_actual", 0)
            item["severity"] = "critical" if stock == 0 else "warning"
        return items

    def classify_inventory(self, items: list) -> dict:
        """Clasifica lista de inventario en ok | warning | critical."""
        ok, warning, critical = [], [], []
        for item in items:
            stock   = item.get("stock_actual", 0)
            minimum = item.get("stock_minimo", 5)
            if stock == 0:
                critical.append({**item, "severity": "critical"})
            elif stock <= minimum:
                warning.append({**item, "severity": "warning"})
            else:
                ok.append({**item, "severity": "ok"})
        return {"ok": ok, "warning": warning, "critical": critical}

    def has_low_stock(self) -> bool:
        """Helper para Dashboard: ¿hay algún producto con stock bajo?"""
        return len(self.get_low_stock_alerts()) > 0

    # ================================================================== #
    # ALERTAS F5 — gestión de inventory_alerts                          #
    # ================================================================== #

    def get_alerts(self, status: str = "new") -> list:
        """
        NUEVO F5 — Lista alertas de inventory_alerts con JOIN a products.

        Args:
            status: 'new' | 'acknowledged' | 'resolved' | 'ignored' | None (todas)

        Cada alerta incluye:
            id, alert_type, stock_actual, stock_minimo, stock_maximo,
            status, generated_at, notes, products.name, products.sku
        """
        tenant_id = self._require_auth()
        res = self.repo.get_alerts(tenant_id, status=status)
        items = res.data or []

        # Enriquecer con severity y label legible
        for item in items:
            stock = item.get("stock_actual", 0)
            min_  = item.get("stock_minimo", 0)
            atype = item.get("alert_type", "")

            item["severity"] = (
                "critical" if (atype == "out_of_stock" or stock == 0)
                else "warning"
            )
            item["alert_label"] = {
                "low_stock":   "Stock bajo",
                "out_of_stock":"Sin stock",
                "overstock":   "Sobre stock",
                "expiring":    "Por vencer",
            }.get(atype, atype)

            # Nombre de producto plano (viene del join)
            p = item.get("products") or {}
            item["product_name"] = p.get("name", "Producto")
            item["product_sku"]  = p.get("sku", "")

        return items

    def get_alerts_count(self, status: str = "new") -> int:
        """
        NUEVO F5 — Conteo rápido para badge en sidebar.
        No lanza excepciones: retorna 0 en caso de error.
        """
        try:
            tenant_id = self._require_auth()
            return self.repo.get_alerts_count(tenant_id, status=status)
        except Exception:
            return 0

    def acknowledge_alert(self, alert_id: str) -> None:
        """
        NUEVO F5 — Marcar alerta como vista (acknowledged).
        Registra acknowledged_by = usuario actual.
        """
        self._require_auth()
        user_id = self._current_user_id()
        self.repo.update_alert_status(alert_id, "acknowledged", user_id=user_id)

    def resolve_alert(self, alert_id: str) -> None:
        """
        NUEVO F5 — Marcar alerta como resuelta.
        Implica que el problema fue atendido (ej: se realizó una compra).
        """
        self._require_auth()
        self.repo.update_alert_status(alert_id, "resolved")

    def ignore_alert(self, alert_id: str) -> None:
        """
        NUEVO F5 — Descartar alerta sin marcarla como resuelta.
        Útil para falsos positivos o configuración incorrecta de thresholds.
        """
        self._require_auth()
        self.repo.update_alert_status(alert_id, "ignored")

    def acknowledge_all_alerts(self) -> int:
        """
        NUEVO F5 — Marcar todas las alertas 'new' del tenant como acknowledged.
        Retorna el conteo de alertas actualizadas.

        CASO DE USO: "Marcar todo como visto" desde el panel de alertas.
        """
        tenant_id = self._require_auth()
        res = self.repo.bulk_update_alerts_status(tenant_id, "acknowledged")
        return len(res.data or [])

    def trigger_alert_generation(self) -> int:
        """
        NUEVO F5 — Llamar a generate_inventory_alerts() RPC.
        Genera alertas para todos los productos del tenant que estén bajo mínimo.
        Retorna cantidad de alertas nuevas generadas.

        CUÁNDO LLAMAR: al abrir el panel de alertas, después de un ajuste de stock,
        o desde un scheduler periódico (cada 15 min).
        """
        tenant_id = self._require_auth()
        try:
            from config.supabase_client import supabase
            res = supabase.rpc(
                "generate_inventory_alerts",
                {"p_tenant_id": tenant_id},
            ).execute()
            return res.data or 0
        except Exception as e:
            _log.warning("generate_inventory_alerts falló: %s", e)
            return 0

    # ================================================================== #
    # THRESHOLDS F5                                                      #
    # ================================================================== #

    def get_thresholds(self) -> list:
        """
        NUEVO F5 — Todos los thresholds del tenant.
        Usado en el panel de configuración de umbrales.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_all_thresholds(tenant_id)
        return res.data or []

    def get_threshold(self, product_id: str) -> dict | None:
        """
        NUEVO F5 — Threshold de un producto específico.
        Retorna None si el producto no tiene threshold configurado.
        """
        self._require_auth()
        res = self.repo.get_threshold(product_id)
        data = res.data or []
        return data[0] if data else None

    def set_threshold(
        self,
        product_id: str,
        stock_minimo: int,
        stock_maximo: int,
        reorder_point: int = None, #type: ignore
        reorder_quantity: int = None,#type: ignore
        alert_on_low_stock: bool = True,
        alert_on_overstock: bool = False,
    ) -> None:
        """
        NUEVO F5 — Crear o actualizar threshold para un producto.

        Args:
            product_id:         UUID del producto.
            stock_minimo:       Nivel mínimo (dispara alerta low_stock).
            stock_maximo:       Nivel máximo (dispara alerta overstock).
            reorder_point:      Stock en el que se sugiere reordenar.
                                Default: stock_minimo + 10.
            reorder_quantity:   Cantidad sugerida a comprar.
                                Default: stock_maximo // 2.
            alert_on_low_stock: Activar alertas de stock bajo.
            alert_on_overstock: Activar alertas de sobre stock.

        VALIDACIONES:
            - stock_minimo < stock_maximo (CHECK en BD)
            - reorder_point >= stock_minimo
            - Todos positivos
        """
        tenant_id = self._require_auth()

        if stock_minimo < 0:
            raise ValidationError("stock_minimo", "No puede ser negativo")
        if stock_maximo <= stock_minimo:
            raise ValidationError("stock_maximo", "Debe ser mayor que stock_minimo")

        rp = reorder_point if reorder_point is not None else stock_minimo + 10
        rq = reorder_quantity if reorder_quantity is not None else stock_maximo // 2

        if rp < stock_minimo:
            raise ValidationError("reorder_point", "Debe ser ≥ stock_minimo")
        if rp >= stock_maximo:
            # Ajuste automático silencioso: no tiene sentido reordenar cuando hay sobre stock
            rp = min(rp, stock_maximo - 1)

        self.repo.upsert_threshold(
            tenant_id=tenant_id,
            product_id=product_id,
            stock_minimo=stock_minimo,
            stock_maximo=stock_maximo,
            reorder_point=rp,
            reorder_quantity=rq,
            alert_on_low_stock=alert_on_low_stock,
            alert_on_overstock=alert_on_overstock,
        )

    # ================================================================== #
    # REORDER LIST F5                                                    #
    # ================================================================== #

    def get_reorder_list(self) -> list:
        """
        NUEVO F5 — Productos que necesitan reorden.

        Un producto necesita reorden si:
            stock_actual <= reorder_point (de su threshold)

        Incluye cantidad_a_comprar = reorder_quantity del threshold.
        Ordenados por urgencia: out_of_stock primero, luego critical, warning.

        IMPLEMENTACIÓN: usa get_inventory_full() y filtra en Python.
        El status 'warning' ya incluye stock <= reorder_point por definición
        del RPC. Los 'critical' y 'out_of_stock' también necesitan reorden.
        """
        items = self.get_inventory_full()
        needs_reorder = [
            item for item in items
            if item.get("stock_status") in ("critical", "out_of_stock", "warning")
        ]
        # Ordenar: out_of_stock → critical → warning
        priority = {"out_of_stock": 0, "critical": 1, "warning": 2, "ok": 3}
        needs_reorder.sort(key=lambda x: priority.get(x.get("stock_status", "ok"), 9))
        return needs_reorder

    # ================================================================== #
    # AJUSTE MANUAL — modificado para usar RPC atómica                  #
    # ================================================================== #

    def adjust_stock(
        self,
        product_id: str,
        nuevo_stock: int,
        stock_minimo: int = None,   # type: ignore  # mantenido por retro-compat
        notas: str = "",
    ) -> dict:
        """
        Ajuste manual de stock desde InventoryView.

        CAMBIO F5: En lugar de llamar a upsert() + add_kardex_entry() por separado,
        ahora calcula el delta y llama a register_movement(movement_type='adjustment').
        La RPC actualiza inventory + kardex + movements_log + alerta en una transacción.

        Si stock_minimo cambió también, actualiza el threshold por separado
        (no entra en la RPC de movimiento porque son tablas distintas).

        Args:
            product_id:   UUID del producto.
            nuevo_stock:  Valor ABSOLUTO del nuevo stock (no un delta).
            stock_minimo: Nuevo umbral mínimo (opcional — actualiza threshold si se pasa).
            notas:        Motivo del ajuste para el kardex.

        Returns:
            {"stock_anterior": int, "stock_posterior": int}
        """
        tenant_id = self._require_auth()

        if nuevo_stock < 0:
            raise ValidationError("nuevo_stock", "El stock no puede ser negativo")

        # Stock actual antes del ajuste
        current_res  = self.repo.get_stock(product_id)
        current_data = (current_res.data or [{}])[0]
        stock_ant    = current_data.get("stock_actual", 0)

        delta = nuevo_stock - stock_ant

        if delta == 0:
            # Nada que cambiar en stock, pero si cambió stock_minimo lo actualizamos
            if stock_minimo is not None:
                self._maybe_update_threshold_minimum(product_id, tenant_id, stock_minimo)
            return {"stock_anterior": stock_ant, "stock_posterior": nuevo_stock}

        nota_auto = notas or f"Ajuste manual: {stock_ant} → {nuevo_stock}"
        user_id   = self._current_user_id()

        try:
            self.repo.register_movement(
                tenant_id=tenant_id,
                product_id=product_id,
                movement_type="adjustment",
                quantity_change=delta,
                reference_type="manual",
                notes=nota_auto,
                created_by=user_id,
            )
        except Exception as e:
            raise Exception(f"No se pudo ajustar el stock: {e}") from e

        # Si también cambió el umbral mínimo, actualizar threshold
        if stock_minimo is not None:
            self._maybe_update_threshold_minimum(product_id, tenant_id, stock_minimo)

        # Fire & forget: evento de stock bajo si aplica
        if self.event_service and nuevo_stock <= (stock_minimo or current_data.get("stock_minimo", 5)):
            try:
                self.event_service.emit(
                    tenant_id, "low_stock",
                    {"product_id": product_id, "stock_actual": nuevo_stock},
                )
            except Exception:
                pass

        _log.info(
            "adjust_stock: producto=%s, %d→%d (delta=%+d)",
            product_id, stock_ant, nuevo_stock, delta
        )
        return {"stock_anterior": stock_ant, "stock_posterior": nuevo_stock}

    def _maybe_update_threshold_minimum(
        self, product_id: str, tenant_id: str, new_minimum: int
    ) -> None:
        """
        Actualiza stock_minimo del threshold si existe.
        Si no existe threshold, no lo crea (eso es responsabilidad de set_threshold).
        """
        try:
            existing = self.get_threshold(product_id)
            if existing:
                self.repo.upsert_threshold(
                    tenant_id=tenant_id,
                    product_id=product_id,
                    stock_minimo=new_minimum,
                    stock_maximo=existing.get("stock_maximo", 100),
                    reorder_point=max(new_minimum, existing.get("reorder_point", new_minimum + 5)),
                    reorder_quantity=existing.get("reorder_quantity", 50),
                    alert_on_low_stock=existing.get("alert_on_low_stock", True),
                    alert_on_overstock=existing.get("alert_on_overstock", False),
                )
        except Exception as e:
            _log.warning("No se pudo actualizar threshold mínimo: %s", e)

    # ================================================================== #
    # CONSUMIR STOCK — modificado para usar RPC atómica                 #
    # ================================================================== #

    def consume_stock(
        self,
        product_id: str,
        quantity: int,
        sale_id: str = None,       # type: ignore
        tenant_id: str = None,     # type: ignore
    ) -> None:
        """
        Decrementa el stock tras una venta. Llamado por SaleService/CreateSaleUseCase.

        CAMBIO F5: Ahora llama a register_movement(movement_type='sale', quantity_change=-quantity).
        La RPC hace inventory + kardex + movements_log + alerta en una transacción.

        RETRO-COMPAT: firma idéntica a la versión pre-F5.
        Si register_movement falla, cae silenciosamente (mismo comportamiento anterior)
        para no revertir una venta ya registrada.
        """
        t_id = tenant_id or Session.tenant_id
        if not t_id:
            return

        try:
            self.repo.register_movement(
                tenant_id=t_id,
                product_id=product_id,
                movement_type="sale",
                quantity_change=-quantity,   # negativo = salida
                reference_type="sale",
                reference_id=sale_id,
                notes=f"Venta — {quantity} unidad(es)",
            )
        except Exception as e:
            _log.warning(
                "consume_stock: no se pudo actualizar inventario para %s: %s",
                product_id, e
            )
            # FALLBACK: intentar método legacy para no perder el kardex
            try:
                stock_ant, stock_post = self.repo.decrement_stock(product_id, quantity)
                self.repo.add_kardex_entry({
                    "tenant_id":       t_id,
                    "product_id":      product_id,
                    "tipo":            "salida",
                    "cantidad":        -quantity,
                    "saldo_anterior":  stock_ant,
                    "saldo_posterior": stock_post,
                    "referencia_id":   sale_id,
                    "referencia_tipo": "sale",
                    "notas":           f"Venta (fallback) — {quantity} unidad(es)",
                })
            except Exception as e2:
                _log.error("consume_stock fallback también falló: %s", e2)

    # ================================================================== #
    # INICIALIZAR STOCK (sin cambios)                                   #
    # ================================================================== #

    def initialize_stock(
        self,
        product_id: str,
        stock_inicial: int = 0,
        stock_minimo: int = 5,
    ) -> None:
        """
        Crea registro de inventory para un producto nuevo.
        Conservado sin cambios — se llama desde ProductService al crear producto.
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

    # ================================================================== #
    # HISTORIAL KARDEX (sin cambios)                                    #
    # ================================================================== #

    def get_kardex(self, product_id: str, limit: int = 50) -> list:
        """Historial de movimientos de un producto vía RPC kardex_by_product."""
        tenant_id = self._require_auth()
        res = self.repo.get_kardex(tenant_id, product_id, limit)
        return res.data or []

    # ================================================================== #
    # MOVEMENTS LOG F5                                                   #
    # ================================================================== #

    def get_movements_log(
        self, product_id: str = None, limit: int = 50   # type: ignore
    ) -> list:
        """
        NUEVO F5 — Historial desde inventory_movements_log (más detallado que kardex).
        Incluye quantity_before/after y movement_type normalizado.
        """
        tenant_id = self._require_auth()
        res = self.repo.get_movements_log(tenant_id, product_id=product_id, limit=limit)
        return res.data or []