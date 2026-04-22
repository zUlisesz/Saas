# infrastructure/repositories/inventory_alert_repository.py
#
# NUEVA — Fase 5 (22 Abril 2026)
#
# JUSTIFICACIÓN DE SEPARACIÓN:
#   Las alertas de inventario tienen su propio ciclo de vida
#   (new → acknowledged → resolved|ignored) y su propia tabla.
#   Meterlas en InventoryRepository violaría SRP y crecería
#   descontroladamente conforme se añadan tipos de alerta en Fase 7+.
#
# PATRÓN:
#   Idéntico a todos los repos del proyecto:
#   - Solo habla con Supabase
#   - Sin lógica de negocio
#   - Métodos descriptivos que reflejan la intención
#   - RPCs para operaciones que requieren SECURITY DEFINER
#
# NOTA SOBRE RPCs vs. QUERIES DIRECTAS:
#   acknowledge_alert y resolve_alert usan RPCs porque necesitan
#   SECURITY DEFINER para actualizar sin que RLS interfiera.
#   get_all y get_new usan queries directas porque RLS del tenant
#   ya filtra correctamente (política alerts_tenant_isolation).

from config.supabase_client import supabase


class InventoryAlertRepository:

    # ------------------------------------------------------------------ #
    # LECTURA                                                             #
    # ------------------------------------------------------------------ #

    def get_all(self, tenant_id: str, status: str = None, limit: int = 100): #type: ignore
        """
        Retorna alertas del tenant, con join al producto para mostrar nombre.

        Args:
            tenant_id: UUID del tenant activo.
            status:    Filtro opcional — 'new'|'acknowledged'|'resolved'|'ignored'.
                       None = todas.
            limit:     Máx de filas. Default 100 para no sobrecargar la UI.

        DECISIÓN: incluimos join a products para que InventoryAlertService
        no tenga que hacer una segunda query para obtener el nombre.
        """
        q = (
            supabase.table("inventory_alerts")
            .select("*, products(id, name, barcode)")
            .eq("tenant_id", tenant_id)
            .order("generated_at", desc=True)
            .limit(limit)
        )
        if status:
            q = q.eq("status", status)
        return q.execute()

    def get_new(self, tenant_id: str):
        """
        Alertas sin revisar (status='new').
        Atajo frecuente: sidebar badge, dashboard banner, polling.
        """
        return self.get_all(tenant_id, status="new")

    def get_by_product(self, tenant_id: str, product_id: str, limit: int = 20):
        """
        Historial de alertas de un producto específico.
        Para el modal de detalle en InventoryView.
        """
        return (
            supabase.table("inventory_alerts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("product_id", product_id)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )

    def count_new(self, tenant_id: str) -> int:
        """
        Conteo rápido de alertas nuevas.
        Usado para el badge sin traer toda la data.

        DECISIÓN: Supabase count via head=True es más eficiente que
        traer filas y hacer len(). Para tablas pequeñas la diferencia
        es mínima, pero es el patrón correcto a escala.
        """
        try:
            res = (
                supabase.table("inventory_alerts")
                .select("id", count="exact", head=True) #type: ignore
                .eq("tenant_id", tenant_id)
                .eq("status", "new")
                .execute()
            )
            return res.count or 0
        except Exception:
            return 0

    # ------------------------------------------------------------------ #
    # ESCRITURA — Transiciones de estado (vía RPC)                       #
    # ------------------------------------------------------------------ #

    def acknowledge(self, alert_id: str, user_id: str):
        """
        Marca alerta como acknowledged usando RPC acknowledge_alert.

        RPC es idempotente: solo actualiza si status='new'.
        Retorna la fila actualizada o lista vacía si ya estaba procesada.

        DECISIÓN: RPC en lugar de UPDATE directo porque la función
        tiene SECURITY DEFINER y valida la precondición (status='new').
        """
        return supabase.rpc(
            "acknowledge_alert",
            {"p_alert_id": alert_id, "p_user_id": user_id},
        ).execute()

    def resolve(self, alert_id: str, user_id: str, notes: str = None): #type: ignore
        """
        Marca alerta como resolved usando RPC resolve_alert.
        Acepta desde new o acknowledged (no desde ignored).

        Args:
            notes: Comentario del usuario sobre la resolución. Opcional.
        """
        params = {"p_alert_id": alert_id, "p_user_id": user_id}
        if notes:
            params["p_notes"] = notes
        return supabase.rpc("resolve_alert", params).execute()

    def ignore(self, alert_id: str):
        """
        Marca alerta como ignored (descartada sin resolución).
        UPDATE directo — no requiere SECURITY DEFINER porque
        RLS del tenant ya garantiza que solo el propietario accede.
        """
        return (
            supabase.table("inventory_alerts")
            .update({"status": "ignored"})
            .eq("id", alert_id)
            .execute()
        )

    # ------------------------------------------------------------------ #
    # GENERACIÓN — Dispara la RPC de creación masiva                     #
    # ------------------------------------------------------------------ #

    def generate_for_tenant(self, tenant_id: str = None): #type: ignore
        """
        Dispara RPC generate_inventory_alerts() en BD.
        Crea automáticamente alertas low_stock/overstock para todos los tenants
        (si tenant_id es None) o para uno específico.

        NOTA: la RPC actual no acepta p_tenant_id — genera para todos.
        Cuando se escale a Fase 7 (planes) se puede parchear la RPC
        para aceptar el parámetro y limitar por tenant.

        Retorna: {"alerts_generated": int} o None si falla.
        """
        try:
            return supabase.rpc("generate_inventory_alerts", {}).execute()
        except Exception as e:
            print(f"[ALERT REPO] generate_for_tenant falló: {e}")
            return None