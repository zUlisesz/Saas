# domain/models/recharge.py
#
# Entidad de dominio: Recarga Electrónica.
#
# DECISIÓN: dataclass puro sin lógica de negocio.
# Las reglas de validación viven en domain/specifications/recharge_specs.py.
# La orquestación vive en domain/services/recharge_service.py.

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Recharge:
    """Entidad que representa una recarga electrónica registrada."""
    id:              str
    tenant_id:       str
    phone:           str
    operator:        str
    amount:          float
    status:          str            # 'success' | 'failed' | 'pending'
    external_tx_id:  Optional[str]  = None
    created_at:      Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Recharge":
        """Construye la entidad desde un dict de Supabase."""
        created_raw = data.get("created_at")
        if isinstance(created_raw, str):
            try:
                created_at = datetime.fromisoformat(created_raw)
            except ValueError:
                created_at = None
        else:
            created_at = created_raw

        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            phone=data["phone"],
            operator=data["operator"],
            amount=float(data.get("amount", 0)),
            status=data.get("status", "pending"),
            external_tx_id=data.get("external_tx_id"),
            created_at=created_at,
        )

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "tenant_id":      self.tenant_id,
            "phone":          self.phone,
            "operator":       self.operator,
            "amount":         self.amount,
            "status":         self.status,
            "external_tx_id": self.external_tx_id,
            "created_at":     self.created_at.isoformat() if self.created_at else None,
        }
