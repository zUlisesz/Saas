# infrastructure/repositories/recharge_repository.py
#
# Fase 6: Repositorio de Recargas Electrónicas.
#
# DECISIONES:
#   Solo RPCs para escritura (create, update_status): las RPCs tienen
#   SECURITY DEFINER y garantizan atomicidad. Llamar directo a la tabla
#   puede violar RLS en edge cases.
#
#   get_by_external_id() usa query directa (.from_): es un SELECT simple
#   de solo lectura, protegido por el índice parcial idx_recharges_ext_tx
#   y por RLS. Si en el futuro requiere bypassear RLS se crea un RPC.
#
#   _map_to_entity() y _map_to_history_item(): patrón Data Mapper.
#   Si la BD cambia un nombre de columna, solo se edita aquí.
#
#   try/except en cada método público: los errores de Supabase son
#   detalles de infraestructura que no deben filtrarse al dominio.
#   Se envuelven en RepositoryError.
#
#   update_status() loguea a ERROR (no solo WARNING) porque un fallo
#   aquí deja el registro en estado inconsistente: el proveedor ya
#   procesó la recarga pero BD dice 'pending'.
#
#   No hay Session.tenant_id aquí: el tenant_id lo pasa el servicio.
#   El repo es stateless — más fácil de testear.

from typing import Optional

from config.supabase_client import supabase
from infrastructure.logging_config import get_logger
from domain.models.recharge import Recharge
from domain.schemas.recharge_schemas import RechargeHistoryItem
from domain.exceptions import RepositoryError

_log = get_logger(__name__)


class RechargeRepository:

    # ── ESCRITURA ──────────────────────────────────────────────────────────

    def create(
        self,
        *,
        tenant_id:  str,
        phone:      str,
        operator:   str,
        amount:     float,
        created_by: str,
    ) -> str:
        """
        Crea una recarga con status='pending' vía RPC create_recharge.
        Retorna el UUID del registro creado.
        Lanza RepositoryError si Supabase falla.
        """
        try:
            result = supabase.rpc("create_recharge", {
                "p_tenant_id":  tenant_id,
                "p_phone":      phone,
                "p_operator":   operator,
                "p_amount":     amount,
                "p_created_by": created_by,
            }).execute()

            if result.data is None:
                raise RepositoryError("create_recharge RPC retornó None")

            return str(result.data)

        except RepositoryError:
            raise
        except Exception as exc:
            _log.error("RechargeRepository.create falló: %s", exc)
            raise RepositoryError(f"Error al crear recarga en BD: {exc}") from exc

    def update_status(
        self,
        *,
        recharge_id:  str,
        status:       str,
        ext_tx_id:    Optional[str]  = None,
        ext_response: Optional[dict] = None,
    ) -> None:
        """
        Actualiza status + datos externos de un recharge vía RPC complete_recharge.
        Llamar después de que el provider responda (éxito, fallo o timeout).
        Lanza RepositoryError si Supabase falla.
        """
        try:
            supabase.rpc("complete_recharge", {
                "p_recharge_id":  recharge_id,
                "p_status":       status,
                "p_ext_tx_id":    ext_tx_id,
                "p_ext_response": ext_response,
            }).execute()

        except Exception as exc:
            # ERROR (no WARNING): el provider ya procesó la recarga pero no
            # pudimos guardar el resultado. Registro queda en estado inconsistente.
            _log.error(
                "RechargeRepository.update_status FALLÓ para %s — status=%s. "
                "El registro queda en estado inconsistente. Error: %s",
                recharge_id, status, exc,
            )
            raise RepositoryError(
                f"No se pudo actualizar estado de recarga {recharge_id}: {exc}"
            ) from exc

    # ── LECTURA ────────────────────────────────────────────────────────────

    def get_history(
        self,
        *,
        tenant_id: str,
        limit:     int = 50,
    ) -> list[RechargeHistoryItem]:
        """
        Historial de recargas del tenant vía RPC get_recharge_history.
        La RPC hace JOIN con auth.users para obtener cajero_name.
        Lanza RepositoryError si Supabase falla (lista vacía no es error).
        """
        try:
            result = supabase.rpc("get_recharge_history", {
                "p_tenant_id": tenant_id,
                "p_limit":     limit,
            }).execute()

            rows = result.data or []
            return [self._map_to_history_item(row) for row in rows]

        except Exception as exc:
            _log.error("RechargeRepository.get_history falló: %s", exc)
            raise RepositoryError(f"Error al obtener historial: {exc}") from exc

    def get_by_external_id(self, ext_tx_id: str) -> Optional[Recharge]:
        """
        Busca una recarga por external_tx_id (para deduplicación).
        Retorna None si no existe — no lanza excepción.
        El servicio decide si un None implica error o no.

        Query directa (no RPC): SELECT de solo lectura, RLS del tenant aplica,
        protegido por índice idx_recharges_ext_tx.
        """
        try:
            result = (
                supabase
                .from_("recharges")
                .select("*")
                .eq("external_tx_id", ext_tx_id)
                .maybe_single()
                .execute()
            )
            if result.data is None:
                return None
            return self._map_to_entity(result.data)

        except Exception as exc:
            # No lanzar RepositoryError — la deduplicación es best-effort.
            # Si falla la búsqueda, el servicio procede y confía en el
            # UNIQUE constraint de BD para rechazar el duplicado.
            _log.warning("RechargeRepository.get_by_external_id falló: %s", exc)
            return None

    # ── MAPPING INTERNO ────────────────────────────────────────────────────

    def _map_to_entity(self, row: dict) -> Recharge:
        return Recharge(
            id=                row["id"],
            tenant_id=         row["tenant_id"],
            phone=             row["phone"],
            operator=          row["operator"],
            amount=            float(row["amount"]),
            currency=          row.get("currency", "BOB"),
            status=            row["status"],
            created_at=        row["created_at"],
            created_by=        row["created_by"],
            external_tx_id=    row.get("external_tx_id"),
            external_response= row.get("external_response"),
            error_code=        row.get("error_code"),
            error_message=     row.get("error_message"),
            completed_at=      row.get("completed_at"),
        )

    def _map_to_history_item(self, row: dict) -> RechargeHistoryItem:
        return RechargeHistoryItem(
            id=          row["id"],
            phone=       row["phone"],
            operator=    row["operator"],
            amount=      float(row["amount"]),
            status=      row["status"],
            created_at=  row["created_at"],
            cajero_name= row.get("cajero_name", "—"),
        )
