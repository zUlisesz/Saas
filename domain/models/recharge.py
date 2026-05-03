# domain/models/recharge.py
#
# Entidad de dominio: Recarga Electrónica.
#
# DECISIONES:
#   frozen=True: una entidad recuperada de BD es inmutable. Si el estado
#   cambia (pending → success), el repo crea un nuevo objeto. Patrón
#   consistente con el resto de modelos del proyecto.
#
#   UUID como str: Supabase los retorna como str. Convertir a uuid.UUID
#   en el repo no agrega valor y complica el mapping.
#
#   created_at / completed_at como str: Supabase retorna ISO strings.
#   La conversión a datetime es responsabilidad de la capa de presentación
#   si la necesita para formatear — no del dominio.
#
#   is_terminal / is_successful son consultas de estado puro, sin
#   dependencias externas. Aceptable en la entidad.

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Recharge:
    """Espejo 1:1 de la tabla `recharges` en BD. Solo estructura + tipado."""

    id:                str
    tenant_id:         str
    phone:             str
    operator:          str
    amount:            float
    currency:          str
    status:            str               # pending | processing | success | failed | timeout
    created_at:        str
    created_by:        str
    external_tx_id:    Optional[str]   = None
    external_response: Optional[dict]  = None
    error_code:        Optional[str]   = None
    error_message:     Optional[str]   = None
    completed_at:      Optional[str]   = None

    # ── Propiedades de estado (solo lectura, sin lógica de negocio) ───────

    @property
    def is_terminal(self) -> bool:
        """True si el status ya no puede cambiar (success | failed | timeout)."""
        return self.status in ('success', 'failed', 'timeout')

    @property
    def is_successful(self) -> bool:
        return self.status == 'success'
