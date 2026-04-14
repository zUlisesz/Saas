# infrastructure/repositories/category_repository.py
from config.supabase_client import supabase


class CategoryRepository:

    def get_all(self, tenant_id):
        return (
            supabase.table("categories")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("name")
            .execute()
        )

    def create(self, data):
        return supabase.table("categories").insert(data).execute()

    def update(self, category_id, data):
        return (
            supabase.table("categories")
            .update(data)
            .eq("id", category_id)
            .execute()
        )

    def delete(self, category_id):
        return (
            supabase.table("categories")
            .delete()
            .eq("id", category_id)
            .execute()
        )