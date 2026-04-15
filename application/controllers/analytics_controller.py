# application/controllers/analytics_controller.py
#
# JUSTIFICACIÓN:
# El controller vive en 'application' porque su única responsabilidad es
# orquestar: recibir la petición de la vista, llamar al servicio y
# devolver/imprimir el resultado.
#
# NO contiene lógica de negocio (eso es dominio).
# NO habla con la base de datos (eso es infraestructura).
#
# PATRÓN SEGUIDO:
# Idéntico a AuthController y ProductController:
#   __init__ recibe el servicio por inyección.
#   Cada método public corresponde a una acción de la UI.
#
# NOTA SOBRE LA VISTA:
# Los métodos devuelven los datos además de imprimirlos, para que
# dashboard_view.py (Flet) pueda consumir el dict directamente sin
# tener que llamar al servicio por su cuenta.

class AnalyticsController:

    def __init__(self, service):
        """
        Args:
            service: AnalyticsService — inyectado desde main.py.
        """
        self.service = service

    def get_dashboard(self) -> dict:
        """
        Punto de entrada principal para dashboard_view.py.
        Devuelve el dict completo de métricas.
        """
        try:
            data = self.service.get_dashboard()
            self._print_dashboard(data)
            return data
        except Exception as e:
            print(f"[ANALYTICS ERROR] {e}")
            return {}

    def show_daily_sales(self):
        try:
            sales = self.service.get_daily_sales()
            print("\n📅 Ventas por día:")
            for row in sales:
                print(f"  {row.get('day')} → ${row.get('total', 0):.2f}")
            return sales
        except Exception as e:
            print(f"[ANALYTICS ERROR] {e}")
            return []


    def show_top_products(self):
        try:
            products = self.service.get_top_products()
            print("\n🏆 Top productos:")
            for i, p in enumerate(products, 1):
                print(f"  {i}. {p.get('name')} — {p.get('total_qty', 0)} unidades")
            return products
        except Exception as e:
            print(f"[ANALYTICS ERROR] {e}")
            return []

    # ------------------------------------------------------------------ #
    # Helper de impresión (CLI / logs)                                   #
    # ------------------------------------------------------------------ #
    def _print_dashboard(self, data: dict):
        print("\n" + "=" * 40)
        print("       📊 ANALYTICS DASHBOARD")
        print("=" * 40)
        print(f"  💰 Ingresos totales : ${data.get('total_revenue', 0):.2f}")
        print(f"  🧾 Ticket promedio  : ${data.get('avg_ticket', 0):.2f}")
        print(f"  📈 Crecimiento      : {data.get('growth_rate', 0):.1f}%")
        print(f"  🛒 Ventas hoy       : {data.get('sales_today', 0)}")
        print("=" * 40)