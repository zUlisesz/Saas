# domain/ports/inventory_repository.py
#
# Puerto formal del repositorio de inventario (Ports & Adapters).

from typing import Protocol, runtime_checkable, Optional


@runtime_checkable
class InventoryRepositoryPort(Protocol):
    """Contrato formal del repositorio de inventario."""

    def get_stock(self, product_id: str): ...

    def get_all(self, tenant_id: str): ...

    def get_all_with_alerts(self, tenant_id: str): ...

    def get_low_stock_report(self, tenant_id: str): ...

    def get_low_stock(self, tenant_id: str): ...

    def upsert(self, product_id: str, stock_actual: int, stock_minimo: int = 5): ...

    def decrement_stock(self, product_id: str, quantity: int): ...

    def get_thresholds(self, tenant_id: str): ...

    def get_threshold_by_product(self, tenant_id: str, product_id: str): ...

    def upsert_threshold(self, data: dict): ...

    def get_movements_log(
        self, tenant_id: str, product_id: str, limit: int = 50
    ): ...

    def log_movement(
        self,
        product_id: str,
        movement_type: str,
        quantity: int,
        reference_id: Optional[str] = None,
    ): ...

    def add_kardex_entry(self, entry: dict): ...

    def get_kardex(
        self, tenant_id: str, product_id: str, limit: int = 50
    ): ...
