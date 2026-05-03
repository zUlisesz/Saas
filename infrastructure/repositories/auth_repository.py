# infrastructure/repositories/auth_repository.py

from config.supabase_client import get_client


class AuthRepository:

    def __init__(self, client=None):
        self._db = client or get_client()

    def sign_up(self, email, password):
        return self._db.auth.sign_up({"email": email, "password": password})

    def sign_in(self, email, password):
        return self._db.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

    def sign_out(self):
        return self._db.auth.sign_out()

    def create_profile(self, user_id, tenant_id, role="admin"):
        try:
            return (
                self._db.table("profiles")
                .insert({"id": user_id, "tenant_id": tenant_id, "role": role})
                .execute()
            )
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para crear perfiles de usuario")
            raise

    def get_profile(self, user_id):
        return (
            self._db.table("profiles")
            .select("*")
            .eq("id", user_id)
            .execute()
        )