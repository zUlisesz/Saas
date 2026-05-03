# domain/exceptions/__init__.py
#
# Jerarquía de excepciones de dominio para NexaPOS.
#
# MOTIVACIÓN (del diagnóstico):
#   Antes todos los servicios lanzaban ValueError o Exception genérica.
#   Los controladores no podían distinguir entre:
#     • Error de validación (campo vacío)      → mostrar campo específico al usuario
#     • Error de regla de negocio (stock bajo) → mostrar regla violada
#     • Error de infraestructura (DB caída)    → loggear, mensaje genérico
#     • Error de autenticación                 → redirigir a login
#
# CON ESTA JERARQUÍA los controladores manejan cada tipo diferente:
#   except ValidationError    → snackbar con el campo específico en rojo
#   except BusinessRuleError  → snackbar informando la regla violada
#   except RepositoryError    → mensaje genérico de "error del sistema"
#   except AuthenticationError → navigate_to("login")


class NexaPOSError(Exception):
    """Base para todas las excepciones de dominio de NexaPOS."""
    pass


# ─── Autenticación y Autorización ─────────────────────────────────────────────

class AuthenticationError(NexaPOSError):
    """
    Usuario no autenticado, token expirado o credenciales inválidas.
    Los controladores deben redirigir a login cuando la capturan.
    """
    pass


class AuthorizationError(NexaPOSError):
    """
    Usuario autenticado pero sin permisos para la operación.
    Ej: un 'employee' intenta eliminar productos de otro tenant.
    """
    pass


# ─── Validación de datos ──────────────────────────────────────────────────────

class ValidationError(NexaPOSError):
    """
    Datos de entrada inválidos (formato, rango, campos requeridos).
    Incluye el campo específico para que la UI pueda resaltarlo.
    """
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


# ─── Reglas de Negocio ────────────────────────────────────────────────────────

class BusinessRuleError(NexaPOSError):
    """
    Los datos son válidos pero la operación viola una regla del dominio.
    Ej: intentar vender más unidades de las que hay en stock.
    """
    pass


class InsufficientStockError(BusinessRuleError):
    """Stock insuficiente para completar una venta."""
    def __init__(self, product_name: str, available: int, requested: int):
        self.product_name = product_name
        self.available    = available
        self.requested    = requested
        super().__init__(
            f"Stock insuficiente para '{product_name}': "
            f"disponible {available}, solicitado {requested}"
        )


class InsufficientPaymentError(BusinessRuleError):
    """El monto recibido no cubre el total de la venta."""
    def __init__(self, total: float, received: float):
        self.total    = total
        self.received = received
        super().__init__(
            f"Monto insuficiente. Total: ${total:.2f}, recibido: ${received:.2f}"
        )


class DuplicateBarcodeError(BusinessRuleError):
    """El código de barras ya está registrado para otro producto en este tenant."""
    def __init__(self, barcode: str):
        self.barcode = barcode
        super().__init__(f"El código de barras '{barcode}' ya está registrado")


class EmptyCartError(BusinessRuleError):
    """Se intentó registrar una venta con el carrito vacío."""
    def __init__(self):
        super().__init__("El carrito está vacío")


# ─── Entidades no encontradas ─────────────────────────────────────────────────

class NotFoundError(NexaPOSError):
    """Entidad solicitada no encontrada en el repositorio."""
    def __init__(self, entity: str, identifier: str = ""):
        self.entity     = entity
        self.identifier = identifier
        msg = f"{entity} no encontrado"
        if identifier:
            msg += f" (id: {identifier})"
        super().__init__(msg)


# ─── Infraestructura / Repositorios ───────────────────────────────────────────

class RepositoryError(NexaPOSError):
    """
    Error de persistencia: base de datos caída, violación de RLS,
    timeout de red, etc.
    Los controladores deben mostrar un mensaje genérico y loggear el detalle.
    """
    pass


# ─── Recargas Electrónicas (Fase 6) ──────────────────────────────────────────

class InvalidPhoneError(ValidationError):
    """Número de teléfono con formato o longitud inválida."""
    def __init__(self):
        super().__init__("phone", "El número debe tener entre 8 y 12 dígitos")


class InvalidAmountError(ValidationError):
    """Monto de recarga fuera del rango permitido."""
    def __init__(self, min_val: float, max_val: float):
        super().__init__("amount",
            f"El monto debe estar entre Bs {min_val} y Bs {max_val}")


class InvalidOperatorError(ValidationError):
    """Operadora de telefonía no reconocida en el catálogo."""
    def __init__(self, operators: list):
        super().__init__("operator",
            f"Operador no válido. Opciones: {operators}")


class RechargeProviderError(NexaPOSError):
    """
    Fallo externo del proveedor de recargas (API caída, respuesta inesperada).
    Hereda de NexaPOSError — no de ValidationError ni BusinessRuleError —
    porque es un fallo del sistema externo, no del usuario.
    Los controllers lo capturan con except NexaPOSError o except RechargeProviderError.
    """
    pass


class RechargeTimeoutError(RechargeProviderError):
    """La API del proveedor no respondió dentro del tiempo límite."""
    def __init__(self):
        super().__init__("Tiempo de espera agotado. Intente de nuevo.")


class DuplicateRechargeError(NexaPOSError):
    """
    external_tx_id duplicado — probable reintento de doble cobro.
    Hereda de NexaPOSError para ser capturable en el bloque genérico del controller.
    """
    def __init__(self, ext_tx_id: str):
        self.ext_tx_id = ext_tx_id
        super().__init__(f"Transacción duplicada: {ext_tx_id}")
