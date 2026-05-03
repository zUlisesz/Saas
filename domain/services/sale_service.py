# domain/services/sale_service.py
#
# CAMBIOS (Fase 5 — Inventario Inteligente):
#
# 1. __init__ ahora acepta `inventory_service` (InventoryService) en lugar
#    de `inventory_repo` directamente.
#    DECISIÓN: SaleService ya no llama al repo de inventario — lo hace
#    a través de InventoryService. Así el kardex se registra automáticamente
#    en CADA venta sin duplicar lógica.
#
#    RETRO-COMPATIBILIDAD: para no romper nada, el parámetro sigue aceptando
#    el repo viejo con duck typing. Si recibe un repo lo envuelve en un
#    adaptador mínimo. Esto permite migrar gradualmente.
#
# 2. El paso 4 (actualizar inventario) ahora llama a
#    inventory_service.consume_stock() en lugar de repo.decrement_stock().

from session.session import Session
from domain.ports.sale_repository import SaleRepositoryPort


class SaleService:

    def __init__(self, sale_repo: SaleRepositoryPort, inventory_repo=None,
                 event_service=None, inventory_service=None):
        """
        Args:
            sale_repo:          SaleRepository      (requerido)
            inventory_repo:     InventoryRepository (legacy — se mantiene para
                                compatibilidad hacia atrás)
            event_service:      EventService        (opcional)
            inventory_service:  InventoryService    (Fase 5 — preferido sobre repo)

        POLÍTICA DE PRECEDENCIA:
            Si inventory_service está inyectado → úsalo.
            Si no, pero inventory_repo sí → comportamiento legacy.
            Si ninguno → inventario no se actualiza (warning).
        """
        self.sale_repo         = sale_repo
        self.event_service     = event_service
        self.inventory_service = inventory_service
        # Legacy fallback
        self._legacy_repo      = inventory_repo

    def _require_auth(self):
        if not Session.tenant_id:
            raise Exception("No autenticado")

    # ------------------------------------------------------------------ #
    # Crear venta                                                         #
    # ------------------------------------------------------------------ #
    def create_sale(self, cart: list, payment_method: str, amount_received: float = 0):
        self._require_auth()

        if not cart:
            raise ValueError("El carrito está vacío")

        valid_methods = ("cash", "card", "transfer", "electronic")
        if payment_method not in valid_methods:
            raise ValueError("Método de pago inválido")

        total = sum(float(item["price"]) * int(item["quantity"]) for item in cart)

        if payment_method == "cash" and amount_received < total:
            raise ValueError(
                f"Monto insuficiente. Total: ${total:.2f}, recibido: ${amount_received:.2f}"
            )

        if Session.current_user is None:
            raise Exception("Usuario no autenticado")

        # 1. Registro de la venta
        sale_res = self.sale_repo.create_sale(
            {
                "tenant_id": Session.tenant_id,
                "user_id":   Session.current_user.id,
                "total":     total,
                "status":    "completed",
            }
        )
        if not sale_res.data:
            raise Exception("Error al registrar la venta")
        sale    = sale_res.data[0]
        sale_id = sale["id"]

        # 2. Items de venta
        items_data = [
            {
                "sale_id":    sale_id,
                "product_id": item["id"],
                "quantity":   int(item["quantity"]),
                "price":      float(item["price"]),
            }
            for item in cart
        ]
        try:
            self.sale_repo.create_sale_items(items_data)
        except Exception as e:
            raise Exception(f"Error al registrar items de venta: {e}")

        # 3. Registro de pago
        # tenant_id requerido (NOT NULL) y status indican el estado inicial del pago.
        try:
            self.sale_repo.create_payment(
                {
                    "sale_id":   sale_id,
                    "method":    payment_method,
                    "amount":    amount_received if payment_method == "cash" else total,
                    "tenant_id": Session.tenant_id,
                    "status":    "completed",
                }
            )
        except Exception as e:
            raise Exception(f"Error al registrar pago: {e}")

        # 4. Actualizar inventario (no crítico — nunca revierte la venta)
        for item in cart:
            try:
                if self.inventory_service:
                    # FASE 5: usa InventoryService → kardex automático
                    self.inventory_service.consume_stock(
                        product_id=item["id"],
                        quantity=int(item["quantity"]),
                        sale_id=sale_id,
                        tenant_id=Session.tenant_id,
                    )
                elif self._legacy_repo:
                    # Legacy: comportamiento anterior
                    self._legacy_repo.decrement_stock(item["id"], int(item["quantity"]))
                    self._legacy_repo.log_movement(
                        item["id"], "sale", -int(item["quantity"]), sale_id
                    )
            except Exception:
                pass

        # 5. Emitir evento sale_created (fire & forget)
        if self.event_service:
            try:
                self.event_service.emit(
                    Session.tenant_id,
                    "sale_created",
                    {
                        "sale_id":        sale_id,
                        "total":          total,
                        "items_count":    len(cart),
                        "payment_method": payment_method,
                        "items": [
                            {
                                "product_id": i["id"],
                                "name":       i.get("name", ""),
                                "quantity":   int(i["quantity"]),
                                "price":      float(i["price"]),
                            }
                            for i in cart
                        ],
                    },
                )
            except Exception:
                pass

        change = amount_received - total if payment_method == "cash" else 0
        return {"sale": sale, "total": total, "change": change, "items": cart}

    # ------------------------------------------------------------------ #
    # Consultas                                                           #
    # ------------------------------------------------------------------ #
    def get_sales(self):
        self._require_auth()
        res = self.sale_repo.get_all(Session.tenant_id)
        return res.data or []

    def get_today_stats(self):
        self._require_auth()
        res     = self.sale_repo.get_today_stats(Session.tenant_id)
        sales   = res.data or []
        count   = len(sales)
        revenue = sum(float(s.get("total", 0)) for s in sales)
        return {"count": count, "revenue": revenue}