# application/container.py
#
# NUEVA — Fase 5 (22 Abril 2026)
#
# JUSTIFICACIÓN:
#   app.py como Composition Root manual funciona bien hasta ~8 servicios.
#   En Fases 6-8 se añaden: RechargeService, SubscriptionService,
#   AuditService, NotificationService — la lista crece y las dependencias
#   entre servicios se vuelven un grafo difícil de mantener en un solo método.
#
#   DECISIÓN: No usar un framework de DI externo (injector, dependency-injector)
#   porque agrega dependencia externa y complejidad innecesaria para el tamaño
#   actual del proyecto. En cambio, se implementa un container ligero que:
#     - Resuelve dependencias por nombre de string (registry pattern)
#     - Construye singletons lazy (se instancian solo cuando se piden)
#     - Es testeable: se puede pasar un repo/servicio mock via register()
#     - Mantiene compatibilidad total con app.py existente
#
# USO EN app.py (reemplaza el bloque _init_dependencies):
#
#   from application.container import ServiceContainer
#   container = ServiceContainer()
#   container.wire()
#
#   self.inventory_controller = container.get("inventory_controller")
#   self.sale_controller      = container.get("sale_controller")
#   # ... etc.
#
# USO EN TESTS (override de dependencias):
#
#   container = ServiceContainer()
#   container.register("inventory_repo", lambda: mock_repo)
#   container.wire()
#   svc = container.get("inventory_service")
#
# EXTENSIÓN PARA NUEVA FASE:
#   Solo hay que añadir el bloque de registro en wire():
#   self.register("recharge_repo",     lambda: RechargeRepository())
#   self.register("recharge_service",  lambda: RechargeService(...))
#   Nada más cambia.

from __future__ import annotations
from typing import Callable, Any


