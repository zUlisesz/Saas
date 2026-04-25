# application/controllers/inventory_controller.py
#
# FASE 5 — ACTUALIZACIÓN (22 Abril 2026)
#
# CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
#
#   1. __init__ recibe alert_service (InventoryAlertService) como segundo
#      servicio. OPCIONAL — si no se provee, los métodos de alerta
#      retornan valores vacíos/seguros (degradación elegante).
#
#   2. NUEVO: get_alerts(status) — delega a alert_service.get_alerts()
#
#   3. NUEVO: get_alert_count() — conteo rápido para badge del sidebar
#
#   4. NUEVO: acknowledge_alert(alert_id) — reconocer alerta
#
#   5. NUEVO: resolve_alert(alert_id, notes) — resolver alerta
#
#   6. NUEVO: ignore_alert(alert_id) — descartar alerta
#
#   7. NUEVO: get_alert_summary() — para banner del dashboard
#
#   8. NUEVO: get_thresholds() — para UI de configuración de umbrales
#
#   9. NUEVO: update_threshold(...) — actualizar min/max/reorder
#
#   10. NUEVO: generate_alerts() — trigger manual + refresh
#
# MÉTODOS CONSERVADOS (sin cambios):
#   get_inventory, get_low_stock_alerts, has_low_stock,
#   adjust_stock, get_kardex
#
# PRINCIPIO: ninguna lógica de negocio aquí.
# Cada método = try/except + delegar al servicio + snackbar si falla.

from domain.exceptions import AuthenticationError


