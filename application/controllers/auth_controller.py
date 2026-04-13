# application/controllers/auth_controller.py

class AuthController:

    def __init__(self, service):
        self.service = service

    def register(self):
        email = input("Email: ")
        password = input("Password: ")

        self.service.register(email, password)

    def login(self):
        email = input("Email: ")
        password = input("Password: ")

        self.service.login(email, password)