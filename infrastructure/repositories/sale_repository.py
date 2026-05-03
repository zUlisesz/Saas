# infrastructure/repositories/sale_repository.py

from config.supabase_client import get_client
from datetime import date


class SaleRepository:

    def __init__(self, client=None):
        self._db = client or get_client()

    def create_sale(self, sale_data):
        # Ensure tenant_id is present for RLS policy
        if "tenant_id" not in sale_data or not sale_data["tenant_id"]:
            raise ValueError("tenant_id es requerido para crear una venta")
        try:
            res = self._db.table("sales").insert(sale_data).execute()
            return res
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para crear ventas en este espacio de trabajo")
            raise

    def create_sale_items(self, items):
        if not items:
            return None
        try:
            res = self._db.table("sale_items").insert(items).execute()
            return res
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para crear items de venta")
            raise

    def create_payment(self, payment_data):
        try:
            res = self._db.table("payments").insert(payment_data).execute()
            return res
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para crear pagos")
            raise

    def get_all(self, tenant_id, limit=50):
        return (
            self._db.table("sales")
            .select("*, sale_items(*, products(name)), payments(*)")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    def get_today_stats(self, tenant_id):
        today = date.today().isoformat()
        return (
            self._db.table("sales")
            .select("id, total, status")
            .eq("tenant_id", tenant_id)
            .gte("created_at", today)
            .execute()
        )

    def get_by_id(self, sale_id):
        return (
            self._db.table("sales")
            .select("*, sale_items(*, products(name, sku)), payments(*)")
            .eq("id", sale_id)
            .single()
            .execute()
        )

    def delete_sale(self, sale_id: str):
        """
        Elimina una venta y sus registros relacionados.
        Orden obligatorio: payments → sale_items → sales.
        La FK payments→sales es RESTRICT: borrar la venta con pagos activos
        lanza error en Postgres, por eso se eliminan primero.
        """
        try:
            self._db.table("payments").delete().eq("sale_id", sale_id).execute()
        except Exception:
            pass
        try:
            self._db.table("sale_items").delete().eq("sale_id", sale_id).execute()
        except Exception:
            pass
        return self._db.table("sales").delete().eq("id", sale_id).execute()