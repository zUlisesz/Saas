# infrastructure/repositories/event_repository.py
#
# JUSTIFICACIÓN:
# Repositorio dedicado exclusivamente a la capa de persistencia de eventos.
# Sigue el mismo patrón que product_repository.py y auth_repository.py:
# recibe el cliente de Supabase por inyección, no lo importa directamente,
# para mantener la capa de infraestructura desacoplada y testeable.
#
# No contiene lógica de negocio; sólo habla con la base de datos.

from config.supabase_client import supabase


class EventRepository:

    def create(self, event: dict):
        """
        Inserta un evento en la tabla 'events'.
        El dict debe contener: tenant_id, type, payload.
        Supabase asigna automáticamente id y created_at.
        """
        return supabase.table("events").insert(event).execute()

    def get_by_tenant(self, tenant_id: str, event_type: str = None): # type: ignore
        """
        Devuelve eventos de un tenant, con filtro opcional por tipo.
        Útil para auditoría y para el módulo de analytics en el futuro.
        """
        query = supabase.table("events").select("*").eq("tenant_id", tenant_id)

        if event_type:
            query = query.eq("type", event_type)

        return query.order("created_at", desc=True).execute()