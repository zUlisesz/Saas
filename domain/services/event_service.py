# domain/services/event_service.py
#
# JUSTIFICACIÓN:
# EventService vive en 'domain' porque orquesta lógica de negocio: 
# construir el payload del evento, validar campos obligatorios y delegarlo 
# al repositorio. No toca Supabase directamente.
#
# PATRÓN SEGUIDO:
# Mismo patrón que ProductService y AuthService:
#   __init__ recibe el repo por inyección → el servicio no sabe CÓMO se persiste.
#
# USO:
# Este servicio se inyecta en cualquier otro servicio que necesite emitir
# eventos (SaleService, ProductService, AuthService...).
# Así desacoplamos el "qué pasó" del "cómo se registra".

from datetime import datetime, timezone


class EventService:

    # Tipos de evento reconocidos por el sistema.
    # Centralizar aquí evita strings sueltos por todo el código (typo-safe).
    SALE_CREATED      = "sale_created"
    PRODUCT_CREATED   = "product_created"
    PRODUCT_DELETED   = "product_deleted"
    STOCK_UPDATED     = "stock_updated"
    USER_LOGIN        = "user_login"
    USER_REGISTER     = "user_register"
    TICKET_GENERATED  = "ticket_generated"

    def __init__(self, repo):
        """
        Args:
            repo: EventRepository — inyectado desde main.py (o desde tests con un mock).
        """
        self.repo = repo

    def emit(self, tenant_id: str, event_type: str, payload: dict) -> None:
        """
        Registra un evento en el sistema.

        Args:
            tenant_id:   UUID del tenant al que pertenece el evento.
            event_type:  Constante de clase (ej. EventService.SALE_CREATED).
            payload:     Dict con datos relevantes del evento (serializable a JSON).

        DECISIÓN DE DISEÑO:
            El método es 'fire and forget': no lanza excepción si el repo falla,
            sólo loguea el error. Los eventos son observabilidad, nunca deben
            interrumpir el flujo principal de negocio.
        """
        if not tenant_id:
            raise ValueError("[EventService] tenant_id es obligatorio para emitir un evento")

        if not event_type:
            raise ValueError("[EventService] event_type es obligatorio")

        event = {
            "tenant_id": tenant_id,
            "type":      event_type,
            "payload":   payload or {},
        }

        try:
            self.repo.create(event)
            print(f"[EVENT] {event_type} → tenant: {tenant_id}")
        except Exception as e:
            # No propagamos: un fallo de observabilidad NO debe romper la venta.
            print(f"[EVENT ERROR] No se pudo registrar '{event_type}': {e}")