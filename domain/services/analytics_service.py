# domain/services/analytics_service.py
#
# JUSTIFICACIÓN:
# AnalyticsService vive en 'domain' porque contiene LÓGICA DE NEGOCIO:
# combinar métricas, calcular tasa de crecimiento, clasificar datos.
# El repositorio sólo trae datos crudos; el servicio los convierte en
# información útil para tomar decisiones.
#
# PATRÓN SEGUIDO:
# Mismo patrón que ProductService: __init__ recibe repo por inyección.
# Así podemos hacer tests unitarios pasando un repo mock.
#
# DEPENDENCIA DE SESSION:
# Seguimos el mismo patrón que ProductService y SaleService: leemos
# Session.tenant_id para garantizar aislamiento multi-tenant.
# Ninguna métrica puede "escapar" al tenant del usuario autenticado.

from session.session import Session


class AnalyticsService:

    def __init__(self, analytics_repo):
        """
        Args:
            analytics_repo: AnalyticsRepository — inyectado desde main.py.
        """
        self.repo = analytics_repo

    # ------------------------------------------------------------------ #
    # Guard reutilizable                                                  #
    # ------------------------------------------------------------------ #
    def _require_auth(self):
        if not Session.tenant_id:
            raise Exception("[AnalyticsService] No autenticado")
        return Session.tenant_id

    # ------------------------------------------------------------------ #
    # Dashboard completo                                                  #
    # ------------------------------------------------------------------ #
    def get_dashboard(self) -> dict:
        """
        Agrega todas las métricas en un único dict listo para la UI.
        Una sola llamada → menos roundtrips desde la vista.

        Returns:
            {
                "sales_by_day":   [...],   # [{day, total}]
                "avg_ticket":     float,
                "top_products":   [...],   # [{name, total_qty}]
                "total_revenue":  float,
                "growth_rate":    float,   # %
                "sales_today":    int,
            }
        """
        tenant_id = self._require_auth()

        # --- Queries paralelas (en Python síncrono, secuenciales) ---
        sales_res   = self.repo.sales_by_day(tenant_id)
        avg_res     = self.repo.average_ticket(tenant_id)
        top_res     = self.repo.top_products(tenant_id)
        revenue_res = self.repo.total_revenue(tenant_id)
        today_res   = self.repo.sales_count_today(tenant_id)

        sales_by_day  = sales_res.data or []
        avg_ticket    = float(avg_res.data or 0)
        top_products  = top_res.data or []
        revenue_rows  = revenue_res.data or []
        sales_today   = today_res.count if today_res.count is not None else 0

        total_revenue = sum(float(r["total"]) for r in revenue_rows if r.get("total"))

        return {
            "sales_by_day":  sales_by_day,
            "avg_ticket":    round(avg_ticket, 2),
            "top_products":  top_products,
            "total_revenue": round(total_revenue, 2),
            "growth_rate":   round(self._growth_rate(sales_by_day), 2),
            "sales_today":   sales_today,
        }

    # ------------------------------------------------------------------ #
    # Ventas por día (standalone, por si la vista la necesita por separado)
    # ------------------------------------------------------------------ #
    def get_daily_sales(self) -> list:
        tenant_id = self._require_auth()
        res = self.repo.sales_by_day(tenant_id)
        return res.data or []

    # ------------------------------------------------------------------ #
    # Top productos (standalone)                                          #
    # ------------------------------------------------------------------ #
    def get_top_products(self) -> list:
        tenant_id = self._require_auth()
        res = self.repo.top_products(tenant_id)
        return res.data or []

    # ------------------------------------------------------------------ #
    # Tasa de crecimiento                                                 #
    # ------------------------------------------------------------------ #
    def _growth_rate(self, sales_data: list) -> float:
        """
        Compara el total del primer día registrado vs el último.
        Devuelve porcentaje de cambio. Si no hay suficientes datos → 0.

        DECISIÓN: calculamos en Python (no en SQL) porque es una operación
        liviana sobre datos ya traídos, y queremos mantener la función SQL
        simple y reutilizable.
        """
        if len(sales_data) < 2:
            return 0.0

        first = float(sales_data[0].get("total", 0) or 0)
        last  = float(sales_data[-1].get("total", 0) or 0)

        if first == 0:
            return 0.0

        return ((last - first) / first) * 100