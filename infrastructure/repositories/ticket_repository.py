# infrastructure/repositories/ticket_repository.py
#
# JUSTIFICACIÓN:
# Aunque el roadmap no especifica explícitamente un ticket_repository,
# el requisito de "historial de tickets" (Fase 3) implica persistencia.
# Separamos la persistencia en su propio repositorio para no contaminar
# sale_repository con responsabilidades ajenas.
#
# La tabla 'tickets' actúa como log inmutable de comprobantes generados.
# Incluso si una venta se cancela, el ticket emitido queda en el historial.

from config.supabase_client import supabase


class TicketRepository:

    def save(self, ticket: dict):
        """
        Persiste el ticket en la tabla 'tickets'.
        Sólo guarda los campos relevantes (no el dict completo
        para evitar datos redundantes).
        """
        record = {
            "folio":          ticket["folio"],
            "tenant_id":      ticket["tenant_id"],
            "sale_id":        ticket.get("sale_id"),
            "total":          ticket["total"],
            "payment_method": ticket.get("payment_method", "cash"),
            "generated_at":   ticket["generated_at"],
            "payload":        ticket,     # snapshot completo en jsonb
        }
        return supabase.table("tickets").insert(record).execute()

    def get_by_tenant(self, tenant_id: str):
        """
        Devuelve el historial de tickets del tenant, más recientes primero.
        """
        return (
            supabase.table("tickets")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("generated_at", desc=True)
            .execute()
        )

    def get_by_folio(self, folio: str):
        """
        Busca un ticket específico por folio. Útil para reimprimir.
        """
        return (
            supabase.table("tickets")
            .select("*")
            .eq("folio", folio)
            .limit(1)
            .execute()
        )