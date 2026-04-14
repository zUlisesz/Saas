# infrastructure/repositories/product_repository.py

from config.supabase_client import supabase


class ProductRepository:

    def get_all(self, tenant_id):
        return (
            supabase.table("products")
            .select("*, categories(name)")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .order("name")
            .execute()
        )

    def get_by_id(self, product_id):
        return (
            supabase.table("products")
            .select("*, categories(name)")
            .eq("id", product_id)
            .single()
            .execute()
        )

    def search(self, tenant_id, query):
        return (
            supabase.table("products")
            .select("*, categories(name)")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .ilike("name", f"%{query}%")
            .execute()
        )

    def create(self, data):
        return supabase.table("products").insert(data).execute()

    def update(self, product_id, data):
        return (
            supabase.table("products")
            .update(data)
            .eq("id", product_id)
            .execute()
        )

    def soft_delete(self, product_id):
        return (
            supabase.table("products")
            .update({"is_active": False})
            .eq("id", product_id)
            .execute()
        )

    def count(self, tenant_id):
        return (
            supabase.table("products")
            .select("id", count="exact")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .execute()
        )