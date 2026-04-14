# application/controllers/product_controller.py

class ProductController:

    def __init__(self, service, app):
        self.service = service
        self.app = app

    def get_products(self):
        try:
            return self.service.list_products()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def search_products(self, query: str):
        try:
            return self.service.search_products(query)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def create_product(self, data: dict) -> bool:
        try:
            self.service.create_product(data)
            self.app.show_snackbar("Producto creado exitosamente ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def update_product(self, product_id: str, data: dict) -> bool:
        try:
            self.service.update_product(product_id, data)
            self.app.show_snackbar("Producto actualizado ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def delete_product(self, product_id: str) -> bool:
        try:
            self.service.delete_product(product_id)
            self.app.show_snackbar("Producto eliminado")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def get_count(self) -> int:
        try:
            return self.service.get_count()
        except Exception:
            return 0