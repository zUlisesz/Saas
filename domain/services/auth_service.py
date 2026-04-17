# domain/services/auth_service.py
#
# CAMBIOS (refactor arquitectural):
#   • login() usa LoginRequest (DTO) para validar entrada y lanza
#     AuthenticationError en vez de Exception genérica.
#   • register() fue movido al RegisterUserUseCase (application/use_cases/).
#     Se mantiene aquí solo como fallback en caso de que el use case
#     no esté inyectado en el controlador.
#   • _require_auth ya no existe aquí: login/logout no la necesitan.

import uuid

from session.session import Session
from domain.schemas.auth_schemas import LoginRequest, RegisterRequest
from domain.exceptions import AuthenticationError, RepositoryError


class AuthService:

    def __init__(self, auth_repo, tenant_repo):
        self.auth_repo   = auth_repo
        self.tenant_repo = tenant_repo

    # ─── Login ────────────────────────────────────────────────────
    def login(self, email: str, password: str):
        request = LoginRequest(email=email, password=password)
        request.validate()  # lanza ValidationError si datos inválidos

        res  = self.auth_repo.sign_in(email, password)
        user = res.user
        if not user:
            raise AuthenticationError("Credenciales inválidas")

        profile_res = self.auth_repo.get_profile(user.id)
        if not profile_res.data:
            raise AuthenticationError(
                "Usuario sin perfil asociado. Contacta al soporte."
            )

        profile   = profile_res.data[0]
        tenant_id = profile.get("tenant_id")
        role      = profile.get("role", "employee")

        if not tenant_id:
            raise AuthenticationError(
                "Perfil sin tenant asociado. Contacta al soporte."
            )

        Session.start(user, tenant_id, role)
        return user

    # ─── Register (fallback — preferir RegisterUserUseCase) ───────
    def register(self, email: str, password: str):
        """
        Mantiene la implementación original como fallback.
        El flujo recomendado pasa por RegisterUserUseCase, que usa
        excepciones de dominio y es más fácil de testear.
        """
        request = RegisterRequest(email=email, password=password)
        request.validate()

        res  = self.auth_repo.sign_up(email, password)
        user = res.user
        if not user:
            raise AuthenticationError("No se pudo crear el usuario en autenticación")

        tenant_id = str(uuid.uuid4())
        tenant    = self.tenant_repo.create(
            {"id": tenant_id, "name": f"Negocio de {email.split('@')[0]}"}
        )
        if not tenant.data:
            raise RepositoryError("Error al crear el espacio de trabajo")

        profile = self.auth_repo.create_profile(user.id, tenant_id, role="admin")
        if not profile.data:
            raise RepositoryError("Error al crear el perfil de usuario")

        return user

    # ─── Logout ───────────────────────────────────────────────────
    def logout(self):
        self.auth_repo.sign_out()
        Session.end()
