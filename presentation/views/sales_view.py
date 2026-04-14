# presentation/views/sales_view.py

import flet as ft
from presentation.theme import AppTheme


class SalesView:

    def __init__(self, page, colors, is_dark, sale_controller, app):
        self.page = page
        self.colors = colors
        self.is_dark = is_dark
        self.ctrl = sale_controller
        self.app = app
        self._sales: list[dict] = []
        self._rows_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

    def build(self):
        c = self.colors
        self._sales = self.ctrl.get_sales()
        stats = self.ctrl.get_today_stats()

        self._render_rows()

        refresh_btn = ft.IconButton(
            ft.icons.REFRESH_ROUNDED,
            icon_color=AppTheme.ACCENT,
            tooltip="Actualizar",
            on_click=self._refresh,
        )

        stat_row = ft.Row(
            [
                self._mini_stat("Ventas hoy", str(stats["count"]), AppTheme.gradient_primary()),
                self._mini_stat("Ingresos hoy", f"${stats['revenue']:,.2f}", AppTheme.gradient_success()),
                self._mini_stat("Total registradas", str(len(self._sales)), AppTheme.gradient_info()),
            ],
            spacing=12,
        )

        col_header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Fecha", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("ID Venta", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Total", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Método", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Estado", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                ],
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=c["surface"],
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
        )

        table = ft.Container(
            content=ft.Column(
                [col_header, ft.Container(height=1, bgcolor=c["border"]), self._rows_col],
                spacing=0, expand=True,
            ),
            bgcolor=c["card"],
            border_radius=12,
            border=ft.border.all(1, c["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        return ft.Container(
            content=ft.Column(
                [
                    AppTheme.page_header("Historial de Ventas", "Registro completo de transacciones", c, action=refresh_btn),
                    ft.Container(height=20),
                    stat_row,
                    ft.Container(height=20),
                    table,
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.padding.all(28),
            bgcolor=c["bg"],
        )

    def _render_rows(self, sales=None):
        c = self.colors
        data = sales if sales is not None else self._sales
        self._rows_col.controls.clear()

        if not data:
            self._rows_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.Icon(ft.icons.RECEIPT_LONG_ROUNDED, color=c["text_secondary"], size=48),
                         ft.Text("Sin ventas registradas", color=c["text_secondary"])],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                    ),
                    alignment=ft.alignment.center, height=160,
                )
            )
            self.page.update()
            return

        STATUS_COLORS = {"completed": AppTheme.SUCCESS, "pending": AppTheme.WARNING, "cancelled": AppTheme.ERROR}

        for sale in data:
            total = float(sale.get("total", 0))
            created = str(sale.get("created_at", ""))[:16].replace("T", " ")
            sale_id = str(sale.get("id", ""))
            status = sale.get("status", "completed")
            status_color = STATUS_COLORS.get(status, AppTheme.SUCCESS)

            # Extract payment method from nested payments if present
            payments = sale.get("payments", [])
            method = payments[0].get("method", "—") if payments else "—"
            method_labels = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia", "—": "—"}
            method_label = method_labels.get(method, method)

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(created, size=12, color=c["text"], expand=2),
                        ft.Text(sale_id[:8] + "...", size=11, color=c["text_secondary"],
                                font_family="monospace", expand=2),
                        ft.Text(f"${total:,.2f}", size=13, weight=ft.FontWeight.BOLD, color=c["text"], expand=1),
                        ft.Text(method_label, size=12, color=c["text_secondary"], expand=1),
                        ft.Container(
                            content=ft.Text(status, size=11, color="white"),
                            bgcolor=status_color,
                            border_radius=20,
                            padding=ft.padding.symmetric(horizontal=10, vertical=3),
                            expand=1,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
            )
            self._rows_col.controls.append(row)

        self.page.update()

    def _refresh(self, e):
        self._sales = self.ctrl.get_sales()
        self._render_rows()

    def _mini_stat(self, label, value, gradient):
        c = self.colors
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.icons.ANALYTICS_ROUNDED, color="white", size=20),
                        width=40, height=40, border_radius=10,
                        gradient=gradient, alignment=ft.alignment.center,
                    ),
                    ft.Column(
                        [
                            ft.Text(label, size=11, color=c["text_secondary"]),
                            ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=c["text"]),
                        ],
                        spacing=2, tight=True,
                    ),
                ],
                spacing=12,
            ),
            padding=ft.padding.all(16),
            bgcolor=c["card"],
            border_radius=12,
            border=ft.border.all(1, c["border"]),
            expand=True,
        )