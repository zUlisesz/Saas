# application/controllers/auth_controller.py


class AuthController:

    def __init__(self, service, app):
        self.service = service
        self.app = app

    def login(self, email: str, password: str) -> bool:
        try:
            self.service.login(email, password)
            self.app.navigate_to("dashboard")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def register(self, email: str, password: str) -> bool:
        try:
            self.service.register(email, password)
            self.app.show_snackbar(
                "Registro exitoso. Verifica tu email y luego inicia sesión."
            )
            self.app.navigate_to("login")
            return True
        except Exception as ex:
            self.app.show_snackbar(str(ex), error=True)
            return False

    def logout(self):
        self.service.logout()
        self.app.navigate_to("login")