class ServiceContainer:
    """
    DI Container ligero con resolución lazy por nombre.

    Flujo:
        1. register(name, factory_fn)  → registra un factory (lambda)
        2. wire()                      → registra todos los servicios del proyecto
        3. get(name)                   → instancia (o retorna singleton) el servicio

    Todos los servicios son SINGLETONS dentro de una misma instancia del container.
    """

    def __init__(self):
        self._factories:  dict[str, Callable] = {}
        self._singletons: dict[str, Any]      = {}
        self._wired: bool = False

    # ------------------------------------------------------------------ #
    # API pública                                                         #
    # ------------------------------------------------------------------ #

    def register(self, name: str, factory: Callable) -> "ServiceContainer":
        """
        Registra un factory para un servicio.
        Si ya existe, lo sobreescribe (útil en tests para mockear).

        Args:
            name:    Nombre del servicio (ej: "inventory_service")
            factory: Callable sin argumentos que retorna la instancia.

        Returns: self (fluent API)
        """
        self._factories[name] = factory
        # Si ya había un singleton construido, invalidarlo
        self._singletons.pop(name, None)
        return self

    def get(self, name: str) -> Any:
        """
        Retorna el servicio solicitado, construyéndolo si es la primera vez.
        Usa el patrón singleton: una instancia por container.

        Raises:
            KeyError: si el nombre no está registrado (falla rápido).
        """
        if name not in self._singletons:
            if name not in self._factories:
                raise KeyError(
                    f"ServiceContainer: '{name}' no está registrado. "
                    f"Disponibles: {sorted(self._factories.keys())}"
                )
            self._singletons[name] = self._factories[name]()
        return self._singletons[name]

    def wire(self) -> "ServiceContainer":
        """
        Registra TODOS los servicios del proyecto.
        Se llama UNA VEZ desde App._init_dependencies().

        Orden: Repositorios → Servicios → Use Cases → Controllers.
        Las lambdas usan closures sobre `self` para permitir
        que cada factory llame a self.get() de sus dependencias.

        CONVENCIÓN DE NOMBRES:
            *_repo       → RepositoryXxx
            *_service    → XxxService
            *_use_case   → XxxUseCase
            *_controller → XxxController
        """
        if self._wired:
            return self

        # ── Repositorios ──────────────────────────────────────────────

        self.register("auth_repo", lambda: self._import(
            "infrastructure.repositories.auth_repository", "AuthRepository"
        )())

        self.register("tenant_repo", lambda: self._import(
            "infrastructure.repositories.tenant_repository", "TenantRepository"
        )())

        self.register("product_repo", lambda: self._import(
            "infrastructure.repositories.product_repository", "ProductRepository"
        )())

        self.register("category_repo", lambda: self._import(
            "infrastructure.repositories.category_repository", "CategoryRepository"
        )())

        self.register("sale_repo", lambda: self._import(
            "infrastructure.repositories.sale_repository", "SaleRepository"
        )())

        self.register("inventory_repo", lambda: self._import(
            "infrastructure.repositories.inventory_repository", "InventoryRepository"
        )())

        self.register("alert_repo", lambda: self._import(
            "infrastructure.repositories.inventory_alert_repository",
            "InventoryAlertRepository"
        )())

        self.register("event_repo", lambda: self._import(
            "infrastructure.repositories.event_repository", "EventRepository"
        )())

        self.register("analytics_repo", lambda: self._import(
            "infrastructure.repositories.analytics_repository", "AnalyticsRepository"
        )())

        self.register("ticket_repo", lambda: self._import(
            "infrastructure.repositories.ticket_repository", "TicketRepository"
        )())

        # ── Servicios ─────────────────────────────────────────────────

        self.register("auth_service", lambda: self._import(
            "domain.services.auth_service", "AuthService"
        )(self.get("auth_repo"), self.get("tenant_repo")))

        self.register("event_service", lambda: self._import(
            "domain.services.event_service", "EventService"
        )(self.get("event_repo")))

        self.register("product_service", lambda: (
            lambda BarcodeService, ProductService: ProductService(
                self.get("product_repo"),
                barcode_service=BarcodeService(),
            )
        )(
            self._import("domain.services.barcode_service", "BarcodeService"),
            self._import("domain.services.product_service", "ProductService"),
        ))

        self.register("category_service", lambda: self._import(
            "domain.services.category_service", "CategoryService"
        )(self.get("category_repo")))

        self.register("analytics_service", lambda: self._import(
            "domain.services.analytics_service", "AnalyticsService"
        )(self.get("analytics_repo")))

        self.register("ticket_service", lambda: self._import(
            "domain.services.ticket_service", "TicketService"
        )(
            ticket_repo=self.get("ticket_repo"),
            event_service=self.get("event_service"),
        ))

        self.register("inventory_service", lambda: self._import(
            "domain.services.inventory_service", "InventoryService"
        )(
            inventory_repo=self.get("inventory_repo"),
            event_service=self.get("event_service"),
        ))

        self.register("alert_service", lambda: self._import(
            "domain.services.inventory_alert_service", "InventoryAlertService"
        )(alert_repo=self.get("alert_repo")))

        self.register("sale_service", lambda: self._import(
            "domain.services.sale_service", "SaleService"
        )(
            sale_repo=self.get("sale_repo"),
            event_service=self.get("event_service"),
            inventory_service=self.get("inventory_service"),
        ))

        # Fase 6: RechargeService
        self.register("recharge_service", lambda: self._import(
            "domain.services.recharge_service", "RechargeService"
        )(event_service=self.get("event_service")))

        # ── Use Cases ─────────────────────────────────────────────────

        self.register("register_use_case", lambda: self._import(
            "application.use_cases.register_user_use_case", "RegisterUserUseCase"
        )(self.get("auth_repo"), self.get("tenant_repo")))

        self.register("create_product_use_case", lambda: self._import(
            "application.use_cases.create_product_use_case", "CreateProductUseCase"
        )(
            product_repo=self.get("product_repo"),
            inventory_service=self.get("inventory_service"),
            event_service=self.get("event_service"),
        ))

        self.register("create_sale_use_case", lambda: self._import(
            "application.use_cases.create_sale_use_case", "CreateSaleUseCase"
        )(
            self.get("sale_repo"),
            self.get("inventory_service"),
            self.get("event_service"),
        ))

        # ── Controllers ───────────────────────────────────────────────

        self.register("auth_controller", lambda: self._import(
            "application.controllers.auth_controller", "AuthController"
        )(
            self.get("auth_service"),
            self._app_ref(),
            self.get("register_use_case"),
        ))

        self.register("product_controller", lambda: self._import(
            "application.controllers.product_controller", "ProductController"
        )(
            self.get("product_service"),
            self._app_ref(),
            create_use_case=self.get("create_product_use_case"),
        ))

        self.register("category_controller", lambda: self._import(
            "application.controllers.category_controller", "CategoryController"
        )(self.get("category_service"), self._app_ref()))

        self.register("sale_controller", lambda: self._import(
            "application.controllers.sale_controller", "SaleController"
        )(
            self.get("sale_service"),
            self._app_ref(),
            self.get("create_sale_use_case"),
        ))

        self.register("analytics_controller", lambda: self._import(
            "application.controllers.analytics_controller", "AnalyticsController"
        )(self.get("analytics_service")))

        self.register("inventory_controller", lambda: self._import(
            "application.controllers.inventory_controller", "InventoryController"
        )(
            service=self.get("inventory_service"),
            app=self._app_ref(),
            alert_service=self.get("alert_service"),
        ))

        self.register("recharge_controller", lambda: self._import(
            "application.controllers.recharge_controller", "RechargeController"
        )(self.get("recharge_service"), self._app_ref()))

        self._wired = True
        return self

    # ------------------------------------------------------------------ #
    # Integración con App                                                 #
    # ------------------------------------------------------------------ #

    def set_app(self, app) -> "ServiceContainer":
        """
        Inyecta la referencia a la instancia de App.
        Llamado ANTES de wire() desde App._init_dependencies().

        Por qué es necesario: los controllers reciben `app` para llamar
        a show_snackbar(). El container necesita una ref a app.
        """
        self._app = app
        return self

    def _app_ref(self):
        """
        Retorna la referencia a App. Falla con mensaje claro si no se llamó set_app().
        """
        if not hasattr(self, "_app"):
            raise RuntimeError(
                "ServiceContainer: llama set_app(app) antes de wire(). "
                "Los controllers necesitan la referencia a App."
            )
        return self._app

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _import(module_path: str, class_name: str):
        """
        Import lazy: importa el módulo y retorna la clase.
        Lazy porque los imports en el top-level de container.py
        causarían imports circulares (app.py importa container,
        container importaría todos los módulos del proyecto).

        El costo de import es mínimo — Python cachea módulos en sys.modules.
        """
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def has(self, name: str) -> bool:
        """Comprueba si un servicio está registrado."""
        return name in self._factories

    def registered(self) -> list[str]:
        """Lista de todos los nombres registrados. Útil para debugging."""
        return sorted(self._factories.keys())

    def reset(self) -> "ServiceContainer":
        """
        Limpia los singletons (no los factories).
        Útil en tests para forzar re-instanciación entre test cases.
        """
        self._singletons.clear()
        return self