# domain/services/ticket_service.py
#
# JUSTIFICACIÓN:
# TicketService vive en 'domain' porque la generación de un folio,
# el formateo del comprobante y la decisión de qué incluir en el PDF
# son REGLAS DE NEGOCIO, no detalles de infraestructura.
#
# DEPENDENCIAS EXTERNAS:
# - fpdf2 (pip install fpdf2): librería ligera para PDF, sin dependencia
#   de Java ni de un runtime externo. Se prefiere sobre reportlab para
#   proyectos pequeños/medianos porque su API es más simple.
#
# PATRÓN SEGUIDO:
# __init__ recibe ticket_repo por inyección para persistir el historial.
# La generación del PDF es un detalle técnico encapsulado en _build_pdf().
#
# INTEGRACIÓN EN pos_view.py (después de cobrar):
#   ticket = ticket_service.generate(sale_data)
#   ticket_service.export_pdf(ticket, path="tickets/folio_001.pdf")

import uuid
from datetime import datetime
from pathlib import Path
from fpdf import FPDF

try:
    _FPDF_AVAILABLE = True
except ImportError:
    _FPDF_AVAILABLE = False
    print("[TICKET WARNING] fpdf2 no instalado. Instala con: pip install fpdf2")

from session.session import Session


class TicketService:

    def __init__(self, ticket_repo=None, event_service=None):
        """
        Args:
            ticket_repo:   TicketRepository (opcional) — para persistir historial.
            event_service: EventService     (opcional) — para emitir ticket_generated.
        """
        self.ticket_repo   = ticket_repo
        self.event_service = event_service

    # ------------------------------------------------------------------ #
    # Generar ticket (en memoria)                                         #
    # ------------------------------------------------------------------ #
    def generate(self, sale: dict) -> dict:
        """
        Construye el dict del ticket a partir de los datos de una venta.

        Args:
            sale: {
                "items":          [{"name": str, "qty": int, "price": float}],
                "total":          float,
                "payment_method": str,   # cash | card | transfer
                "sale_id":        str,   # UUID de la venta (opcional)
            }

        Returns:
            {
                "folio":          str,   # NXP-<8 chars uuid>
                "items":          list,
                "subtotal":       float,
                "total":          float,
                "payment_method": str,
                "generated_at":   str,   # ISO datetime
                "tenant_id":      str,
            }

        DECISIÓN: el folio se genera aquí (dominio) porque es una regla
        de negocio definir su formato. El repo sólo lo persiste.
        """
        if not Session.tenant_id:
            raise Exception("[TicketService] No autenticado")

        items = sale.get("items", [])
        if not items:
            raise ValueError("[TicketService] La venta no tiene items")

        folio     = f"NXP-{str(uuid.uuid4())[:8].upper()}"
        subtotal  = sum(float(i["price"]) * int(i.get("qty", 1)) for i in items)
        total     = float(sale.get("total", subtotal))
        generated = datetime.now().isoformat(timespec="seconds")

        ticket = {
            "folio":          folio,
            "items":          items,
            "subtotal":       round(subtotal, 2),
            "total":          round(total, 2),
            "payment_method": sale.get("payment_method", "cash"),
            "generated_at":   generated,
            "tenant_id":      Session.tenant_id,
            "sale_id":        sale.get("sale_id"),
        }

        # Persistir historial si el repo está disponible
        if self.ticket_repo:
            try:
                self.ticket_repo.save(ticket)
            except Exception as e:
                print(f"[TICKET WARNING] No se pudo guardar historial: {e}")

        # Emitir evento si event_service está inyectado
        if self.event_service:
            self.event_service.emit(
                Session.tenant_id,
                "ticket_generated",
                {"folio": folio, "total": total}
            )

        print(f"[TICKET] Generado → {folio} | Total: ${total:.2f}")
        return ticket

    # ------------------------------------------------------------------ #
    # Exportar PDF                                                        #
    # ------------------------------------------------------------------ #
    def export_pdf(self, ticket: dict, output_path: str = None) -> str: #type: ignore
        """
        Genera un PDF del ticket y lo guarda en disco.

        Args:
            ticket:      Dict devuelto por generate().
            output_path: Ruta completa del archivo. Si no se provee,
                         se guarda en ./tickets/<folio>.pdf.

        Returns:
            Ruta absoluta del PDF generado.

        DECISIÓN: la generación del PDF está aquí (dominio) porque el
        formato del comprobante es una regla de negocio. Si en el futuro
        necesitamos un adaptador para otro generador (HTML→PDF, etc.),
        podemos extraer _build_pdf() a una interfaz de infraestructura.
        """
        if not _FPDF_AVAILABLE:
            raise RuntimeError(
                "fpdf2 no está instalado. Ejecuta: pip install fpdf2"
            )

        folio = ticket.get("folio", "SIN-FOLIO")

        if not output_path:
            tickets_dir = Path("tickets")
            tickets_dir.mkdir(exist_ok=True)
            output_path = str(tickets_dir / f"{folio}.pdf")

        self._build_pdf(ticket, output_path)
        print(f"[TICKET PDF] Guardado en: {output_path}")
        return output_path

    # ------------------------------------------------------------------ #
    # Historial de tickets                                                #
    # ------------------------------------------------------------------ #
    def get_history(self) -> list:
        """
        Devuelve el historial de tickets del tenant activo.
        Requiere que ticket_repo esté inyectado.
        """
        if not self.ticket_repo:
            raise RuntimeError("[TicketService] ticket_repo no fue inyectado")

        if not Session.tenant_id:
            raise Exception("[TicketService] No autenticado")

        res = self.ticket_repo.get_by_tenant(Session.tenant_id)
        return res.data or []

    # ------------------------------------------------------------------ #
    # Construcción del PDF (detalle técnico privado)                     #
    # ------------------------------------------------------------------ #
    def _build_pdf(self, ticket: dict, path: str):
        """
        Construye el PDF físico usando fpdf2.
        Formato tipo ticket de caja: 80mm de ancho (estándar impresoras POS).
        """
        pdf = FPDF(unit="mm", format=(80, 200))
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=5)

        # --- Encabezado ---
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, "NexaPOS", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", size=8)
        pdf.cell(0, 5, f"Folio: {ticket['folio']}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Fecha: {ticket['generated_at']}", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)
        pdf.set_draw_color(180, 180, 180)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(3)

        # --- Items ---
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(40, 5, "Producto", new_x="NEXT")
        pdf.cell(10, 5, "Cant", align="C", new_x="NEXT")
        pdf.cell(20, 5, "Precio", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", size=8)
        for item in ticket.get("items", []):
            name  = str(item.get("name", ""))[:22]
            qty   = int(item.get("qty", 1))
            price = float(item.get("price", 0))
            pdf.cell(40, 5, name, new_x="NEXT")
            pdf.cell(10, 5, str(qty), align="C", new_x="NEXT")
            pdf.cell(20, 5, f"${price:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)
        pdf.line(5, pdf.get_y(), 75, pdf.get_y())
        pdf.ln(3)

        # --- Totales ---
        pdf.set_font("Helvetica", size=9)
        pdf.cell(50, 5, "Subtotal:", new_x="NEXT")
        pdf.cell(20, 5, f"${ticket['subtotal']:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(50, 6, "TOTAL:", new_x="NEXT")
        pdf.cell(20, 6, f"${ticket['total']:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", size=8)
        method_label = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia"}
        method = method_label.get(ticket.get("payment_method", "cash"), ticket.get("payment_method", ""))
        pdf.cell(0, 5, f"Pago: {method}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(0, 4, "Gracias por su compra", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.output(path)