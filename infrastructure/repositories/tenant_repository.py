# infrastructure/repositories/tenant_repository.py

from config.supabase_client import supabase

class TenantRepository:

    def create(self, data):
        return supabase.table("tenants").insert(data).execute()

    def get_by_id(self, tenant_id):
        return (
            supabase.table("tenants")
            .select("*")
            .eq("id", tenant_id)
            .single()
            .execute()
        )