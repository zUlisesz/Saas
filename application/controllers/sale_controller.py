# application/controllers/sale_controller.py


class SaleController:

    def __init__(self, service, app):
        self.service = service
        self.app = app

    def create_sale(self, cart: list, payment_method: str, amount_received: float = 0):
        try:
            result = self.service.create_sale(cart, payment_method, amount_received)
            self.app.show_snackbar("¡Venta registrada exitosamente! ✓")
            return result
        
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return None

    def get_sales(self):
        try:
            return self.service.get_sales()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def get_today_stats(self):
        try:
            return self.service.get_today_stats()
        except Exception:
            return {"count": 0, "revenue": 0.0}