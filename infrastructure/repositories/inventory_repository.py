# infrastructure/repositories/inventory_repository.py

from config.supabase_client import supabase

class InventoryRepository:

    def get_stock(self, product_id):
        return (
            supabase.table("inventory")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )

    def get_all(self, tenant_id):
        return (
            supabase.table("inventory")
            .select("*, products!inner(id, name, sku, tenant_id)")
            .eq("products.tenant_id", tenant_id)
            .execute()
        )

    def upsert(self, product_id, stock_actual, stock_minimo=5):
        return (
            supabase.table("inventory")
            .upsert(
                {
                    "product_id": product_id,
                    "stock_actual": stock_actual,
                    "stock_minimo": stock_minimo,
                },
                on_conflict="product_id",
            )
            .execute()
        )

    def decrement_stock(self, product_id, quantity):
        current = self.get_stock(product_id)
        if current.data:
            new_stock = max(0, current.data[0]["stock_actual"] - quantity)
            return self.upsert(product_id, new_stock, current.data[0]["stock_minimo"])

    def log_movement(self, product_id, movement_type, quantity, reference_id=None):
        return (
            supabase.table("stock_movements")
            .insert(
                {
                    "product_id": product_id,
                    "type": movement_type,
                    "quantity": quantity,
                    "reference_id": reference_id,
                }
            )
            .execute()
        )