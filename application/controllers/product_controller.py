# application/controllers/product_controller.py
#
# ============================================================================
# CAMBIO FASE 5 (patch):
#
# PROBLEMA: create_product() llamaba a ProductService.create_product() que
#   no inicializa inventory. CreateProductUseCase sí lo hace, pero no
#   estaba wired en este controlador → productos nuevos sin fila inventory.
#
# SOLUCIÓN: __init__ acepta create_use_case=None (opcional).
#   create_product() usa el use_case si está disponible, fallback al service.
#   En app.py se pasa create_product_use_case al instanciar el controlador.
#
# RETRO-COMPATIBILIDAD: si no se inyecta use_case, funciona igual que antes.
# Esto evita romper tests existentes que instancian el controlador sin use_case.
#
# FASE 4 (Código de Barras) conservada sin cambios.
# ============================================================================

from domain.exceptions import ValidationError, NexaPOSError


class ProductController:

    def __init__(self, service, app, create_use_case=None):
        """
        Args:
            service:         ProductService (requerido)
            app:             NexaPOS app instance
            create_use_case: CreateProductUseCase (opcional — Fase 5).
                             Si se inyecta, create_product() lo usa en lugar
                             del service directo para garantizar initialize_stock().
        """
        self.service         = service
        self.app             = app
        self._create_uc      = create_use_case   # NUEVO Fase 5

    # ================================================================== #
    # Listado y búsqueda                                                  #
    # ================================================================== #

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

    # ================================================================== #
    # Fase 4 — Barcode                                                   #
    # ================================================================== #

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

    # ================================================================== #
    # CRUD                                                                #
    # ================================================================== #

    def create_product(self, data: dict) -> bool:
        """
        Crea un producto.

        CAMBIO F5: si create_use_case está disponible lo usa (garantiza
        que inventory + threshold se inicialicen). Si no, fallback al service.

        data puede incluir:
            name, price, cost, sku, barcode, barcode_type, category_id,
            stock_inicial (NUEVO), stock_minimo (NUEVO)
        """
        try:
            if self._create_uc is not None:
                # Path preferido: use case inicializa inventory + threshold
                self._create_uc.execute(data)
            else:
                # Fallback legacy (sin initialize_stock)
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

    # ================================================================== #
    # Barcode management (Fase 4)                                        #
    # ================================================================== #

    def assign_barcode(self, product_id: str, barcode: str,
                       barcode_type: str = "ean13") -> bool:
        try:
            self.service.assign_barcode(product_id, barcode, barcode_type)
            self.app.show_snackbar("Código de barras asignado ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def assign_barcodes_bulk(self) -> bool:
        try:
            count = self.service.assign_barcodes_bulk()
            self.app.show_snackbar(f"{count} código(s) asignados ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def get_pending_products(self) -> list:
        try:
            return self.service.get_pending_products()
        except Exception:
            return []

    def get_barcode_stats(self) -> dict:
        try:
            return self.service.get_barcode_stats()
        except Exception:
            return {}