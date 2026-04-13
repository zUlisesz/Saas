# infrastructure/repositories/auth_repository.py

from config.supabase_client import supabase

class AuthRepository:

    def sign_up(self, email, password):
        return supabase.auth.sign_up({
        "email": email,
        "password": password
    })

    def sign_in(self, email, password):
        return supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

    def create_profile(self, user_id, tenant_id):
        return supabase.table("profiles").insert({
            "id": user_id,
            "tenant_id": tenant_id
        }).execute()
    
    def get_profile(self, user_id):
        return supabase.table("profiles")\
            .select("*")\
            .eq("id", user_id)\
            .execute()