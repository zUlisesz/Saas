# domain/services/auth_service.py

from session.session import Session
from infrastructure.repositories.auth_repository import AuthRepository
from infrastructure.repositories.tenant_repository import TenantRepository
import uuid

class AuthService:

    def __init__(self, auth_repo, tenant_repo):
        self.auth_repo = auth_repo
        self.tenant_repo = tenant_repo

    def register(self, email, password):

        # 1. Crear usuario (auth)
        res = self.auth_repo.sign_up(email, password)
        user = res.user

        if not user:
            raise Exception("Error en auth")

        # 2. Crear tenant
        tenant_id = str(uuid.uuid4())

        tenant = self.tenant_repo.create({
            "id": tenant_id,
            "name": f"Tenant de {email}"
        })

        if not tenant.data:
            raise Exception("Error creando tenant")

        # 3. Crear profile
        profile = self.auth_repo.create_profile(user.id, tenant_id)

        if not profile.data:
            raise Exception("Error creando profile")

        print("[AUTH] Registro completo")

        return user

    def login(self, email, password):
        res = self.auth_repo.sign_in(email, password)

        user = res.user
        if not user:
            raise Exception("Credenciales inválidas")

        # Obtener profile
        profile = self.auth_repo.get_profile(user.id)

        # 🔥 VALIDACIÓN CLAVE
        if not profile.data or len(profile.data) == 0:
            raise Exception("Usuario sin perfil asociado (inconsistencia)")

        profile_data = profile.data[0]
        print(type(profile_data))

        tenant_id = profile_data.get("tenant_id")

        if not tenant_id:
            raise Exception("Perfil sin tenant_id (dato corrupto)")

        # 🔐 Iniciar sesión
        Session.start(user, tenant_id)

        return user