# presentation/views/recharge_panel.py
#
# Fase 6: Panel de Recargas Electrónicas — componente extraído de pos_view.py.
#
# RAZÓN DE EXTRACCIÓN (H7):
#   pos_view.py superó 700 líneas combinando venta, barcodes y recargas.
#   Este componente agrupa toda la lógica y UI de recargas en un solo lugar,
#   con su propio estado interno (_recharge_history_col).
#
# USO EN pos_view.py:
#   panel = RechargePanel(page=page, colors=colors, recharge_ctrl=ctrl, app=app)
#   tab_content = panel.build()
#
# PRINCIPIO: RechargePanel recibe el controller por inyección.
# Nunca instancia servicios ni repositorios directamente.

import threading
import flet as ft

from presentation.theme import AppTheme


class RechargePanel:

    def __init__(self, page, colors, recharge_ctrl, app):
        self.page          = page
        self.colors        = colors
        self.recharge_ctrl = recharge_ctrl
        self.app           = app

        self._recharge_history_col = ft.Column(spacing=4)

    # ─────────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────────

    def build(self) -> ft.Control:
        """Construye y retorna el contenido completo de la tab de recargas."""
        c         = self.colors
        operators = self.recharge_ctrl.get_operators() if self.recharge_ctrl else []

        selected_operator = ft.Ref[ft.Dropdown]()
        phone_field       = AppTheme.make_text_field(
            "Número de teléfono (10 dígitos)", colors=c
        )
        amounts_row      = ft.Row(wrap=True, spacing=8, run_spacing=8)
        selected_amount  = {"value": None}
        amount_label     = ft.Text("", size=14, color=c["text_secondary"])
        commission_label = ft.Text("", size=12, color=AppTheme.SUCCESS,
                                   weight=ft.FontWeight.W_600)

        def on_operator_change(e):
            op_id   = selected_operator.current.value
            amounts = self.recharge_ctrl.get_amounts_for(op_id) if op_id else []
            amounts_row.controls.clear()
            selected_amount["value"] = None
            amount_label.value       = "Selecciona un monto"
            commission_label.value   = ""

            for amt in amounts:
                def make_chip(a=amt):
                    return ft.Container(
                        content=ft.Text(f"${a}", size=13, weight=ft.FontWeight.W_600,
                                        color="white"),
                        gradient=AppTheme.gradient_primary(),
                        border_radius=20,
                        padding=ft.padding.symmetric(horizontal=14, vertical=7),
                        ink=True,
                        on_click=lambda e, amount=a: select_amount(amount),
                    )
                amounts_row.controls.append(make_chip())

            self.page.update()

        def select_amount(amount: int):
            selected_amount["value"] = amount  # type: ignore
            amount_label.value = f"Monto seleccionado: ${amount}"
            op_id = selected_operator.current.value if selected_operator.current else None
            if op_id and self.recharge_ctrl:
                comm = self.recharge_ctrl.get_commission_estimate(op_id, float(amount))
                commission_label.value = f"Ganancia estimada: Bs {comm:.2f}"
            else:
                commission_label.value = ""
            amount_label.update()
            commission_label.update()

        def on_recharge(e):
            op_id  = selected_operator.current.value if selected_operator.current else None
            amount = selected_amount["value"]
            phone  = phone_field.value or ""

            if not op_id:
                self.app.show_snackbar("Selecciona una operadora", error=True)
                return
            if not amount:
                self.app.show_snackbar("Selecciona un monto", error=True)
                return
            if not phone:
                self.app.show_snackbar("Ingresa el número de teléfono", error=True)
                return
            if not self.recharge_ctrl.is_valid_phone(phone):
                self.app.show_snackbar(
                    "Número inválido: debe tener 8-12 dígitos", error=True
                )
                return

            operator_name = next(
                (op["name"] for op in operators if op["id"] == op_id), op_id
            )
            commission = self.recharge_ctrl.get_commission_estimate(op_id, float(amount))

            def reset_form():
                phone_field.value        = ""
                selected_amount["value"] = None
                amount_label.value       = "Selecciona un monto"
                commission_label.value   = ""
                self.page.update()

            self._show_recharge_confirmation(
                phone=phone,
                operator=op_id,
                operator_name=operator_name,
                amount=float(amount),
                commission=commission,
                on_success=reset_form,
            )

        op_options = [
            ft.dropdown.Option(key=op["id"], text=op["name"])
            for op in operators
        ]

        operator_dd = ft.Dropdown(
            ref=selected_operator,
            options=op_options,
            label="Operadora",
            border_radius=12,
            border_color=c["border"],
            focused_border_color=AppTheme.ACCENT,
            label_style=ft.TextStyle(color=c["text_secondary"], size=13),
            text_style=ft.TextStyle(color=c["text"]),
            bgcolor=c["input_fill"],
            on_change=on_operator_change,
        )

        recharge_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.PHONE_ANDROID_ROUNDED, color="white", size=18),
                ft.Text("Procesar Recarga", color="white", weight=ft.FontWeight.W_600),
            ], spacing=8, tight=True),
            gradient=AppTheme.gradient_primary(),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            on_click=on_recharge,
            ink=True,
        )

        # Carga inicial del historial en background — evita conflictos de
        # conexión con operaciones Supabase en curso en el hilo de UI.
        if self.recharge_ctrl:
            threading.Thread(
                target=self._async_load_recharge_history, daemon=True
            ).start()

        return ft.Column(
            [
                ft.Text("Recarga Electrónica", size=16,
                        weight=ft.FontWeight.BOLD, color=c["text"]),
                ft.Container(height=12),
                operator_dd,
                ft.Container(height=12),
                ft.Text("Montos disponibles:", size=12, color=c["text_secondary"]),
                ft.Container(height=6),
                amounts_row,
                ft.Container(height=4),
                amount_label,
                commission_label,
                ft.Container(height=12),
                phone_field,
                ft.Container(height=16),
                recharge_btn,
                ft.Container(height=8),
                ft.Divider(height=1),
                ft.Container(height=8),
                ft.Text("Últimas recargas", size=12, weight=ft.FontWeight.W_600,
                        color=c["text_secondary"]),
                ft.Container(height=4),
                self._recharge_history_col,
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    # ─────────────────────────────────────────────────────────────
    # Diálogo de confirmación
    # ─────────────────────────────────────────────────────────────

    def _show_recharge_confirmation(
        self,
        phone: str,
        operator: str,
        amount: float,
        operator_name: str,
        commission: float,
        on_success=None,
    ):
        c = self.colors

        def on_confirm(e):
            dialog.open = False
            self.page.update()
            result = self.recharge_ctrl.process_recharge(phone, operator, amount)
            if result:
                if on_success:
                    on_success()
                self._refresh_recharge_history()

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.PHONE_ANDROID_ROUNDED, color=AppTheme.ACCENT),
                ft.Text("Confirmar Recarga", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Operadora:", size=13, color=c["text_secondary"]),
                        ft.Text(operator_name, size=13, weight=ft.FontWeight.W_600,
                                color=c["text"]),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text("Número:", size=13, color=c["text_secondary"]),
                        ft.Text(phone, size=13, weight=ft.FontWeight.W_600,
                                color=c["text"]),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text("Monto:", size=14, weight=ft.FontWeight.BOLD,
                                color=c["text"]),
                        ft.Text(f"Bs {amount:.2f}", size=14,
                                weight=ft.FontWeight.BOLD, color=AppTheme.ACCENT),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=8),
                    ft.Row([
                        ft.Text("Comisión estimada:", size=12,
                                color=c["text_secondary"]),
                        ft.Text(f"Bs {commission:.2f}", size=12,
                                color=AppTheme.SUCCESS, weight=ft.FontWeight.W_600),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=10, tight=True),
                width=320,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Confirmar", color="white",
                                    weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_confirm,
                    ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────────
    # Historial
    # ─────────────────────────────────────────────────────────────

    def _async_load_recharge_history(self):
        """Carga inicial del historial en background thread."""
        self._fill_recharge_history()
        try:
            self._recharge_history_col.update()
        except Exception:
            pass

    def _fill_recharge_history(self):
        """Reconstruye controles del historial. No llama page.update()."""
        c = self.colors
        self._recharge_history_col.controls.clear()

        history = self.recharge_ctrl.get_history(limit=10)

        if not history:
            self._recharge_history_col.controls.append(
                ft.Text("Sin recargas aún", size=12, color=c["text_secondary"])
            )
            return

        status_colors = {
            "success": AppTheme.SUCCESS,
            "failed":  AppTheme.ERROR,
            "timeout": AppTheme.WARNING,
        }

        for item in history:
            if isinstance(item, dict):
                phone    = item.get("phone", "—")
                operator = item.get("operator", "")
                amount   = item.get("amount", 0)
                status   = item.get("status", "")
                label    = status
            else:
                phone    = item.phone
                operator = item.operator
                amount   = item.amount
                status   = item.status
                label    = item.status_label

            self._recharge_history_col.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(phone, size=12, expand=True),
                        ft.Text(str(operator).capitalize(), size=11,
                                color=c["text_secondary"]),
                        ft.Text(f"Bs {float(amount):.0f}", size=12,
                                weight=ft.FontWeight.W_600, color=c["text"]),
                        ft.Text(label, size=11,
                                color=status_colors.get(status, c["text_secondary"])),
                    ], spacing=8),
                    padding=ft.padding.symmetric(vertical=4),
                )
            )

    def _refresh_recharge_history(self):
        """Refresca el historial tras una recarga. Llama page.update()."""
        self._fill_recharge_history()
        try:
            self._recharge_history_col.update()
        except Exception:
            pass
