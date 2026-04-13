# domain/services/product_service.py

from session.session import Session

class ProductService:

    def __init__(self, repo):
        self.repo = repo

    def create_product(self, data):
        if not Session.tenant_id:
            raise Exception("No autenticado")

        if not data.get("name"):
            raise ValueError("Nombre requerido")

        if float(data["price"]) <= 0:
            raise ValueError("Precio inválido")

        data["tenant_id"] = Session.tenant_id

        return self.repo.create(data)

    def list_products(self):
        if not Session.tenant_id:
            raise Exception("No autenticado")

        return self.repo.get_all(Session.tenant_id)