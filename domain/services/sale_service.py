# domain/services/sale_service.py

from session.session import Session


class SaleService:

    def __init__(self, sale_repo, inventory_repo):
        self.sale_repo = sale_repo
        self.inventory_repo = inventory_repo

    def _require_auth(self):    
        if not Session.tenant_id:
            raise Exception("No autenticado")

    def create_sale(self, cart: list, payment_method: str, amount_received: float = 0):
        """
        cart: [{"id": uuid, "name": str, "price": float, "quantity": int}]
        payment_method: "cash" | "card" | "transfer"
        """
        self._require_auth()

        if not cart:
            raise ValueError("El carrito está vacío")

        valid_methods = ("cash", "card", "transfer")
        if payment_method not in valid_methods:
            raise ValueError("Método de pago inválido")

        total = sum(float(item["price"]) * int(item["quantity"]) for item in cart)

        if payment_method == "cash" and amount_received < total:
            raise ValueError(
                f"Monto insuficiente. Total: ${total:.2f}, recibido: ${amount_received:.2f}"
            )

        # 1. Create sale record
        if Session.current_user is None:
            raise Exception("Usuario no autenticado")
        
        sale_res = self.sale_repo.create_sale(
            {
                "tenant_id": Session.tenant_id,
                "user_id": Session.current_user.id,
                "total": total,
                "status": "completed",
            }
        )
        if not sale_res.data:
            raise Exception("Error al registrar la venta")
        sale = sale_res.data[0]
        sale_id = sale["id"]

        # 2. Create sale items
        items_data = [
            {
                "sale_id": sale_id,
                "product_id": item["id"],
                "quantity": int(item["quantity"]),
                "price": float(item["price"]),
            }
            for item in cart
        ]
        try:
            self.sale_repo.create_sale_items(items_data)
        except Exception as e:
            raise Exception(f"Error al registrar items de venta: {str(e)}")

        # 3. Create payment record
        try:
            self.sale_repo.create_payment(
                {
                    "sale_id": sale_id,
                    "method": payment_method,
                    "amount": amount_received if payment_method == "cash" else total,
                }
            )
        except Exception as e:
            raise Exception(f"Error al registrar pago: {str(e)}")

        # 4. Update inventory & log movements
        for item in cart:
            try:
                self.inventory_repo.decrement_stock(item["id"], int(item["quantity"]))
                self.inventory_repo.log_movement(
                    item["id"], "sale", -int(item["quantity"]), sale_id
                )
            except Exception:
                pass  # Don't fail the sale if inventory update fails

        change = amount_received - total if payment_method == "cash" else 0
        return {"sale": sale, "total": total, "change": change}

    def get_sales(self):
        self._require_auth()
        res = self.sale_repo.get_all(Session.tenant_id)
        return res.data or []

    def get_today_stats(self):
        self._require_auth()
        res = self.sale_repo.get_today_stats(Session.tenant_id)
        sales = res.data or []
        count = len(sales)
        revenue = sum(float(s.get("total", 0)) for s in sales)
        return {"count": count, "revenue": revenue}