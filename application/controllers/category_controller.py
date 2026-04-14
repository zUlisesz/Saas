# application/controllers/category_controller.py


class CategoryController:

    def __init__(self, service, app):
        self.service = service
        self.app = app

    def get_categories(self):
        try:
            return self.service.list_categories()
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return []

    def create_category(self, name: str) -> bool:
        try:
            self.service.create_category(name)
            self.app.show_snackbar("Categoría creada ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def update_category(self, category_id: str, name: str) -> bool:
        try:
            self.service.update_category(category_id, name)
            self.app.show_snackbar("Categoría actualizada ✓")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def delete_category(self, category_id: str) -> bool:
        try:
            self.service.delete_category(category_id)
            self.app.show_snackbar("Categoría eliminada")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False