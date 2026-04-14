# domain/services/auth_service.py

import uuid
from session.session import Session


class AuthService:

    def __init__(self, auth_repo, tenant_repo):
        self.auth_repo = auth_repo
        self.tenant_repo = tenant_repo

    def register(self, email: str, password: str):
        if not email or not password:
            raise ValueError("Email y contraseña son requeridos")
        if len(password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")

        res = self.auth_repo.sign_up(email, password)
        user = res.user
        if not user:
            raise Exception("Error al crear usuario en auth")

        tenant_id = str(uuid.uuid4())
        tenant = self.tenant_repo.create(
            {"id": tenant_id, "name": f"Negocio de {email.split('@')[0]}"}
        )
        if not tenant.data:
            raise Exception("Error al crear tenant")

        profile = self.auth_repo.create_profile(user.id, tenant_id, role="admin")
        if not profile.data:
            raise Exception("Error al crear perfil")

        return user

    def login(self, email: str, password: str):
        if not email or not password:
            raise ValueError("Email y contraseña son requeridos")

        res = self.auth_repo.sign_in(email, password)
        user = res.user
        if not user:
            raise Exception("Credenciales inválidas")

        profile_res = self.auth_repo.get_profile(user.id)
        if not profile_res.data:
            raise Exception("Usuario sin perfil asociado")

        profile = profile_res.data[0]
        tenant_id = profile.get("tenant_id")
        role = profile.get("role", "employee")

        if not tenant_id:
            raise Exception("Perfil sin tenant_id")

        Session.start(user, tenant_id, role)
        return user

    def logout(self):
        self.auth_repo.sign_out()
        Session.end()