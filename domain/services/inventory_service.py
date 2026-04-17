# domain/services/inventory_service.py
#
# NUEVA — Fase 5: Inventario Inteligente
#
# JUSTIFICACIÓN:
# Antes la lógica de inventario estaba dispersa:
#   • SaleService llamaba directamente a inventory_repo
#   • No había una capa de dominio para las reglas de stock
#   • El kardex no existía
#
# Ahora InventoryService centraliza TODA la lógica de inventario:
#   • Ajustes de stock con kardex automático
#   • Validación de stock mínimo
#   • Alertas de stock bajo
#   • Inicialización de stock para productos nuevos
#
# PATRÓN:
#   __init__ recibe inventory_repo y event_service por inyección.
#   SaleService también recibe inventory_service (reemplaza el repo directo).
#
# DECISIÓN ARQUITECTÓNICA IMPORTANTE:
#   SaleService ya llamaba a inventory_repo.decrement_stock() directamente.
#   Ahora lo hará a través de InventoryService.consume_stock().
#   Esto centraliza la lógica de kardex sin duplicar código.

from session.session import Session
from domain.exceptions import AuthenticationError, ValidationError
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class InventoryService:

    def __init__(self, inventory_repo, event_service=None):
        """
        Args:
            inventory_repo: InventoryRepository (requerido)
            event_service:  EventService        (opcional) — para emitir low_stock
        """
        self.repo          = inventory_repo
        self.event_service = event_service

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")
        return Session.tenant_id

    # ------------------------------------------------------------------ #
    # Consultar inventario completo                                      #
    # ------------------------------------------------------------------ #
    def list_inventory(self) -> list:
        tenant_id = self._require_auth()
        res = self.repo.get_all(tenant_id)
        return res.data or []

    # ------------------------------------------------------------------ #
    # Alertas de stock bajo                                              #
    # ------------------------------------------------------------------ #
    def get_low_stock_alerts(self) -> list:
        """
        Devuelve productos con stock_actual <= stock_minimo.
        Cada item incluye severity: "critical" (stock=0) o "warning" (stock<=minimo).
        """
        tenant_id = self._require_auth()
        res = self.repo.get_low_stock(tenant_id)
        items = res.data or []
        for item in items:
            stock = item.get("stock_actual", 0)
            item["severity"] = "critical" if stock == 0 else "warning"
        return items

    def classify_inventory(self, items: list) -> dict:
        """
        Filtra una lista de items de inventario en tres categorías.
        Returns: {ok: [...], warning: [...], critical: [...]}
        """
        ok, warning, critical = [], [], []
        for item in items:
            stock = item.get("stock_actual", 0)
            minimum = item.get("stock_minimo", 5)
            if stock == 0:
                critical.append({**item, "severity": "critical"})
            elif stock <= minimum:
                warning.append({**item, "severity": "warning"})
            else:
                ok.append({**item, "severity": "ok"})
        return {"ok": ok, "warning": warning, "critical": critical}

    def has_low_stock(self) -> bool:
        """Helper rápido para que Dashboard muestre o no el banner de alerta."""
        return len(self.get_low_stock_alerts()) > 0

    # ------------------------------------------------------------------ #
    # Ajuste manual de stock (desde InventoryView)                      #
    # ------------------------------------------------------------------ #
    def adjust_stock(self, product_id: str, nuevo_stock: int,
                     stock_minimo: int = None, notas: str = "") -> dict: #type: ignore
        """
        Ajuste manual de stock con registro kardex.

        Args:
            product_id:   UUID del producto.
            nuevo_stock:  Valor absoluto del nuevo stock (no delta).
            stock_minimo: Nuevo umbral mínimo (opcional).
            notas:        Motivo del ajuste.

        Returns:
            Dict con stock_anterior y stock_posterior.

        DECISIÓN: "ajuste" siempre se registra en kardex como tipo='ajuste'
        sin importar si sube o baja. La dirección se infiere de cantidad
        (positivo = entrada, negativo = salida).
        """
        tenant_id = self._require_auth()

        # Obtener stock actual antes del ajuste
        current_res = self.repo.get_stock(product_id)
        current_data = (current_res.data or [{}])[0]
        stock_ant   = current_data.get("stock_actual", 0)
        stock_min   = stock_minimo if stock_minimo is not None else current_data.get("stock_minimo", 5)

        # Validar
        if nuevo_stock < 0:
            raise ValidationError("nuevo_stock", "El stock no puede ser negativo")

        # Persistir
        self.repo.upsert(product_id, nuevo_stock, stock_min)

        # Registrar en kardex
        delta = nuevo_stock - stock_ant
        self.repo.add_kardex_entry({
            "tenant_id":       tenant_id,
            "product_id":      product_id,
            "tipo":            "ajuste",
            "cantidad":        delta,
            "saldo_anterior":  stock_ant,
            "saldo_posterior": nuevo_stock,
            "referencia_tipo": "manual",
            "notas":           notas or f"Ajuste manual: {stock_ant} → {nuevo_stock}",
        })

        # Emitir evento si quedó con stock bajo (fire & forget)
        if self.event_service and nuevo_stock <= stock_min:
            try:
                self.event_service.emit(
                    tenant_id,
                    "low_stock",
                    {"product_id": product_id, "stock_actual": nuevo_stock,
                     "stock_minimo": stock_min},
                )
            except Exception:
                pass

        return {"stock_anterior": stock_ant, "stock_posterior": nuevo_stock}

    # ------------------------------------------------------------------ #
    # Inicializar stock para un producto nuevo                          #
    # ------------------------------------------------------------------ #
    def initialize_stock(self, product_id: str, stock_inicial: int = 0,
                         stock_minimo: int = 5) -> None:
        """
        Crea el registro de inventario para un producto recién creado.
        Registra en kardex como tipo='inicio'.
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
    # Consumir stock (llamado por SaleService tras una venta)           #
    # ------------------------------------------------------------------ #
    def consume_stock(self, product_id: str, quantity: int,
                      sale_id: str = None, tenant_id: str = None) -> None: #type: ignore
        """
        Decrementa el stock y registra kardex.
        Llamado por SaleService — NO por la vista directamente.

        Args:
            product_id: UUID del producto vendido.
            quantity:   Unidades vendidas (positivo).
            sale_id:    UUID de la venta para referencia cruzada.
            tenant_id:  Opcional; si no se pasa, usa Session.

        DECISIÓN: SaleService llama a este método en vez de llamar
        directamente a inventory_repo. Así centralizamos el kardex
        sin duplicar lógica.
        """
        t_id = tenant_id or Session.tenant_id
        if not t_id:
            return  # Si no hay sesión, ignoramos (venta ya completada)

        try:
            stock_ant, stock_post = self.repo.decrement_stock(product_id, quantity)

            # También log en stock_movements (tabla original intacta)
            self.repo.log_movement(product_id, "sale", -quantity, sale_id)

            # Registrar en kardex
            self.repo.add_kardex_entry({
                "tenant_id":       t_id,
                "product_id":      product_id,
                "tipo":            "salida",
                "cantidad":        -quantity,
                "saldo_anterior":  stock_ant,
                "saldo_posterior": stock_post,
                "referencia_id":   sale_id,
                "referencia_tipo": "sale",
                "notas":           f"Venta — {quantity} unidad(es)",
            })

            # Alerta si quedó con stock bajo
            current_res  = self.repo.get_stock(product_id)
            current_data = (current_res.data or [{}])[0]
            stock_min    = current_data.get("stock_minimo", 5)

            if self.event_service and stock_post <= stock_min:
                try:
                    self.event_service.emit(
                        t_id, "low_stock",
                        {"product_id": product_id,
                         "stock_actual": stock_post,
                         "stock_minimo": stock_min},
                    )
                except Exception:
                    pass

        except Exception as e:
            _log.warning("No se pudo actualizar stock para producto %s: %s", product_id, e)

    # ------------------------------------------------------------------ #
    # Historial kardex de un producto                                   #
    # ------------------------------------------------------------------ #
    def get_kardex(self, product_id: str, limit: int = 50) -> list:
        tenant_id = self._require_auth()
        res = self.repo.get_kardex(tenant_id, product_id, limit)
        return res.data or []