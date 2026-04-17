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
        # Ensure tenant_id is present for RLS policy
        if "tenant_id" not in data or not data["tenant_id"]:
            raise ValueError("tenant_id es requerido para crear una categoría")
        try:
            res = supabase.table("categories").insert(data).execute()
            return res
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para crear categorías en este espacio de trabajo")
            raise

    def update(self, category_id, data):
        try:
            return (
                supabase.table("categories")
                .update(data)
                .eq("id", category_id)
                .execute()
            )
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para actualizar esta categoría")
            raise

    def delete(self, category_id, tenant_id):
        try:
            res = (
                supabase.table("categories")
                .delete()
                .eq("id", category_id)
                .eq("tenant_id", tenant_id)
                .execute()
            )
            if not res.data:
                raise Exception("No se encontró la categoría o no tienes permisos para eliminarla")
            return res
        except Exception as e:
            error_msg = str(e)
            if "foreign key" in error_msg.lower():
                raise Exception("No se puede eliminar: hay productos asignados a esta categoría")
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para eliminar esta categoría")
            raise
