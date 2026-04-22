# presentation/app.py
#
# CAMBIOS (Fases 4, 5, 6):
#
# FASE 4 — Código de Barras:
#   • product_controller expone find_by_barcode() usado en pos_view
#   • No cambia el DI — ProductService ya tiene el método
#
# FASE 5 — Inventario Inteligente:
#   • InventoryService inyectado con inventory_repo + event_service
#   • InventoryController construido y expuesto como self.inventory_controller
#   • SaleService ahora recibe inventory_service (en vez del repo directo)
#   • has_low_stock se consulta en _render() para pasarlo a MainLayout
#   • Nueva ruta "inventory" → InventoryView
#
# FASE 6 — Recargas Electrónicas:
#   • RechargeService construido con event_service inyectado
#   • RechargeController expuesto como self.recharge_controller
#   • PosView recibe recharge_controller (opcional — degradación elegante)
#
# PRINCIPIO (mantenido):
#   Este archivo es el ÚNICO Composition Root.
#   Ningún servicio ni vista crea sus propias dependencias.

import flet as ft
from application.use_cases import create_product_use_case
from domain.services.inventory_alert_service import InventoryAlertService
from infrastructure.repositories.inventory_alert_repository import InventoryAlertRepository
from presentation.theme import AppTheme


class App:

    def __init__(self, page: ft.Page):
        self.page          = page
        self.is_dark       = True
        self.current_route = "login"
        self._setup_page()
        self._init_dependencies()
        self.navigate_to("login")

    # ─── Page setup ───────────────────────────────────────────────
    def _setup_page(self):
        self.page.title         = "NexaPOS"
        self.page.auto_scroll   = True
        self.page.window_width  = 1280
        self.page.window_height = 800
        self.page.window_min_width  = 960
        self.page.window_min_height = 640
        self.page.window_center()
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme      = ft.Theme(color_scheme_seed=AppTheme.ACCENT,
                                        use_material3=True)
        self.page.dark_theme = ft.Theme(color_scheme_seed=AppTheme.ACCENT,
                                        use_material3=True)
        self.page.bgcolor = AppTheme.DARK["bg"]
        self.page.padding = 0
        self.page.spacing = 0

    # ─── Composition Root ─────────────────────────────────────────
    def _init_dependencies(self):

        # ── Repositorios ──────────────────────────────────────────
        from infrastructure.repositories.auth_repository      import AuthRepository
        from infrastructure.repositories.tenant_repository    import TenantRepository
        from infrastructure.repositories.product_repository   import ProductRepository
        from infrastructure.repositories.category_repository  import CategoryRepository
        from infrastructure.repositories.sale_repository      import SaleRepository
        from infrastructure.repositories.inventory_repository import InventoryRepository
        from infrastructure.repositories.event_repository     import EventRepository
        from infrastructure.repositories.analytics_repository import AnalyticsRepository
        from infrastructure.repositories.ticket_repository    import TicketRepository
        from infrastructure.repositories.inventory_alert_repository import InventoryAlertRepository
        
        alert_repo = InventoryAlertRepository()
        auth_repo      = AuthRepository()
        tenant_repo    = TenantRepository()
        product_repo   = ProductRepository()
        category_repo  = CategoryRepository()
        sale_repo      = SaleRepository()
        inventory_repo = InventoryRepository()
        event_repo     = EventRepository()
        analytics_repo = AnalyticsRepository()
        ticket_repo    = TicketRepository()

        # ── Servicios ─────────────────────────────────────────────
        from domain.services.auth_service       import AuthService
        from domain.services.barcode_service    import BarcodeService
        from domain.services.product_service    import ProductService
        from domain.services.category_service   import CategoryService
        from domain.services.event_service      import EventService
        from domain.services.analytics_service  import AnalyticsService
        from domain.services.ticket_service     import TicketService
        from domain.services.inventory_service  import InventoryService   # NUEVO Fase 5
        from domain.services.sale_service       import SaleService
        from domain.services.recharge_service   import RechargeService    # NUEVO Fase 6
        from domain.services.inventory_alert_service import InventoryAlertService

        alert_svc = InventoryAlertService(alert_repo=alert_repo)  # NUEVO Fase 5
        auth_svc      = AuthService(auth_repo, tenant_repo)
        barcode_svc   = BarcodeService()
        product_svc   = ProductService(product_repo, barcode_service=barcode_svc)
        category_svc  = CategoryService(category_repo)
        event_svc     = EventService(event_repo)
        analytics_svc = AnalyticsService(analytics_repo)
        ticket_svc    = TicketService(ticket_repo=ticket_repo,
                                      event_service=event_svc)

        # NUEVO Fase 5: InventoryService con eventos para alertas de stock
        inventory_svc = InventoryService(
            inventory_repo=inventory_repo,
            event_service=event_svc,
        )

        # CAMBIO Fase 5: SaleService ahora usa inventory_service
        sale_svc = SaleService(
            sale_repo=sale_repo,
            event_service=event_svc,
            inventory_service=inventory_svc,       # NUEVO — reemplaza inventory_repo
        )

        # NUEVO Fase 6: RechargeService (mock, sin recharge_repo aún)
        recharge_svc = RechargeService(event_service=event_svc)

        # ── Use Cases ─────────────────────────────────────────────
        from application.use_cases.create_sale_use_case    import CreateSaleUseCase
        from application.use_cases.register_user_use_case  import RegisterUserUseCase
        from application.use_cases.create_product_use_case import CreateProductUseCase  # ← AÑADIR
        
        create_sale_use_case    = CreateSaleUseCase(sale_repo, inventory_svc, event_svc)
        register_use_case       = RegisterUserUseCase(auth_repo, tenant_repo)
        create_product_use_case = CreateProductUseCase(                                 # ← AÑADIR
            product_repo=product_repo,
            inventory_service=inventory_svc,
            event_service=event_svc,
        )

        # ── Controladores ─────────────────────────────────────────
        from application.controllers.auth_controller       import AuthController
        from application.controllers.product_controller    import ProductController
        from application.controllers.category_controller   import CategoryController
        from application.controllers.sale_controller       import SaleController
        from application.controllers.analytics_controller  import AnalyticsController
        from application.controllers.inventory_controller  import InventoryController  # NUEVO
        from application.controllers.recharge_controller   import RechargeController   # NUEVO

        self.auth_controller      = AuthController(auth_svc, self, register_use_case)
        self.product_controller = ProductController(
            product_svc,
            self,
            create_use_case=create_product_use_case,   # ← AÑADIR ESTE ARGUMENTO
        )
        self.category_controller  = CategoryController(category_svc, self)
        self.sale_controller      = SaleController(sale_svc, self, create_sale_use_case)
        self.analytics_controller = AnalyticsController(analytics_svc)
        self.ticket_service       = ticket_svc
        self.inventory_controller = InventoryController(
           service=inventory_svc,           
           app=self,
          alert_service=alert_svc,    # NUEVO
       )
        self.recharge_controller  = RechargeController(recharge_svc, self)    # NUEVO

    # ─── Navegación ───────────────────────────────────────────────
    def navigate_to(self, route: str):
        self.current_route = route
        self._render(route)

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.page.theme_mode = (ft.ThemeMode.DARK if self.is_dark
                                else ft.ThemeMode.LIGHT)
        self.page.bgcolor = self.get_colors()["bg"]
        self.page.update()
        self._render(self.current_route)

    def get_colors(self) -> dict:
        return AppTheme.DARK if self.is_dark else AppTheme.LIGHT

    # ─── Render ───────────────────────────────────────────────────
    def _render(self, route: str):
        from presentation.views.login_view       import LoginView
        from presentation.views.register_view    import RegisterView
        from presentation.components.main_layout import MainLayout

        colors = self.get_colors()

        if route == "login":
            view = LoginView(self.page, colors, self.is_dark,
                             self.auth_controller, self)
            self._set_content(view.build())
            return

        if route == "register":
            view = RegisterView(self.page, colors, self.is_dark,
                                self.auth_controller, self)
            self._set_content(view.build())
            return

        # NUEVO Fase 5: consultar alertas para sidebar
        has_low_stock = False
        try:
            has_low_stock = self.inventory_controller.has_low_stock()
        except Exception:
            pass

        content_view = self._build_content_view(route, colors)
        layout       = MainLayout(
            self.page, colors, self.is_dark, route,
            content_view, self,
            has_low_stock=has_low_stock,             # NUEVO
        )
        self._set_content(layout.build())

    def _build_content_view(self, route: str, colors: dict):
        from presentation.views.dashboard_view  import DashboardView
        from presentation.views.pos_view        import PosView
        from presentation.views.products_view   import ProductsView
        from presentation.views.categories_view import CategoriesView
        from presentation.views.sales_view      import SalesView
        from presentation.views.analytics_view  import AnalyticsView
        from presentation.views.inventory_view  import InventoryView   # NUEVO Fase 5

        views = {
            "dashboard": lambda: DashboardView(
                self.page, colors, self.is_dark,
                self.sale_controller, self.product_controller,
                self.analytics_controller,
                self.inventory_controller,      # NUEVO: para banner de alertas
                app=self,
            ),
            "pos": lambda: PosView(
                self.page, colors, self.is_dark,
                self.sale_controller, self.product_controller,
                self.ticket_service, self,
                recharge_controller=self.recharge_controller,  # NUEVO Fase 6
            ),
            "products": lambda: ProductsView(
                self.page, colors, self.is_dark,
                self.product_controller, self.category_controller, self,
            ),
            "inventory": lambda: InventoryView(    # NUEVO Fase 5
                self.page, colors, self.is_dark,
                self.inventory_controller, self,
            ),
            "categories": lambda: CategoriesView(
                self.page, colors, self.is_dark,
                self.category_controller, self,
            ),
            "sales": lambda: SalesView(
                self.page, colors, self.is_dark,
                self.sale_controller, self,
            ),
            "analytics": lambda: AnalyticsView(
                self.page, colors, self.is_dark,
                self.analytics_controller, self,
            ),
        }
        factory = views.get(route, views["dashboard"])
        return factory()

    def _set_content(self, control):
        self.page.controls.clear()   # type: ignore
        self.page.controls.append(   # type: ignore
            ft.Container(content=control, expand=True)
        )
        self.page.update()           # type: ignore

    # ─── Notificaciones ───────────────────────────────────────────
    def show_snackbar(self, message: str, error: bool = False):
        icon  = ft.icons.ERROR_ROUNDED if error else ft.icons.CHECK_CIRCLE_ROUNDED
        color = AppTheme.ERROR if error else AppTheme.SUCCESS
        self.page.snack_bar = ft.SnackBar(
            content=ft.Row([
                ft.Icon(icon, color="white", size=18),
                ft.Text(message, color="white", size=13, expand=True),
            ], spacing=10),
            bgcolor=color, duration=3000,
            behavior=ft.SnackBarBehavior.FLOATING,
        )
        self.page.snack_bar.open = True
        self.page.update()