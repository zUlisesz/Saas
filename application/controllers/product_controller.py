# application/controllers/product_controller.py
#
# Fase 4 — Código de Barras:
#   • assign_barcode()       → delega a service.assign_barcode() + snackbar
#   • assign_barcodes_bulk() → delega + snackbar con conteo
#   • get_pending_products() → delega
#   • get_barcode_stats()    → delega
#   • generate_barcode()     → acepta barcode_type opcional

from domain.exceptions import ValidationError, NexaPOSError


class ProductController:

    def __init__(self, service, app):
        self.service = service
        self.app     = app

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

    # ─── Código de barras ─────────────────────────────────────────

    def find_by_barcode(self, barcode: str) -> dict | None:
        try:
            return self.service.find_by_barcode(barcode)
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return None

    def generate_barcode(self, product_id: str, barcode_type: str = "ean13") -> str:
        try:
            return self.service.generate_barcode_for(product_id, barcode_type)
        except Exception:
            return ""

    def assign_barcode(
        self, product_id: str, barcode: str, barcode_type: str = "ean13"
    ) -> bool:
        try:
            self.service.assign_barcode(product_id, barcode, barcode_type)
            self.app.show_snackbar("Código de barras asignado ✓")
            return True
        except ValidationError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False
        except NexaPOSError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False
        except Exception as ex:
            self.app.show_snackbar(f"Error inesperado: {ex}", error=True)
            return False

    def assign_barcodes_bulk(self, barcode_type: str = "ean13") -> int:
        try:
            count = self.service.assign_barcodes_bulk(barcode_type)
            self.app.show_snackbar(f"{count} código(s) asignado(s) ✓")
            return count
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return 0

    def get_pending_products(self) -> list[dict]:
        try:
            return self.service.get_pending_products()
        except Exception:
            return []

    def get_barcode_stats(self) -> dict:
        try:
            return self.service.get_barcode_stats()
        except Exception:
            return {}

    # ─── CRUD ─────────────────────────────────────────────────────

    def create_product(self, data: dict) -> bool:
        try:
            self.service.create_product(data)
            self.app.show_snackbar("Producto creado exitosamente ✓")
            return True
        except ValidationError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False
        except NexaPOSError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False
        except Exception as ex:
            self.app.show_snackbar(f"Error inesperado: {ex}", error=True)
            return False

    def update_product(self, product_id: str, data: dict) -> bool:
        try:
            self.service.update_product(product_id, data)
            self.app.show_snackbar("Producto actualizado ✓")
            return True
        except ValidationError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False
        except NexaPOSError as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False
        except Exception as ex:
            self.app.show_snackbar(f"Error inesperado: {ex}", error=True)
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
