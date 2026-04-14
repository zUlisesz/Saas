# infrastructure/repositories/sale_repository.py

from config.supabase_client import supabase
from datetime import date


class SaleRepository:

    def create_sale(self, sale_data):
        return supabase.table("sales").insert(sale_data).execute()

    def create_sale_items(self, items):
        return supabase.table("sale_items").insert(items).execute()

    def create_payment(self, payment_data):
        return supabase.table("payments").insert(payment_data).execute()

    def get_all(self, tenant_id, limit=50):
        return (
            supabase.table("sales")
            .select("*, sale_items(*, products(name))")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    def get_today_stats(self, tenant_id):
        today = date.today().isoformat()
        return (
            supabase.table("sales")
            .select("id, total, status")
            .eq("tenant_id", tenant_id)
            .gte("created_at", today)
            .execute()
        )

    def get_by_id(self, sale_id):
        return (
            supabase.table("sales")
            .select("*, sale_items(*, products(name, sku)), payments(*)")
            .eq("id", sale_id)
            .single()
            .execute()
        )