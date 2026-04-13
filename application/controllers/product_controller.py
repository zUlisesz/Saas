# application/controllers/product_controller.py

class ProductController:

    def __init__(self, service):
        self.service = service

    def create(self):
        name = input("Nombre: ")
        price = input("Precio: ")

        data = {
            "name": name,
            "price": price
        }

        res = self.service.create_product(data)
        print(res.data)

    def list(self):
        res = self.service.list_products()
        print("Productos:\n")
        for element in res.data:
            print(f"id: {element['id']} - Nombre: {element['name']} - Precio: {element['price']}")