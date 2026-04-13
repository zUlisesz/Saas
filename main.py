# main.py

from infrastructure.repositories.auth_repository import AuthRepository
from infrastructure.repositories.product_repository import ProductRepository

from domain.services.auth_service import AuthService
from domain.services.product_service import ProductService

from application.controllers.auth_controller import AuthController
from application.controllers.product_controller import ProductController
from infrastructure.repositories.tenant_repository import TenantRepository


def main():

    auth_repo = AuthRepository()
    product_repo = ProductRepository()
    tenant_repo = TenantRepository()
    auth_service = AuthService(auth_repo, tenant_repo)
    product_service = ProductService(product_repo)

    auth_controller = AuthController(auth_service)
    product_controller = ProductController(product_service)

    while True:
        print("\n1. Register")
        print("2. Login")
        print("3. Crear producto")
        print("4. Listar productos")
        print("5. Salir")

        op = input("Opción: ")

        if op == "1":
            auth_controller.register()
        elif op == "2":
            auth_controller.login()
        elif op == "3":
            product_controller.create()
        elif op == "4":
            product_controller.list()
        elif op == "5":
            break


if __name__ == "__main__":
    main()