# application/use_cases/create_sale_use_case.py
#
# PATRÓN Use Case (DDD Application Layer).
#
# PROBLEMA QUE RESUELVE:
#   En SaleService.create_sale() había un bug de consistencia:
#     1. Se inserta el header de venta (sale)
#     2. Si la inserción de sale_items falla → la venta queda HUÉRFANA en BD
#     3. Si la inserción del pago falla     → la venta queda SIN PAGO en BD
#   No había rollback ni cleanup.
#
# SOLUCIÓN:
#   Este use case orquesta el flujo completo con cleanup explícito si falla
#   en los pasos críticos (items y pago). Los pasos no-críticos (inventario,
#   evento) nunca revierten la venta — son fire-and-forget.
#
# FLUJO:
#   1. Validar request  → ValidationError / BusinessRuleError si falla
#   2. Crear header     → RepositoryError si falla
#   3. Insertar items   → RepositoryError + cleanup si falla
#   4. Registrar pago   → RepositoryError + cleanup si falla
#   5. Actualizar stock → silencioso (no crítico)
#   6. Emitir evento    → silencioso (fire & forget)

from domain.schemas.sale_schemas import CreateSaleRequest
from domain.exceptions import AuthenticationError, RepositoryError
from session.session import Session
from infrastructure.logging_config import get_logger

_log = get_logger(__name__)


class CreateSaleUseCase:

    def __init__(self, sale_repo, inventory_service=None, event_service=None):
        """
        Args:
            sale_repo:         SaleRepository   (requerido)
            inventory_service: InventoryService  (opcional — sin él no hay kardex)
            event_service:     EventService      (opcional — sin él no hay eventos)
        """
        self.sale_repo         = sale_repo
        self.inventory_service = inventory_service
        self.event_service     = event_service

    def execute(self, request: CreateSaleRequest) -> dict:
        """
        Ejecuta la creación completa de una venta.

        Args:
            request: CreateSaleRequest (aún sin validar).

        Returns:
            dict con {sale, total, change, items} — mismo formato que
            SaleService.create_sale() para no romper vistas existentes.

        Raises:
            AuthenticationError:           sin sesión activa.
            ValidationError / BusinessRuleError: request inválido.
            RepositoryError:               fallo de persistencia crítico.
        """
        # ── 0. Guardia de autenticación ────────────────────────────
        if not Session.tenant_id or not Session.current_user:
            raise AuthenticationError("No hay sesión activa")

        # ── 1. Validación (lanza ValidationError / BusinessRuleError) ─
        request.validate()

        # ── 2. Crear header de venta ───────────────────────────────
        sale_res = self.sale_repo.create_sale({
            "tenant_id": Session.tenant_id,
            "user_id":   Session.current_user.id,
            "total":     request.total,
            "status":    "completed",
        })
        if not sale_res.data:
            raise RepositoryError("Error al registrar la venta en base de datos")

        sale    = sale_res.data[0]
        sale_id = sale["id"]

        # ── 3. Insertar items (con cleanup si falla) ───────────────
        items_data = [
            {
                "sale_id":    sale_id,
                "product_id": item.product_id,
                "quantity":   item.quantity,
                "price":      item.unit_price,
            }
            for item in request.items
        ]
        try:
            self.sale_repo.create_sale_items(items_data)
        except Exception as e:
            self._cleanup_sale(sale_id)
            raise RepositoryError(f"Error al registrar ítems de venta: {e}") from e

        # ── 4. Registrar pago (con cleanup si falla) ───────────────
        try:
            self.sale_repo.create_payment({
                "sale_id": sale_id,
                "method":  request.payment_method,
                "amount":  (request.amount_received
                            if request.payment_method == "cash"
                            else request.total),
            })
        except Exception as e:
            self._cleanup_sale(sale_id)
            raise RepositoryError(f"Error al registrar pago: {e}") from e

        # ── 5. Actualizar inventario (no crítico — nunca revierte) ─
        if self.inventory_service:
            for item in request.items:
                try:
                    self.inventory_service.consume_stock(
                        product_id=item.product_id,
                        quantity=item.quantity,
                        sale_id=sale_id,
                        tenant_id=Session.tenant_id,
                    )
                except Exception:
                    pass  # kardex falla silenciosamente

        # ── 6. Emitir evento (fire & forget) ──────────────────────
        if self.event_service:
            try:
                self.event_service.emit(
                    Session.tenant_id,
                    "sale_created",
                    {
                        "sale_id":        sale_id,
                        "total":          request.total,
                        "items_count":    len(request.items),
                        "payment_method": request.payment_method,
                        "items": [
                            {
                                "product_id": i.product_id,
                                "name":       i.product_name,
                                "quantity":   i.quantity,
                                "price":      i.unit_price,
                            }
                            for i in request.items
                        ],
                    },
                )
            except Exception:
                pass

        change = (
            request.amount_received - request.total
            if request.payment_method == "cash" else 0
        )

        # Retornamos el mismo formato que SaleService.create_sale()
        # para mantener compatibilidad con PosView.
        return {
            "sale":   sale,
            "total":  request.total,
            "change": change,
            "items":  [
                {
                    "id":       i.product_id,
                    "name":     i.product_name,
                    "quantity": i.quantity,
                    "price":    i.unit_price,
                }
                for i in request.items
            ],
        }

    # ─── Cleanup ───────────────────────────────────────────────────
    def _cleanup_sale(self, sale_id: str) -> None:
        """
        Elimina una venta huérfana cuando el flujo falló tras crearla.
        Best-effort: si el borrado falla, loggeamos pero no relanzamos
        (la venta ya está en estado inconsistente de todas formas).
        """
        try:
            self.sale_repo.delete_sale(sale_id)
        except Exception as e:
            _log.warning("No se pudo limpiar venta huérfana %s: %s", sale_id, e)
