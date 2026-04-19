# domain/services/product_service.py
#
# Fase 4 — Código de Barras:
#   • __init__ acepta barcode_service opcional (fallback al algoritmo naïve)
#   • assign_barcode()        → asigna + valida + registra historial
#   • get_pending_products()  → productos con PENDING-*
#   • assign_barcodes_bulk()  → reemplaza todos los PENDING del tenant
#   • get_barcode_stats()     → cobertura de barcodes
#   • create_product/update_product validan formato de barcode si se proveyó

from session.session import Session
from domain.schemas.product_schemas import CreateProductRequest, UpdateProductRequest
from domain.exceptions import (
    AuthenticationError, RepositoryError, ValidationError, DuplicateBarcodeError,
)


class ProductService:

    def __init__(self, repo, barcode_service=None):
        self.repo            = repo
        self.barcode_service = barcode_service  # opcional — fallback naïve si None

    def _require_auth(self) -> str:
        if not Session.tenant_id:
            raise AuthenticationError("No hay sesión activa")
        return Session.tenant_id

    # ─── Listado y búsqueda ───────────────────────────────────────

    def list_products(self):
        tenant_id = self._require_auth()
        res = self.repo.get_all(tenant_id)
        return res.data or []

    def search_products(self, query):
        tenant_id = self._require_auth()
        res = self.repo.search(tenant_id, query)
        return res.data or []

    # ─── Código de barras ─────────────────────────────────────────

    def find_by_barcode(self, barcode: str) -> dict | None:
        tenant_id = self._require_auth()
        if not barcode or not barcode.strip():
            return None
        res  = self.repo.get_by_barcode(tenant_id, barcode.strip())
        data = res.data or []
        return data[0] if data else None

    def generate_barcode_for(self, product_id: str, barcode_type: str = "ean13") -> str:
        if self.barcode_service:
            return self.barcode_service.generate_for_type(product_id, barcode_type)
        # Fallback naïve (sin checksum — solo si BarcodeService no está disponible)
        numeric = "".join(c for c in product_id.replace("-", "") if c.isdigit())
        while len(numeric) < 12:
            numeric += "0"
        return numeric[:12]

    def assign_barcode(
        self, product_id: str, barcode: str, barcode_type: str = "ean13"
    ) -> dict:
        """Asigna un barcode a un producto, valida formato y registra historial."""
        self._require_auth()

        if self.barcode_service:
            ok, err = self.barcode_service.validate(barcode, barcode_type)
            if not ok:
                raise ValidationError("barcode", err)

        res = self.repo.update(product_id, {"barcode": barcode, "barcode_type": barcode_type})
        if not res.data:
            raise RepositoryError("Error al actualizar el barcode")

        updated = res.data[0]
        self._log_barcode_change(product_id, barcode, barcode_type)
        return updated

    def get_pending_products(self) -> list[dict]:
        tenant_id = self._require_auth()
        res = self.repo.get_pending_products(tenant_id)
        return res.data or []

    def assign_barcodes_bulk(self, barcode_type: str = "ean13") -> int:
        """Genera y asigna EAN-13 a todos los productos PENDING del tenant."""
        pending = self.get_pending_products()
        count   = 0
        for p in pending:
            try:
                new_barcode = self.generate_barcode_for(p["id"], barcode_type)
                self.assign_barcode(p["id"], new_barcode, barcode_type)
                count += 1
            except Exception:
                continue
        return count

    def get_barcode_stats(self) -> dict:
        tenant_id = self._require_auth()
        return self.repo.get_barcode_stats(tenant_id)

    def _log_barcode_change(self, product_id: str, barcode: str, barcode_type: str):
        try:
            self.repo.add_barcode_history({
                "product_id":   product_id,
                "barcode":      barcode,
                "barcode_type": barcode_type,
                "tenant_id":    Session.tenant_id,
            })
        except Exception:
            pass

    # ─── CRUD ─────────────────────────────────────────────────────

    def create_product(self, data: dict) -> dict:
        tenant_id = self._require_auth()

        try:
            price = float(data.get("price", 0))
            cost  = float(data.get("cost", 0))
        except (ValueError, TypeError):
            raise ValidationError("price", "Precio o costo con formato inválido")

        request = CreateProductRequest(
            name=data.get("name", ""),
            price=price,
            cost=cost,
            barcode=data.get("barcode"),
            barcode_type=data.get("barcode_type"),
            category_id=data.get("category_id"),
            is_active=data.get("is_active", True),
        )
        request.validate()

        barcode = request.barcode
        if barcode and self.barcode_service and not self.barcode_service.is_pending(barcode):
            ok, err = self.barcode_service.validate(barcode, request.barcode_type or "ean13")
            if not ok:
                raise ValidationError("barcode", err)

        res = self.repo.create(request.to_db_dict(tenant_id))
        if not res.data:
            raise RepositoryError("Error al crear el producto en base de datos")
        return res.data[0]

    def update_product(self, product_id: str, data: dict) -> dict:
        self._require_auth()

        try:
            price = float(data["price"]) if "price" in data else None
            cost  = float(data["cost"])  if "cost"  in data else None
        except (ValueError, TypeError):
            raise ValidationError("price", "Precio o costo con formato inválido")

        request = UpdateProductRequest(
            name=data.get("name"),
            price=price,
            cost=cost,
            barcode=data.get("barcode"),
            barcode_type=data.get("barcode_type"),
            category_id=data.get("category_id"),
            is_active=data.get("is_active"),
        )
        request.validate()

        barcode = request.barcode
        if barcode and self.barcode_service and not self.barcode_service.is_pending(barcode):
            ok, err = self.barcode_service.validate(barcode, request.barcode_type or "ean13")
            if not ok:
                raise ValidationError("barcode", err)

        res = self.repo.update(product_id, request.to_db_dict())
        if not res.data:
            raise RepositoryError("Error al actualizar el producto")
        return res.data[0]

    def delete_product(self, product_id: str) -> None:
        self._require_auth()
        self.repo.soft_delete(product_id)

    def get_count(self) -> int:
        tenant_id = self._require_auth()
        res = self.repo.count(tenant_id)
        return res.count or 0
