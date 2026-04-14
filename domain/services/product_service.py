# domain/services/product_service.py

from session.session import Session


class ProductService:

    def __init__(self, repo):
        self.repo = repo

    def _require_auth(self):
        if not Session.tenant_id:
            raise Exception("No autenticado")

    def list_products(self):
        self._require_auth()
        res = self.repo.get_all(Session.tenant_id)
        return res.data or []

    def search_products(self, query):
        self._require_auth()
        res = self.repo.search(Session.tenant_id, query)
        return res.data or []

    def create_product(self, data: dict):
        self._require_auth()
        if not data.get("name", "").strip():
            raise ValueError("El nombre es requerido")
        try:
            price = float(data.get("price", 0))
        except (ValueError, TypeError):
            raise ValueError("Precio inválido")
        if price <= 0:
            raise ValueError("El precio debe ser mayor a 0")

        data["name"] = data["name"].strip()
        data["price"] = price
        data["cost"] = float(data.get("cost", 0))
        data["tenant_id"] = Session.tenant_id
        data.setdefault("is_active", True)

        res = self.repo.create(data)
        if not res.data:
            raise Exception("Error al crear producto")
        return res.data[0]

    def update_product(self, product_id: str, data: dict):
        self._require_auth()
        if "name" in data and not data["name"].strip():
            raise ValueError("El nombre es requerido")
        if "price" in data:
            try:
                data["price"] = float(data["price"])
            except (ValueError, TypeError):
                raise ValueError("Precio inválido")

        res = self.repo.update(product_id, data)
        if not res.data:
            raise Exception("Error al actualizar producto")
        return res.data[0]

    def delete_product(self, product_id: str):
        self._require_auth()
        self.repo.soft_delete(product_id)

    def get_count(self):
        self._require_auth()
        res = self.repo.count(Session.tenant_id)
        return res.count or 0