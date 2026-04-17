from domain.schemas.product_schemas import CreateProductRequest
from domain.exceptions import AuthenticationError, RepositoryError
from session.session import Session
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class CreateProductUseCase:

    def __init__(self, product_repo, inventory_service=None, event_service=None):
        self.product_repo      = product_repo
        self.inventory_service = inventory_service
        self.event_service     = event_service

    def execute(self, data: dict) -> dict:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")

        try:
            price = float(data.get("price", 0))
            cost  = float(data.get("cost", 0))
        except (ValueError, TypeError):
            from domain.exceptions import ValidationError
            raise ValidationError("price", "Precio o costo con formato inválido")

        request = CreateProductRequest(
            name=data.get("name", ""),
            price=price,
            cost=cost,
            barcode=data.get("barcode"),
            category_id=data.get("category_id"),
            is_active=data.get("is_active", True),
        )
        request.validate()

        res = self.product_repo.create(request.to_db_dict(Session.tenant_id))
        if not res.data:
            raise RepositoryError("Error al crear el producto en base de datos")

        product    = res.data[0]
        product_id = product["id"]

        # Inicializar stock (fire & forget)
        if self.inventory_service:
            try:
                self.inventory_service.initialize_stock(
                    product_id,
                    stock_inicial=int(data.get("stock_inicial", 0)),
                    stock_minimo=int(data.get("stock_minimo", 5)),
                )
            except Exception as e:
                _log.warning("No se pudo inicializar stock para %s: %s", product_id, e)

        # Emitir evento (fire & forget)
        if self.event_service:
            try:
                self.event_service.emit(
                    Session.tenant_id,
                    "product_created",
                    {"product_id": product_id, "name": request.name, "price": request.price},
                )
            except Exception as e:
                _log.warning("No se pudo emitir evento product_created: %s", e)

        return product
