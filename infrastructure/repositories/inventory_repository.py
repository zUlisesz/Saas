# infrastructure/repositories/inventory_repository.py
#
# FASE 5 — ACTUALIZACIÓN (22 Abril 2026)
#
# CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
#
#   1. get_all_with_alerts(tenant_id) — NUEVO
#      Llama a RPC get_inventory_with_alerts() creada en migración 20260422.
#      Devuelve datos desnormalizados: producto + stock + umbrales + estado + alertas.
#      REEMPLAZA el uso de get_all() en InventoryService.list_inventory().
#      DECISIÓN: get_all() se conserva para backward compat (SaleService lo usa vía
#      consume_stock, que no necesita los datos extra de alertas).
#
#   2. get_low_stock_report(tenant_id) — NUEVO
#      Llama a RPC get_low_stock_report(). Más liviana que get_all_with_alerts.
#      Para el badge de alertas en sidebar/header y el dashboard banner.
#      REEMPLAZA get_low_stock() que llamaba a la RPC obsoleta 'low_stock_products'.
#
#   3. get_thresholds(tenant_id) — NUEVO
#      Lee inventory_thresholds directamente para la UI de configuración.
#
#   4. upsert_threshold(data) — NUEVO
#      Inserta o actualiza un threshold con ON CONFLICT(tenant_id, product_id).
#      DECISIÓN: el upsert lo hace el repo, la validación la hace el servicio.
#
#   5. get_movements_log(product_id, tenant_id, limit) — NUEVO
#      Lee inventory_movements_log para el historial extendido.
#      COMPLEMENTA get_kardex() que ya lee la tabla kardex.
#
# MÉTODOS CONSERVADOS (sin cambios — backward compat):
#   get_stock, get_all, upsert, decrement_stock,
#   log_movement, add_kardex_entry, get_kardex
#
# PRINCIPIO MANTENIDO: cero lógica de negocio en este archivo.

from config.supabase_client import supabase


class InventoryRepository:

    # ------------------------------------------------------------------ #
    # LECTURA — Stock individual                                          #
    # ------------------------------------------------------------------ #

    def get_stock(self, product_id: str):
        """Stock actual de un producto. Usado por consume_stock() y init_stock()."""
        return (
            supabase.table("inventory")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )

    # ------------------------------------------------------------------ #
    # LECTURA — Inventario completo (legacy — conservado)                 #
    # ------------------------------------------------------------------ #

    def get_all(self, tenant_id: str):
        """
        Join directo inventory + products. Conservado para backward compat.
        InventoryService.list_inventory() ahora usa get_all_with_alerts().
        SaleService.consume_stock() no llama a este método — no afecta.
        """
        return (
            supabase.table("inventory")
            .select("*, products!inner(id, name, sku, price, cost, tenant_id, barcode)")
            .eq("products.tenant_id", tenant_id)
            .execute()
        )

    # ------------------------------------------------------------------ #
    # LECTURA — Inventario completo con alertas (NUEVO — Fase 5)         #
    # ------------------------------------------------------------------ #

    def get_all_with_alerts(self, tenant_id: str):
        """
        Llama a RPC get_inventory_with_alerts(p_tenant_id).

        Retorna por fila:
            product_id, product_name, barcode, category_name,
            stock_actual, stock_minimo, stock_maximo,
            reorder_point, reorder_quantity,
            stock_status (ok|low|out_of_stock|overstock),
            active_alerts (int), updated_at

        DECISIÓN: la RPC calcula stock_status en BD (no en Python)
        para evitar lógica duplicada entre repo y servicio.
        SECURITY DEFINER en la función permite que RLS no bloquee
        los joins internos.
        """
        return supabase.rpc(
            "get_inventory_with_alerts",
            {"p_tenant_id": tenant_id},
        ).execute()

    # ------------------------------------------------------------------ #
    # LECTURA — Reporte de stock bajo (NUEVO — Fase 5)                   #
    # ------------------------------------------------------------------ #

    def get_low_stock_report(self, tenant_id: str):
        """
        Llama a RPC get_low_stock_report(p_tenant_id).
        Solo productos con stock_actual <= stock_minimo.

        Más liviana que get_all_with_alerts — para badges y banners.
        REEMPLAZA get_low_stock() que usaba RPC obsoleta.
        """
        return supabase.rpc(
            "get_low_stock_report",
            {"p_tenant_id": tenant_id},
        ).execute()

    def get_low_stock(self, tenant_id: str):
        """
        LEGACY — conservado para compatibilidad.
        Redirige a get_low_stock_report() para no romper código existente.
        """
        return self.get_low_stock_report(tenant_id)

    # ------------------------------------------------------------------ #
    # ESCRITURA — Upsert stock                                            #
    # ------------------------------------------------------------------ #

    def upsert(self, product_id: str, stock_actual: int, stock_minimo: int = 5):
        """
        Inserta o actualiza el registro de inventory.
        ON CONFLICT(product_id) → UPDATE.
        """
        return (
            supabase.table("inventory")
            .upsert(
                {
                    "product_id":   product_id,
                    "stock_actual": max(0, stock_actual),
                    "stock_minimo": max(0, stock_minimo),
                    "updated_at":   "now()",
                },
                on_conflict="product_id",
            )
            .execute()
        )

    def decrement_stock(self, product_id: str, quantity: int):
        """
        LEGACY — conservado para SaleService backward compat.
        Decrementa stock y retorna (stock_anterior, stock_posterior).
        """
        current = self.get_stock(product_id)
        if current.data and len(current.data) > 0:
            stock_ant  = current.data[0]["stock_actual"] #type: ignore
            stock_min  = current.data[0]["stock_minimo"] #type: ignore
            stock_post = max(0, stock_ant - quantity) #type: ignore
            self.upsert(product_id, stock_post, stock_min) #type: ignore
            return stock_ant, stock_post
        return 0, 0

    # ------------------------------------------------------------------ #
    # LECTURA/ESCRITURA — Thresholds (NUEVO — Fase 5)                    #
    # ------------------------------------------------------------------ #

    def get_thresholds(self, tenant_id: str):
        """
        Lee todos los umbrales de un tenant con datos de producto.
        Incluye join a products para mostrar nombre en la UI.
        """
        return (
            supabase.table("inventory_thresholds")
            .select("*, products(id, name, barcode)")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=False)
            .execute()
        )

    def get_threshold_by_product(self, tenant_id: str, product_id: str):
        """Umbral específico de un producto. None si no existe."""
        return (
            supabase.table("inventory_thresholds")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        )

    def upsert_threshold(self, data: dict):
        """
        Inserta o actualiza un threshold.
        data debe contener: tenant_id, product_id.
        Opcional: stock_minimo, stock_maximo, reorder_point,
                  reorder_quantity, alert_on_low_stock, alert_on_overstock.

        ON CONFLICT(tenant_id, product_id) → UPDATE.
        DECISIÓN: la validación (min < max, reorder >= min) la hace
        InventoryService antes de llamar aquí.
        """
        return (
            supabase.table("inventory_thresholds")
            .upsert(data, on_conflict="tenant_id,product_id")
            .execute()
        )

    # ------------------------------------------------------------------ #
    # LECTURA — Historial de movimientos extendido (NUEVO — Fase 5)      #
    # ------------------------------------------------------------------ #

    def get_movements_log(self, tenant_id: str, product_id: str, limit: int = 50):
        """
        Lee inventory_movements_log para el historial detallado.
        COMPLEMENTA get_kardex() — ambas tablas registran movimientos
        pero movements_log tiene movement_type explícito y quantity_before/after.

        DECISIÓN: ambas tablas se mantienen porque kardex es la fuente
        contable oficial (requerimiento del negocio) y movements_log
        es la fuente técnica para debugging/auditoría.
        """
        return (
            supabase.table("inventory_movements_log")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("product_id", product_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    # ------------------------------------------------------------------ #
    # Log de movimientos (legacy — conservado)                            #
    # ------------------------------------------------------------------ #

    def log_movement(self, product_id: str, movement_type: str,
                     quantity: int, reference_id=None):
        """LEGACY — tabla stock_movements. Conservado para historial previo."""
        try:
            return (
                supabase.table("stock_movements")
                .insert(
                    {
                        "product_id":   product_id,
                        "type":         movement_type,
                        "quantity":     quantity,
                        "reference_id": reference_id,
                    }
                )
                .execute()
            )
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para registrar movimientos")
            raise

    # ------------------------------------------------------------------ #
    # Kardex (Fase 5 — conservado)                                        #
    # ------------------------------------------------------------------ #

    def add_kardex_entry(self, entry: dict):
        """
        Inserta una fila en kardex.
        PRINCIPIO: no calculamos saldos aquí — el servicio los trae calculados.
        Falla silenciosamente (kardex es observabilidad, no bloquea la venta).
        """
        try:
            return supabase.table("kardex").insert(entry).execute()
        except Exception as e:
            print(f"[KARDEX WARNING] No se pudo registrar movimiento: {e}")
            return None

    def get_kardex(self, tenant_id: str, product_id: str, limit: int = 50):
        """Historial kardex de un producto. Fuente contable oficial."""
        return supabase.rpc(
            "kardex_by_product",
            {"p_tenant": tenant_id, "p_product": product_id, "p_limit": limit},
        ).execute()