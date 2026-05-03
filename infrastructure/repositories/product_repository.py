# infrastructure/repositories/product_repository.py
#
# CAMBIOS (Fase 4 — Código de Barras):
#
# 1. get_by_barcode(tenant_id, barcode) — nueva consulta para el escáner del POS.
#    DECISIÓN: filtramos SIEMPRE por tenant_id además del barcode.
#    Así dos tenants pueden tener el mismo barcode sin colisionar.
#
# 2. search() — ahora también busca en el campo barcode con ilike.
#    Útil si el cajero escribe manualmente parte del código.
#
# PRINCIPIO: este repositorio SOLO habla con Supabase.
# Ninguna lógica de negocio aquí — eso es responsabilidad de ProductService.

from config.supabase_client import get_client


class ProductRepository:

    def __init__(self, client=None):
        self._db = client or get_client()

    def get_all(self, tenant_id):
        return (
            self._db.table("products")
            .select("*, categories(name)")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .order("name")
            .execute()
        )

    def get_by_id(self, product_id):
        return (
            self._db.table("products")
            .select("*, categories(name)")
            .eq("id", product_id)
            .single()
            .execute()
        )

    # ------------------------------------------------------------------ #
    # NUEVO Fase 4 — Búsqueda exacta por código de barras               #
    # ------------------------------------------------------------------ #
    def get_by_barcode(self, tenant_id: str, barcode: str):
        """
        Devuelve el producto cuyo barcode coincide exactamente.
        Filtra por tenant_id para garantizar aislamiento multi-tenant.

        DECISIÓN: usamos .limit(1) y no .single() porque single() lanza
        excepción si no encuentra nada, lo que rompería el flujo del POS.
        El servicio se encarga de verificar si data está vacía.
        """
        return (
            self._db.table("products")
            .select("*, categories(name)")
            .eq("tenant_id", tenant_id)
            .eq("barcode", barcode)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

    def search(self, tenant_id, query):
        """
        CAMBIO Fase 4: ahora busca tanto en 'name' como en 'barcode'.
        Supabase no soporta OR nativo con ilike en el cliente Python de forma
        directa, así que hacemos dos queries y unimos en Python.
        DECISIÓN: prioridad al match de name (más probable en uso cotidiano).
        """
        name_res = (
            self._db.table("products")
            .select("*, categories(name)")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .ilike("name", f"%{query}%")
            .execute()
        )
        barcode_res = (
            self._db.table("products")
            .select("*, categories(name)")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .ilike("barcode", f"%{query}%")
            .execute()
        )
        # Unir resultados sin duplicados (por id)
        name_data    = name_res.data or []
        barcode_data = barcode_res.data or []
        seen_ids     = {p["id"] for p in name_data} #type: ignore pRoblemas
        combined     = name_data + [p for p in barcode_data if p["id"] not in seen_ids] #type: ignore

        # Devolvemos un objeto duck-typed compatible con el patrón .data
        class _FakeResult:
            def __init__(self, data): self.data = data
        return _FakeResult(combined)

    def create(self, data):
        if "tenant_id" not in data or not data["tenant_id"]:
            raise ValueError("tenant_id es requerido para crear un producto")
        try:
            return self._db.table("products").insert(data).execute()
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para crear productos en este espacio de trabajo")
            raise

    def update(self, product_id, data):
        try:
            return (
                self._db.table("products")
                .update(data)
                .eq("id", product_id)
                .execute()
            )
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para actualizar este producto")
            raise

    def soft_delete(self, product_id):
        try:
            return (
                self._db.table("products")
                .update({"is_active": False})
                .eq("id", product_id)
                .execute()
            )
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para eliminar este producto")
            raise

    def count(self, tenant_id):
        return (
            self._db.table("products")
            .select("id", count="exact")  # type: ignore
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .execute()
        )

    # ------------------------------------------------------------------ #
    # Fase 4 — Barcodes pendientes e historial                           #
    # ------------------------------------------------------------------ #

    def get_pending_products(self, tenant_id: str):
        """Productos cuyo barcode aún es PENDING-* (sin barcode real asignado)."""
        return (
            self._db.table("products")
            .select("id, name, barcode, barcode_type")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .like("barcode", "PENDING-%")
            .execute()
        )

    def add_barcode_history(self, data: dict):
        """Inserta una entrada en product_barcode_history. Fire & forget."""
        try:
            self._db.table("product_barcode_history").insert(data).execute()
        except Exception:
            pass  # No interrumpir el flujo principal si el historial falla

    def get_barcode_stats(self, tenant_id: str) -> dict:
        """Llama a la RPC barcode_coverage_stats() creada en migración 8."""
        try:
            res = self._db.rpc(
                "barcode_coverage_stats", {"p_tenant_id": tenant_id}
            ).execute()
            return (res.data or [{}])[0]
        except Exception:
            return {}