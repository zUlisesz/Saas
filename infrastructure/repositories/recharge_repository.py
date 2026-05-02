# infrastructure/repositories/recharge_repository.py
#
# NUEVA — Fase 6: Recargas Electrónicas
#
# DECISIÓN: Solo habla con Supabase vía RPCs. Sin lógica de negocio.
#
# POR QUÉ RPCs EN VEZ DE QUERIES DIRECTAS:
#   create_recharge y complete_recharge necesitan SECURITY DEFINER para
#   garantizar atomicidad (insertar + actualizar estado en una sola transacción)
#   sin que RLS interfiera. get_recharge_history es una query con join a users
#   que también requiere SECURITY DEFINER.
#
#   La excepción es get_by_external_id: es un SELECT simple filtrado por RLS
#   del tenant — no requiere SECURITY DEFINER y la query directa es más eficiente.
#
# NOTA SOBRE PARÁMETROS:
#   Todos los RPCs usan el prefijo p_ por convención del proyecto
#   (ver inventory_alert_repository.py, analytics_repository.py).

from config.supabase_client import supabase


class RechargeRepository:

    # ------------------------------------------------------------------ #
    # ESCRITURA                                                            #
    # ------------------------------------------------------------------ #

    def create(self, data: dict) -> str:
        """
        Registra una recarga en estado 'pending' vía RPC create_recharge.

        Args:
            data: dict con keys tenant_id, phone, operator, amount.
                  El campo status lo fija la RPC en 'pending'.

        Returns:
            UUID de la recarga recién creada (str).

        Raises:
            Exception: si la RPC falla (RLS, constraint, etc.)
        """
        try:
            res = supabase.rpc("create_recharge", {
                "p_tenant_id": data["tenant_id"],
                "p_phone":     data["phone"],
                "p_operator":  data["operator"],
                "p_amount":    data["amount"],
            }).execute()
            return res.data  # UUID retornado por la RPC
        except Exception as e:
            error_msg = str(e)
            if "row level security" in error_msg.lower():
                raise Exception("No tienes permisos para registrar recargas en este espacio de trabajo")
            raise

    def update_status(
        self,
        recharge_id:   str,
        status:        str,
        ext_tx_id:     str | None = None,
        ext_response:  dict | None = None,
    ) -> None:
        """
        Actualiza el estado de una recarga tras el procesamiento del proveedor.
        Llama RPC complete_recharge (idempotente por external_tx_id).

        Args:
            recharge_id:  UUID de la recarga a actualizar.
            status:       'success' | 'failed' | 'pending'
            ext_tx_id:    ID de transacción del proveedor externo (puede ser None si falló).
            ext_response: Respuesta raw del proveedor para auditoría (guardada como JSONB).
        """
        try:
            supabase.rpc("complete_recharge", {
                "p_recharge_id":  recharge_id,
                "p_status":       status,
                "p_ext_tx_id":    ext_tx_id,
                "p_ext_response": ext_response or {},
            }).execute()
        except Exception as e:
            error_msg = str(e)
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                raise Exception(
                    f"La transacción externa '{ext_tx_id}' ya fue registrada (duplicado)"
                )
            raise

    # ------------------------------------------------------------------ #
    # LECTURA                                                             #
    # ------------------------------------------------------------------ #

    def get_history(self, tenant_id: str, limit: int = 50) -> list[dict]:
        """
        Historial de recargas del tenant con nombre del cajero.
        Llama RPC get_recharge_history (join recharges → users en BD).

        Returns:
            Lista de dicts con keys: id, phone, operator, amount, status,
            created_at, cajero_name. Vacía si no hay recargas o si falla.
        """
        try:
            res = supabase.rpc("get_recharge_history", {
                "p_tenant_id": tenant_id,
                "p_limit":     limit,
            }).execute()
            return res.data or []
        except Exception as e:
            print(f"[RechargeRepo] get_history falló: {e}")
            return []

    def get_by_external_id(self, ext_tx_id: str) -> dict | None:
        """
        Busca una recarga por su ID de transacción externa.
        Usado para deduplicación: si existe, la recarga ya fue procesada.

        DECISIÓN: query directa (no RPC) porque es un SELECT simple;
        RLS del tenant filtra correctamente y no se necesita SECURITY DEFINER.

        Returns:
            Dict con los datos de la recarga, o None si no existe.
        """
        try:
            res = (
                supabase.table("recharges")
                .select("*")
                .eq("external_tx_id", ext_tx_id)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            return rows[0] if rows else None
        except Exception as e:
            print(f"[RechargeRepo] get_by_external_id falló: {e}")
            return None
