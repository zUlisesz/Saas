# domain/ports/sale_repository.py
#
# Puerto formal del repositorio de ventas (Ports & Adapters).
#
# PROPÓSITO:
#   Formaliza el contrato que SaleRepository debe cumplir.
#   El use case (CreateSaleUseCase) y el servicio dependen de este Port,
#   no de la implementación concreta con Supabase.
#
# BENEFICIO:
#   Si en el futuro se cambia Supabase por SQLite offline o una API REST,
#   solo hay que escribir una nueva clase que cumpla este protocolo.
#   El use case no cambia.

from typing import Protocol, runtime_checkable


@runtime_checkable
class SaleRepositoryPort(Protocol):
    """Contrato formal del repositorio de ventas."""

    def create_sale(self, sale_data: dict): ...

    def create_sale_items(self, items: list): ...

    def create_payment(self, payment_data: dict): ...

    def get_all(self, tenant_id: str, limit: int = 50): ...

    def get_today_stats(self, tenant_id: str): ...

    def get_by_id(self, sale_id: str): ...

    def delete_sale(self, sale_id: str) -> None: ...