class InventoryController:

    def __init__(self, service, app, alert_service=None):
        """
        Args:
            service:       InventoryService     (requerido)
            app:           App instance          (requerido — para show_snackbar)
            alert_service: InventoryAlertService (opcional — Fase 5)

        DECISIÓN: alert_service es opcional para mantener compatibilidad
        si alguien instancia InventoryController sin el nuevo servicio
        (ej: tests que aún no migraron).
        """
        self.service       = service
        self.app           = app
        self.alert_service = alert_service

    # ------------------------------------------------------------------ #
    # Inventario                                                          #
    # ------------------------------------------------------------------ #

    def get_inventory(self) -> list:
        """
        Lista completa de inventario con stock_status y active_alerts.
        Usa la nueva RPC get_inventory_with_alerts — datos aplanados.
        """
        try:
            return self.service.list_inventory()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_low_stock_alerts(self) -> list:
        """
        Productos con stock bajo. Para el banner de InventoryView.
        Ahora usa get_low_stock_report RPC — más datos que antes.
        """
        try:
            return self.service.get_low_stock_alerts()
        except Exception:
            return []

    def has_low_stock(self) -> bool:
        try:
            return self.service.has_low_stock()
        except Exception:
            return False

    def adjust_stock(self, product_id: str, nuevo_stock: int,
                     stock_minimo: int = None, notas: str = "") -> bool: #type: ignore
        """
        Ajuste manual de stock.
        Tras el ajuste, dispara generate_alerts() para actualizar alertas.
        """
        try:
            self.service.adjust_stock(product_id, nuevo_stock, stock_minimo, notas)
            self.app.show_snackbar("Stock actualizado ✓")
            # Regenerar alertas tras el ajuste
            self.generate_alerts()
            return True
        except AuthenticationError:
            self.app.navigate_to("login")
            return False
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def get_kardex(self, product_id: str, limit: int = 50) -> list:
        try:
            return self.service.get_kardex(product_id, limit)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_movements_log(self, product_id: str, limit: int = 50) -> list:
        """Historial extendido (inventory_movements_log)."""
        try:
            return self.service.get_movements_log(product_id, limit)
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Alertas (NUEVO — Fase 5)                                           #
    # ------------------------------------------------------------------ #

    def get_alerts(self, status: str = None) -> list: #type: ignore
        """
        Retorna alertas del tenant.
        status=None → todas | 'new' | 'acknowledged' | 'resolved' | 'ignored'
        """
        if not self.alert_service:
            return []
        try:
            return self.alert_service.get_alerts(status=status)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_new_alerts(self) -> list:
        """Alertas sin revisar. Atajo para InventoryView."""
        return self.get_alerts(status="new")

    def get_alert_count(self) -> int:
        """
        Conteo rápido para el badge del sidebar.
        No muestra snackbar — falla silenciosamente.
        """
        if not self.alert_service:
            return 0
        return self.alert_service.count_new()

    def get_alert_summary(self) -> dict:
        """
        Resumen para el banner del dashboard.
        Retorna {total_new, critical, warning, top_critical}.
        """
        if not self.alert_service:
            return {"total_new": 0, "critical": 0, "warning": 0, "top_critical": []}
        try:
            return self.alert_service.get_summary()
        except Exception:
            return {"total_new": 0, "critical": 0, "warning": 0, "top_critical": []}

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Reconoce una alerta (new → acknowledged).
        Muestra snackbar de confirmación.
        """
        if not self.alert_service:
            return False
        try:
            self.alert_service.acknowledge(alert_id)
            self.app.show_snackbar("Alerta reconocida ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def resolve_alert(self, alert_id: str, notes: str = None) -> bool: #type: ignore
        """
        Resuelve una alerta. Muestra snackbar de confirmación.
        """
        if not self.alert_service:
            return False
        try:
            self.alert_service.resolve(alert_id, notes)
            self.app.show_snackbar("Alerta resuelta ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def ignore_alert(self, alert_id: str) -> bool:
        """Descarta una alerta sin resolverla."""
        if not self.alert_service:
            return False
        try:
            self.alert_service.ignore(alert_id)
            self.app.show_snackbar("Alerta descartada")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def generate_alerts(self) -> int:
        """
        Dispara generate_inventory_alerts() en BD.
        Retorna el número de alertas generadas.
        No muestra snackbar — operación de background.
        """
        if not self.alert_service:
            return 0
        try:
            return self.alert_service.generate_alerts()
        except Exception:
            return 0

    # ------------------------------------------------------------------ #
    # Thresholds (NUEVO — Fase 5)                                        #
    # ------------------------------------------------------------------ #

    def get_thresholds(self) -> list:
        """
        Lee todos los umbrales del tenant.
        Para la UI de configuración en InventoryView.
        """
        try:
            return self.service.get_thresholds()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_threshold_for_product(self, product_id: str) -> dict:
        """Umbral de un producto específico (con defaults si no existe)."""
        try:
            return self.service.get_threshold_for_product(product_id)
        except Exception:
            return {
                "stock_minimo": 5, "stock_maximo": 100,
                "reorder_point": 10, "reorder_quantity": 50,
            }

    def update_threshold(
        self,
        product_id: str,
        stock_minimo: int,
        stock_maximo: int,
        reorder_point: int = None, #type: ignore
        reorder_quantity: int = None, #type: ignore
        alert_on_low_stock: bool = True,
        alert_on_overstock: bool = False,
    ) -> bool:
        """
        Actualiza el threshold de un producto.
        Las validaciones de dominio ocurren en InventoryService.
        """
        try:
            self.service.update_threshold(
                product_id, stock_minimo, stock_maximo,
                reorder_point, reorder_quantity,
                alert_on_low_stock, alert_on_overstock,
            )
            self.app.show_snackbar("Umbrales actualizados ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    # ------------------------------------------------------------------ #
    # Aliases y métodos adicionales (usados por InventoryView)            #
    # ------------------------------------------------------------------ #

    def get_inventory_full(self) -> list:
        """Alias de get_inventory() para compatibilidad con InventoryView."""
        return self.get_inventory()

    def get_alerts_count(self, status: str = "new") -> int:
        """Conteo de alertas por status. Para badges en la vista."""
        if not self.alert_service:
            return 0
        try:
            return len(self.alert_service.get_alerts(status=status))
        except Exception:
            return 0

    def get_reorder_list(self) -> list:
        """Productos con stock_actual <= reorder_point (necesitan reposición)."""
        try:
            inventory = self.service.list_inventory()
            return [
                item for item in inventory
                if item.get("stock_actual", 0) <= item.get("reorder_point", 0)
                and item.get("reorder_point", 0) > 0
            ]
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def trigger_alerts(self) -> int:
        """Alias de generate_alerts() para compatibilidad con InventoryView."""
        return self.generate_alerts()

    def acknowledge_all_alerts(self) -> int:
        """Reconoce todas las alertas nuevas. Retorna la cantidad reconocida."""
        if not self.alert_service:
            return 0
        try:
            alerts = self.alert_service.get_alerts(status="new")
            count = 0
            for alert in alerts:
                try:
                    self.alert_service.acknowledge(alert.get("id", ""))
                    count += 1
                except Exception:
                    pass
            if count:
                self.app.show_snackbar(f"{count} alerta(s) marcadas como vistas ✓")
            return count
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return 0

    def purchase_stock(self, product_id: str, qty: int, notas: str = "") -> bool:
        """Entrada de compra: suma qty al stock actual y registra en kardex."""
        try:
            inventory = self.service.list_inventory()
            item = next((i for i in inventory if i.get("product_id") == product_id), None)
            current = item.get("stock_actual", 0) if item else 0
            note = f"Entrada de compra — {qty} unidad(es). {notas}".strip().rstrip(".")
            self.service.adjust_stock(product_id, current + qty, notas=note)
            self.app.show_snackbar(f"Entrada de +{qty} unidades registrada ✓")
            self.generate_alerts()
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def set_threshold(
        self,
        product_id: str,
        stock_minimo: int,
        stock_maximo: int,
        reorder_point: int = None, #type: ignore
        reorder_quantity: int = None, #type: ignore
        alert_on_low_stock: bool = True,
        alert_on_overstock: bool = False,
    ) -> bool:
        """Alias de update_threshold() para compatibilidad con InventoryView."""
        return self.update_threshold(
            product_id, stock_minimo, stock_maximo,
            reorder_point, reorder_quantity,
            alert_on_low_stock, alert_on_overstock,
        )