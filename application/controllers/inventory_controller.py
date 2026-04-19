# application/controllers/inventory_controller.py
#
# ============================================================================
# FASE 5 — Inventario Inteligente: métodos nuevos
# ============================================================================
#
# MÉTODOS NUEVOS:
#   get_inventory_full()         — Vista enriquecida con stock_status
#   get_alerts()                 — Listar alertas por status
#   get_alerts_count()           — Badge rápido (retorna int)
#   acknowledge_alert()          — Marcar una alerta como vista
#   resolve_alert()              — Marcar alerta como resuelta + snackbar
#   ignore_alert()               — Descartar alerta + snackbar
#   acknowledge_all_alerts()     — Marcar todas como vistas + snackbar
#   trigger_alerts()             — Ejecutar generate_inventory_alerts() RPC
#   get_thresholds()             — Lista de thresholds del tenant
#   set_threshold()              — Crear/actualizar threshold + snackbar
#   get_reorder_list()           — Productos que necesitan reorden
#   purchase_stock()             — Entrada de stock por compra (tipo='purchase')
#
# MÉTODOS CONSERVADOS (sin cambios):
#   get_inventory(), get_low_stock_alerts(), has_low_stock(),
#   adjust_stock(), get_kardex()
#
# PATRÓN MANTENIDO:
#   Todos los métodos nuevos siguen el mismo patrón:
#     try → llamar al servicio → retornar datos / snackbar de éxito
#     except → self.app.show_snackbar(str(ex), error=True) → retornar vacío/False
#
#   El controlador NO contiene lógica de negocio.
#   El controlador NO llama directamente a repositorios.

