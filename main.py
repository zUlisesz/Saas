# main.py
#
# CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
#
# 1. Se importan y construyen EventRepository, EventService → Fase 1.
# 2. Se importan y construyen AnalyticsRepository, AnalyticsService,
#    AnalyticsController → Fase 2.
# 3. Se importan y construyen TicketRepository, TicketService → Fase 3.
#
# 4. EventService se inyecta en TicketService para emitir el evento
#    'ticket_generated' automáticamente al generar un comprobante.
#
# 5. Se añaden las opciones 5 (Analytics) y 6 (Generar ticket demo)
#    al menú principal para permitir probar las nuevas funcionalidades.
#
# PRINCIPIO SEGUIDO:
#   La composición de dependencias ocurre SÓLO aquí (main.py actúa como
#   Composition Root). Los servicios y controladores no crean sus propias
#   dependencias; las reciben ya construidas.

from infrastructure.repositories.auth_repository       import AuthRepository
from infrastructure.repositories.product_repository    import ProductRepository
from infrastructure.repositories.tenant_repository     import TenantRepository
from infrastructure.repositories.event_repository      import EventRepository      # NUEVO Fase 1
from infrastructure.repositories.analytics_repository  import AnalyticsRepository  # NUEVO Fase 2
from infrastructure.repositories.ticket_repository     import TicketRepository     # NUEVO Fase 3

from domain.services.auth_service       import AuthService
from domain.services.product_service    import ProductService
from domain.services.event_service      import EventService       # NUEVO Fase 1
from domain.services.analytics_service  import AnalyticsService   # NUEVO Fase 2
from domain.services.ticket_service     import TicketService      # NUEVO Fase 3

from application.controllers.auth_controller import AuthController
from application.controllers.product_controller import ProductController
from application.controllers.analytics_controller import AnalyticsController  # NUEVO Fase 2


def main():

    # --- Repositorios ---
    auth_repo       = AuthRepository()
    product_repo    = ProductRepository()
    tenant_repo     = TenantRepository()
    event_repo      = EventRepository()        # Fase 1
    analytics_repo  = AnalyticsRepository()    # Fase 2
    ticket_repo     = TicketRepository()       # Fase 3

    # --- Servicios ---
    auth_service      = AuthService(auth_repo, tenant_repo)
    product_service   = ProductService(product_repo)
    event_service     = EventService(event_repo)             # Fase 1
    analytics_service = AnalyticsService(analytics_repo)     # Fase 2

    # Fase 3: TicketService recibe ticket_repo para historial
    # y event_service para emitir 'ticket_generated' automáticamente.
    ticket_service = TicketService(
        ticket_repo=ticket_repo,
        event_service=event_service,
    )

    # --- Controladores ---
    auth_controller      = AuthController(auth_service)
    product_controller   = ProductController(product_service)
    analytics_controller = AnalyticsController(analytics_service)  # Fase 2

    while True:
        print("\n========= NexaPOS =========")
        print("1. Register")
        print("2. Login")
        print("3. Crear producto")
        print("4. Listar productos")
        print("5. Ver analytics")          # NUEVO Fase 2
        print("6. Ticket demo (prueba)")   # NUEVO Fase 3
        print("7. Salir")

        op = input("Opción: ").strip()

        if op == "1":
            auth_controller.register()
        elif op == "2":
            auth_controller.login()
        elif op == "3":
            product_controller.create()
        elif op == "4":
            product_controller.list()
        elif op == "5":
            # Fase 2: mostrar dashboard analytics en CLI
            analytics_controller.get_dashboard()
        elif op == "6":
            # Fase 3: genera un ticket de prueba y exporta PDF
            _demo_ticket(ticket_service)
        elif op == "7":
            break


def _demo_ticket(ticket_service: "TicketService"):
    """
    Genera un ticket de demostración para probar la Fase 3 desde el CLI.
    En la app real esto se llama desde pos_view.py después del cobro.
    """
    sale_demo = {
        "items": [
            {"name": "Coca-Cola 600ml", "qty": 2, "price": 18.0},
            {"name": "Sabritas Original", "qty": 1, "price": 15.5},
        ],
        "total":          51.5,
        "payment_method": "cash",
        "sale_id":        None,
    }
    ticket = ticket_service.generate(sale_demo)
    path   = ticket_service.export_pdf(ticket)
    print(f"[DEMO] PDF generado: {path}")


if __name__ == "__main__":
    main()