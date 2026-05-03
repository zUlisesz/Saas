# tests/unit/test_repo_ports.py
#
# Verifica que las implementaciones concretas cumplen con sus Ports
# (Protocol @runtime_checkable). Si alguien añade un método al Port
# y olvida añadirlo al repositorio, este test falla antes del runtime.
#
# Tests: 3

from unittest.mock import MagicMock


class TestRepoPorts:

    def test_sale_repo_cumple_port(self):
        from domain.ports.sale_repository import SaleRepositoryPort
        from infrastructure.repositories.sale_repository import SaleRepository
        repo = SaleRepository(client=MagicMock())
        assert isinstance(repo, SaleRepositoryPort), \
            "SaleRepository no cumple SaleRepositoryPort — método faltante"

    def test_product_repo_cumple_port(self):
        from domain.ports.product_repository import ProductRepositoryPort
        from infrastructure.repositories.product_repository import ProductRepository
        repo = ProductRepository(client=MagicMock())
        assert isinstance(repo, ProductRepositoryPort), \
            "ProductRepository no cumple ProductRepositoryPort — método faltante"

    def test_inventory_repo_cumple_port(self):
        from domain.ports.inventory_repository import InventoryRepositoryPort
        from infrastructure.repositories.inventory_repository import InventoryRepository
        repo = InventoryRepository(client=MagicMock())
        assert isinstance(repo, InventoryRepositoryPort), \
            "InventoryRepository no cumple InventoryRepositoryPort — método faltante"
