# infrastructure/repositories/analytics_repository.py
#
# JUSTIFICACIÓN:
# Separamos analytics en su propio repositorio porque sus queries son
# de LECTURA AGREGADA (GROUP BY, SUM, AVG), mientras que los repositorios
# de entidades (sale_repository, product_repository) hacen CRUD.
# Mezclarlos violaría el Single Responsibility Principle.
#
# Las queries usan Supabase RPC (funciones SQL almacenadas) para:
#   1. Mantener la lógica SQL compleja en la base de datos, no en Python.
#   2. Aprovechar los índices y el query planner de Postgres.
#   3. Evitar traer miles de rows a Python sólo para agregarlos.
#
# Las funciones SQL que deben existir en Supabase están documentadas
# en el archivo: analytics_migration.sql (entregado junto a este módulo).

from config.supabase_client import supabase


class AnalyticsRepository:

    # ------------------------------------------------------------------ #
    # Ventas por día                                                       #
    # ------------------------------------------------------------------ #
    def sales_by_day(self, tenant_id: str):
        """
        Devuelve una lista de {day: date, total: numeric}.
        Llama a la función SQL 'sales_by_day(tenant uuid)'.
        """
        return supabase.rpc("sales_by_day", {"tenant": tenant_id}).execute()

    # ------------------------------------------------------------------ #
    # Ticket promedio                                                      #
    # ------------------------------------------------------------------ #
    def average_ticket(self, tenant_id: str):
        """
        Devuelve el promedio de 'total' de las ventas del tenant.
        Llama a la función SQL 'avg_ticket(tenant uuid)'.
        """
        return supabase.rpc("avg_ticket", {"tenant": tenant_id}).execute()

    # ------------------------------------------------------------------ #
    # Top 10 productos más vendidos                                       #
    # ------------------------------------------------------------------ #
    def top_products(self, tenant_id: str):
        """
        Devuelve lista de {name: text, total_qty: int}.
        Llama a la función SQL 'top_products(tenant uuid)'.
        """
        return supabase.rpc("top_products", {"tenant": tenant_id}).execute()

    # ------------------------------------------------------------------ #
    # Ingresos totales                                                    #
    # ------------------------------------------------------------------ #
    def total_revenue(self, tenant_id: str):
        """
        Devuelve todas las ventas completadas para sumar en Python.
        DECISIÓN: usamos .select("total") directo (sin RPC) porque es
        una query simple; no justifica una función SQL almacenada.
        """
        return (
            supabase.table("sales")
            .select("total")
            .eq("tenant_id", tenant_id)
            .eq("status", "completed")
            .execute()
        )

    # ------------------------------------------------------------------ #
    # Conteo de ventas del día actual                                     #
    # ------------------------------------------------------------------ #
    def sales_count_today(self, tenant_id: str):
        """
        Devuelve el número de ventas registradas hoy.
        Usa filtro por rango de fechas directamente en Supabase.
        """
        from datetime import date
        today = date.today().isoformat()

        return (
            supabase.table("sales")
            .select("id", count="exact") # type: ignore
            .eq("tenant_id", tenant_id)
            .gte("created_at", f"{today}T00:00:00")
            .lte("created_at", f"{today}T23:59:59")
            .execute()
        )