class InventoryController:

    def __init__(self, service, app):
        self.service = service
        self.app     = app

    # ================================================================== #
    # INVENTARIO — consultas                                             #
    # ================================================================== #

    def get_inventory(self) -> list:
        """Inventario básico con JOIN a products (retro-compat)."""
        try:
            return self.service.list_inventory()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_inventory_full(self) -> list:
        """
        NUEVO F5 — Vista enriquecida: stock_status + thresholds.
        Usado por InventoryView tabs.
        """
        try:
            return self.service.get_inventory_full()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    # ================================================================== #
    # ALERTAS LEGACY                                                     #
    # ================================================================== #

    def get_low_stock_alerts(self) -> list:
        """Retro-compat: usa RPC low_stock_products."""
        try:
            return self.service.get_low_stock_alerts()
        except Exception:
            return []

    def has_low_stock(self) -> bool:
        """Badge rápido para Dashboard y sidebar."""
        try:
            return self.service.has_low_stock()
        except Exception:
            return False

    # ================================================================== #
    # ALERTAS F5                                                         #
    # ================================================================== #

    def get_alerts(self, status: str = "new") -> list:
        """
        NUEVO F5 — Alertas de inventory_alerts.

        Args:
            status: 'new' | 'acknowledged' | 'resolved' | 'ignored' | None (todas)
        """
        try:
            return self.service.get_alerts(status=status)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_alerts_count(self, status: str = "new") -> int:
        """NUEVO F5 — Conteo sin lanzar excepciones. Para badges."""
        try:
            return self.service.get_alerts_count(status=status)
        except Exception:
            return 0

    def acknowledge_alert(self, alert_id: str) -> bool:
        """NUEVO F5 — Marcar una alerta como vista. Sin snackbar (acción silenciosa)."""
        try:
            self.service.acknowledge_alert(alert_id)
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def resolve_alert(self, alert_id: str) -> bool:
        """NUEVO F5 — Marcar una alerta como resuelta."""
        try:
            self.service.resolve_alert(alert_id)
            self.app.show_snackbar("Alerta marcada como resuelta ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def ignore_alert(self, alert_id: str) -> bool:
        """NUEVO F5 — Descartar una alerta."""
        try:
            self.service.ignore_alert(alert_id)
            self.app.show_snackbar("Alerta ignorada")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def acknowledge_all_alerts(self) -> int:
        """
        NUEVO F5 — Marcar todas las alertas 'new' como acknowledged.
        Retorna el conteo de alertas actualizadas.
        """
        try:
            count = self.service.acknowledge_all_alerts()
            self.app.show_snackbar(f"{count} alerta(s) marcadas como revisadas ✓")
            return count
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return 0

    def trigger_alerts(self) -> int:
        """
        NUEVO F5 — Ejecutar generate_inventory_alerts() RPC.
        Retorna cuántas alertas nuevas se generaron.
        """
        try:
            count = self.service.trigger_alert_generation()
            if count > 0:
                self.app.show_snackbar(f"{count} alerta(s) nueva(s) generada(s) ✓")
            return count
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return 0

    # ================================================================== #
    # THRESHOLDS F5                                                      #
    # ================================================================== #

    def get_thresholds(self) -> list:
        """NUEVO F5 — Todos los thresholds del tenant."""
        try:
            return self.service.get_thresholds()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_threshold(self, product_id: str) -> dict | None:
        """NUEVO F5 — Threshold de un producto específico."""
        try:
            return self.service.get_threshold(product_id)
        except Exception:
            return None

    def set_threshold(
        self,
        product_id: str,
        stock_minimo: int,
        stock_maximo: int,
        reorder_point: int = None,  # type: ignore
        reorder_quantity: int = None,  # type: ignore
        alert_on_low_stock: bool = True,
        alert_on_overstock: bool = False,
    ) -> bool:
        """
        NUEVO F5 — Crear o actualizar threshold.
        Muestra snackbar de éxito/error.
        """
        try:
            self.service.set_threshold(
                product_id=product_id,
                stock_minimo=stock_minimo,
                stock_maximo=stock_maximo,
                reorder_point=reorder_point,
                reorder_quantity=reorder_quantity,
                alert_on_low_stock=alert_on_low_stock,
                alert_on_overstock=alert_on_overstock,
            )
            self.app.show_snackbar("Umbral de stock actualizado ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    # ================================================================== #
    # REORDER F5                                                         #
    # ================================================================== #

    def get_reorder_list(self) -> list:
        """NUEVO F5 — Productos que necesitan reorden (stock ≤ reorder_point)."""
        try:
            return self.service.get_reorder_list()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    # ================================================================== #
    # AJUSTE DE STOCK                                                    #
    # ================================================================== #

    def adjust_stock(
        self,
        product_id: str,
        nuevo_stock: int,
        stock_minimo: int = None,  # type: ignore
        notas: str = "",
    ) -> bool:
        """
        Ajuste manual de stock (modificado F5: usa RPC atómica).
        Muestra snackbar de éxito.
        """
        try:
            self.service.adjust_stock(product_id, nuevo_stock, stock_minimo, notas)
            self.app.show_snackbar("Stock actualizado ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def purchase_stock(
        self,
        product_id: str,
        quantity: int,
        notas: str = "",
        tenant_id: str = None,  # type: ignore
    ) -> bool:
        """
        NUEVO F5 — Entrada de stock por compra/recepción de mercancía.
        Usa register_movement(movement_type='purchase', quantity_change=+quantity).

        Diferente a adjust_stock porque:
          - adjust_stock: valor ABSOLUTO → calcula delta internamente
          - purchase_stock: cantidad POSITIVA a SUMAR al stock actual
        """
        try:
            from session.session import Session
            t_id = tenant_id or Session.tenant_id
            if not t_id:
                raise Exception("No hay sesión activa")
            if quantity <= 0:
                raise ValueError("La cantidad debe ser mayor a 0")

            self.service.repo.register_movement(
                tenant_id=t_id,
                product_id=product_id,
                movement_type="purchase",
                quantity_change=quantity,
                reference_type="purchase",
                notes=notas or f"Entrada de mercancía — {quantity} unidad(es)",
                created_by=self.service._current_user_id(),
            )
            self.app.show_snackbar(f"+{quantity} unidades registradas ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    # ================================================================== #
    # KARDEX                                                             #
    # ================================================================== #

    def get_kardex(self, product_id: str, limit: int = 50) -> list:
        """Historial kardex de un producto."""
        try:
            return self.service.get_kardex(product_id, limit)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_movements_log(self, product_id: str = None, limit: int = 50) -> list:  # type: ignore
        """NUEVO F5 — Historial desde movements_log (más detallado)."""
        try:
            return self.service.get_movements_log(product_id=product_id, limit=limit)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []