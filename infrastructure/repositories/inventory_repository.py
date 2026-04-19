# infrastructure/repositories/inventory_repository.py
#
# CAMBIOS FASE 5 — Inventario Inteligente:
#
# NUEVOS MÉTODOS (en orden de adición):
#   get_inventory_with_status()    — RPC enriquecida: stock + thresholds + status
#   register_movement()            — RPC atómica: inventory + kardex + log + alerta
#   get_threshold()                — Leer threshold de un producto
#   upsert_threshold()             — Crear/actualizar threshold por producto
#   get_alerts()                   — Listar alertas por tenant (filtrable por status)
#   update_alert_status()          — Cambiar status de una alerta (ack/resolve/ignore)
#   get_movements_log()            — Historial detallado desde movements_log
#   get_reorder_list()             — Productos que necesitan reorden (stock <= reorder_point)
#
# DECISIÓN ARQUITECTÓNICA:
#   adjust_stock() y consume_stock() en el SERVICIO ya llamaban a upsert() + add_kardex_entry()
#   por separado. A partir de Fase 5, delegan a register_movement() (RPC atómica en Supabase)
#   que hace inventory + kardex + movements_log + alerta en una sola transacción.
#   Esto elimina el riesgo de kardex sin actualización de stock o viceversa.
#
# RETRO-COMPATIBILIDAD:
#   Los métodos legacy (decrement_stock, upsert, add_kardex_entry, log_movement) se conservan
#   para no romper código que los llame durante la transición. Se marcan con # LEGACY.
#
# PRINCIPIO: cero lógica de negocio en este archivo — solo persistencia.

from config.supabase_client import supabase


class InventoryRepository:

    # ================================================================== #
    # CONSULTAS BASE                                                     #
    # ================================================================== #

    def get_stock(self, product_id: str):
        return (
            supabase.table("inventory")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )

    def get_all(self, tenant_id: str):
        """
        Inventario del tenant con datos del producto (join).
        DECISIÓN: inner join para evitar N+1.
        """
        return (
            supabase.table("inventory")
            .select("*, products!inner(id, name, sku, price, cost, tenant_id, barcode)")
            .eq("products.tenant_id", tenant_id)
            .execute()
        )

    # ================================================================== #
    # NUEVO F5 — Vista enriquecida con status                           #
    # ================================================================== #

    def get_inventory_with_status(self, tenant_id: str):
        """
        RPC get_inventory_with_status: join de products + inventory + thresholds.
        Retorna stock_status = ok | warning | critical | out_of_stock.

        JUSTIFICACIÓN: evita hacer 3 queries separadas desde el servicio para
        obtener el mismo dato. La lógica de clasificación vive en SQL (más eficiente).
        """
        return supabase.rpc(
            "get_inventory_with_status",
            {"p_tenant_id": tenant_id},
        ).execute()

    # ================================================================== #
    # NUEVO F5 — Movimiento atómico vía RPC                             #
    # ================================================================== #

    def register_movement(
        self,
        tenant_id: str,
        product_id: str,
        movement_type: str,
        quantity_change: int,
        reference_type: str = None, #type: ignore
        reference_id: str = None, #type: ignore
        notes: str = None, #type: ignore
        created_by: str = None, #type: ignore
    ):
        """
        Llama a register_inventory_movement() que actualiza en una sola transacción:
          1. inventory.stock_actual
          2. kardex (fila de historial)
          3. inventory_movements_log (fila de auditoría)
          4. inventory_alerts (si stock baja del mínimo)

        Retorna UUID del movements_log generado, o None si hubo error.

        TIPOS VÁLIDOS: sale | purchase | adjustment | return | damage | inventory_count
        quantity_change NEGATIVO para salidas, POSITIVO para entradas.
        """
        try:
            params = {
                "p_tenant_id":       tenant_id,
                "p_product_id":      product_id,
                "p_movement_type":   movement_type,
                "p_quantity_change": quantity_change,
            }
            if reference_type: params["p_reference_type"] = reference_type
            if reference_id:   params["p_reference_id"]   = reference_id
            if notes:          params["p_notes"]           = notes
            if created_by:     params["p_created_by"]      = created_by

            return supabase.rpc("register_inventory_movement", params).execute()
        except Exception as e:
            raise Exception(f"Error en movimiento de inventario: {e}")

    # ================================================================== #
    # NUEVO F5 — Thresholds CRUD                                        #
    # ================================================================== #

    def get_threshold(self, product_id: str):
        """Obtiene el threshold de un producto específico."""
        return (
            supabase.table("inventory_thresholds")
            .select("*")
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        )

    def get_all_thresholds(self, tenant_id: str):
        """Todos los thresholds del tenant."""
        return (
            supabase.table("inventory_thresholds")
            .select("*")
            .eq("tenant_id", tenant_id)
            .execute()
        )

    def upsert_threshold(
        self,
        tenant_id: str,
        product_id: str,
        stock_minimo: int,
        stock_maximo: int,
        reorder_point: int,
        reorder_quantity: int,
        alert_on_low_stock: bool = True,
        alert_on_overstock: bool = False,
    ):
        """
        Crea o actualiza threshold para un producto.
        CONFLICT: se resuelve por UNIQUE (tenant_id, product_id).
        """
        return (
            supabase.table("inventory_thresholds")
            .upsert(
                {
                    "tenant_id":          tenant_id,
                    "product_id":         product_id,
                    "stock_minimo":       stock_minimo,
                    "stock_maximo":       stock_maximo,
                    "reorder_point":      reorder_point,
                    "reorder_quantity":   reorder_quantity,
                    "alert_on_low_stock": alert_on_low_stock,
                    "alert_on_overstock": alert_on_overstock,
                    "updated_at":         "now()",
                },
                on_conflict="tenant_id,product_id",
            )
            .execute()
        )

    # ================================================================== #
    # NUEVO F5 — Alerts                                                  #
    # ================================================================== #

    def get_alerts(self, tenant_id: str, status: str = "new"):
        """
        Alertas por tenant, filtradas por status.
        JOIN con products para obtener nombre del producto.
        """
        query = (
            supabase.table("inventory_alerts")
            .select("*, products!inner(name, sku, barcode)")
            .eq("tenant_id", tenant_id)
            .order("generated_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        return query.execute()

    def get_alerts_count(self, tenant_id: str, status: str = "new") -> int:
        """Conteo rápido de alertas — para badge en sidebar."""
        try:
            res = (
                supabase.table("inventory_alerts")
                .select("id", count="exact") #type:ignore
                .eq("tenant_id", tenant_id)
                .eq("status", status)
                .execute()
            )
            return res.count or 0
        except Exception:
            return 0

    def update_alert_status(
        self,
        alert_id: str,
        new_status: str,
        user_id: str = None, #type: ignore
    ):
        """
        Cambia el status de una alerta.
        Actualiza acknowledged_at / resolved_at según corresponda.

        STATUS VÁLIDOS: acknowledged | resolved | ignored
        """
        data = {"status": new_status}
        if new_status == "acknowledged":
            data["acknowledged_at"] = "now()"
            if user_id:
                data["acknowledged_by"] = user_id
        elif new_status == "resolved":
            data["resolved_at"] = "now()"

        return (
            supabase.table("inventory_alerts")
            .update(data)
            .eq("id", alert_id)
            .execute()
        )

    def bulk_update_alerts_status(self, tenant_id: str, new_status: str):
        """Marcar todas las alertas 'new' del tenant como acknowledged."""
        data = {"status": new_status}
        if new_status == "acknowledged":
            data["acknowledged_at"] = "now()"
        return (
            supabase.table("inventory_alerts")
            .update(data)
            .eq("tenant_id", tenant_id)
            .eq("status", "new")
            .execute()
        )

    # ================================================================== #
    # NUEVO F5 — Movements log                                          #
    # ================================================================== #

    def get_movements_log(
        self,
        tenant_id: str,
        product_id: str = None, #type:ignore
        limit: int = 50,
    ):
        """
        Historial de movements_log (más rico que kardex en algunos campos).
        Filtrable por producto.
        """
        query = (
            supabase.table("inventory_movements_log")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if product_id:
            query = query.eq("product_id", product_id)
        return query.execute()

    # ================================================================== #
    # NUEVO F5 — Reorder list                                           #
    # ================================================================== #

    def get_reorder_list(self, tenant_id: str):
        """
        Productos que necesitan reorden: stock_actual <= reorder_point.
        JOIN manual vía Supabase: inventory + thresholds + products.

        NOTA: No hay RPC para esto, pero el join es sencillo y se hace
        filtrando en Python tras obtener get_inventory_with_status().
        Usamos esa RPC y filtramos aquí para mantener consistencia.
        """
        return self.get_inventory_with_status(tenant_id)

    # ================================================================== #
    # NUEVO F5 — Stock bajo (RPC existente, mantenida)                  #
    # ================================================================== #

    def get_low_stock(self, tenant_id: str):
        """
        RPC low_stock_products: stock_actual <= stock_minimo.
        MANTENIDA para retro-compatibilidad con código existente.
        """
        return supabase.rpc(
            "low_stock_products", {"tenant": tenant_id}
        ).execute()

    # ================================================================== #
    # LEGACY — Conservados por retro-compatibilidad                     #
    # ================================================================== #

    def upsert(self, product_id: str, stock_actual: int, stock_minimo: int = 5):
        """LEGACY — Usar register_movement() para nuevas operaciones."""
        try:
            return (
                supabase.table("inventory")
                .upsert(
                    {
                        "product_id":   product_id,
                        "stock_actual": stock_actual,
                        "stock_minimo": stock_minimo,
                    },
                    on_conflict="product_id",
                )
                .execute()
            )
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para actualizar el inventario")
            raise

    def decrement_stock(self, product_id: str, quantity: int):
        """LEGACY — Usar register_movement(movement_type='sale') para nuevas ventas."""
        current = self.get_stock(product_id)
        if current.data and len(current.data) > 0:
            stock_ant  = current.data[0]["stock_actual"] #type: ignore
            stock_min  = current.data[0]["stock_minimo"] #type: ignore
            stock_post = max(0, stock_ant - quantity) #type: ignore
            self.upsert(product_id, stock_post, stock_min) #type: ignore
            return stock_ant, stock_post
        return 0, 0

    def add_kardex_entry(self, entry: dict):
        """LEGACY — register_movement() llama a kardex internamente. Conservada por compatibilidad."""
        try:
            return supabase.table("kardex").insert(entry).execute()
        except Exception as e:
            print(f"[KARDEX WARNING] No se pudo registrar movimiento: {e}")
            return None

    def get_kardex(self, tenant_id: str, product_id: str, limit: int = 50):
        """Historial kardex vía RPC (existente desde pre-F5)."""
        return supabase.rpc(
            "kardex_by_product",
            {"p_tenant": tenant_id, "p_product": product_id, "p_limit": limit},
        ).execute()

    def log_movement(
        self,
        product_id: str,
        movement_type: str,
        quantity: int,
        reference_id=None,
    ):
        """LEGACY — Escribe en stock_movements (tabla original). Conservada."""
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