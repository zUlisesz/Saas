from domain.schemas.product_schemas import UpdateProductRequest
from domain.exceptions import AuthenticationError, RepositoryError, ValidationError
from session.session import Session
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class UpdateProductUseCase:

    def __init__(self, product_repo, event_service=None):
        self.product_repo = product_repo
        self.event_service = event_service

    def execute(self, product_id: str, data: dict) -> dict:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")

        try:
            price = float(data["price"]) if "price" in data else None
            cost  = float(data["cost"])  if "cost"  in data else None
        except (ValueError, TypeError):
            raise ValidationError("price", "Precio o costo con formato inválido")

        request = UpdateProductRequest(
            name=data.get("name"),
            price=price,
            cost=cost,
            barcode=data.get("barcode"),
            category_id=data.get("category_id"),
            is_active=data.get("is_active"),
        )
        request.validate()

        res = self.product_repo.update(product_id, request.to_db_dict())
        if not res.data:
            raise RepositoryError("Error al actualizar el producto")

        product = res.data[0]

        # Emitir evento (fire & forget)
        if self.event_service:
            try:
                self.event_service.emit(
                    Session.tenant_id,
                    "product_updated",
                    {"product_id": product_id, **request.to_db_dict()},
                )
            except Exception as e:
                _log.warning("No se pudo emitir evento product_updated: %s", e)

        return product
