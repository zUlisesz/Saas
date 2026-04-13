# infrastructure/repositories/tenant_repository.py

from config.supabase_client import supabase

class TenantRepository:

    def create(self, data):
        return supabase.table("tenants")\
            .insert(data)\
            .execute()