# domain/services/category_service.py

from session.session import Session


class CategoryService:

    def __init__(self, repo):
        self.repo = repo

    def _require_auth(self):
        if not Session.tenant_id:
            raise Exception("No autenticado")

    def list_categories(self):
        self._require_auth()
        res = self.repo.get_all(Session.tenant_id)
        return res.data or []

    def create_category(self, name: str):
        self._require_auth()
        name = name.strip()
        if not name:
            raise ValueError("El nombre es requerido")
        res = self.repo.create({"name": name, "tenant_id": Session.tenant_id})
        if not res.data:
            raise Exception("Error al crear categoría")
        return res.data[0]

    def update_category(self, category_id: str, name: str):
        self._require_auth()
        name = name.strip()
        if not name:
            raise ValueError("El nombre es requerido")
        res = self.repo.update(category_id, {"name": name})
        if not res.data:
            raise Exception("Error al actualizar categoría")
        return res.data[0]

    def delete_category(self, category_id: str):
        self._require_auth()
        self.repo.delete(category_id)