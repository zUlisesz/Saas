# domain/schemas/recharge_schemas.py
#
# DTOs para operaciones de recargas electrónicas.
#
# DECISIÓN: tenant_id en RechargeRequest se inyecta desde Session en el
# controlador, nunca viene del formulario del usuario — evita que un cliente
# envíe recargas a otro tenant.

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RechargeRequest:
    """DTO de entrada para solicitar una recarga."""
    phone:     str
    operator:  str
    amount:    float
    tenant_id: str  # inyectado desde Session, no del formulario


@dataclass
class RechargeResponse:
    """DTO de salida tras procesar una recarga."""
    recharge_id: str
    status:      str            # 'success' | 'failed' | 'pending'
    amount:      float
    phone:       str
    tx_id:       Optional[str] = None
    error:       Optional[str] = None


@dataclass
class RechargeHistoryItem:
    """DTO de historial — combina datos de la recarga y el cajero."""
    id:          str
    phone:       str
    operator:    str
    amount:      float
    status:      str
    created_at:  Optional[datetime]
    cajero_name: Optional[str] = None
