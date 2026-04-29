# presentation/views/inventory_view.py
#
# FASE 5 — REESCRITURA COMPLETA (22 Abril 2026)
#
# CAMBIOS vs. versión anterior:
#
#   1. _render_rows() ADAPTADO a la estructura aplanada de la RPC.
#      ANTES: item["products"]["name"], item["stock_actual"]
#      AHORA: item["product_name"], item["stock_actual"] (campo raíz)
#      MOTIVO: RPC get_inventory_with_alerts devuelve datos desnormalizados.
#
#   2. stock_status COLOR UNIFICADO: 4 estados (ok/low/out_of_stock/overstock)
#      usando el campo calculado en BD. Antes se calculaba en Python con
#      stock_act <= stock_min, lo que divergía de la lógica del servicio.
#
#   3. NUEVO: TabBar con 2 tabs — "Inventario" y "Alertas activas".
#      Tab Alertas muestra las alertas con botones Reconocer/Resolver/Ignorar.
#      DECISIÓN: tabs en vez de dialogs porque las alertas son datos de nivel
#      igual al inventario — no un popup secundario.
#
#   4. NUEVO: _show_threshold_dialog() — modal para editar min/max/reorder.
#      Reemplaza el ajuste básico que solo tenía stock+minimo. Ahora incluye
#      stock_maximo, reorder_point, reorder_quantity, checkboxes de alertas.
#
#   5. NUEVO: _show_kardex_dialog() MEJORADO — muestra tanto kardex
#      (fuente contable) como movements_log (fuente técnica) en tabs.
#
#   6. Banner de alertas usa datos de get_alert_summary() del controller
#      en lugar de get_low_stock_alerts(). Tiene botón "Ver todas".
#
# LAYOUT ACTUALIZADO:
#   ┌────────────────────────────────────────────────────────┐
#   │ 📦 Inventario         [Inventario][Alertas N] [🔄]    │
#   ├────────────────────────────────────────────────────────┤
#   │  Tab: Inventario                                       │
#   │  [!] Banner (si hay alertas)                           │
#   │  Producto | Barcode | Stock | Estado | Máx | Acciones  │
#   │  ...                                                   │
#   ├────────────────────────────────────────────────────────┤
#   │  Tab: Alertas                                          │
#   │  Tipo | Producto | Stock | Estado | Acciones           │
#   │  ...                                                   │
#   └────────────────────────────────────────────────────────┘

from __future__ import annotations
import flet as ft
from presentation.theme import AppTheme


# Mapa de estado → (texto, color)
_STATUS_MAP = {
    "ok":          ("OK",       AppTheme.SUCCESS),
    "low":         ("Bajo",     AppTheme.WARNING),
    "out_of_stock":("Agotado",  AppTheme.ERROR),
    "overstock":   ("Exceso",   AppTheme.BLUE),
}
_ALERT_TYPE_MAP = {
    "low_stock":   ("Stock bajo",  AppTheme.WARNING),
    "out_of_stock":("Agotado",     AppTheme.ERROR),
    "overstock":   ("Exceso",      AppTheme.BLUE),
    "expiring":    ("Por vencer",  AppTheme.WARNING),
}


class InventoryView:

    def __init__(self, page, colors, is_dark, inventory_controller, app):
        self.page    = page
        self.colors  = colors
        self.is_dark = is_dark
        self.ctrl    = inventory_controller
        self.app     = app

        # Estado interno
        self._inventory: list[dict] = []
        self._alerts:    list[dict] = []
        self._tab_idx:   int        = 0

        # Columnas de scroll para cada tab
        self._inv_col   = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._alert_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

        # Ref al badge de alertas para actualizar sin rebuild completo
        self._alert_badge_ref = ft.Ref[ft.Text]()

    # ================================================================== #
    # Build                                                               #
    # ================================================================== #

    def build(self):
        c = self.colors
        self._load_data()

        summary = self.ctrl.get_alert_summary()

        # Header row con refresh
        refresh_btn = ft.IconButton(
            ft.icons.REFRESH_ROUNDED,
            icon_color=AppTheme.ACCENT,
            tooltip="Actualizar",
            on_click=self._refresh,
        )

        # TabBar
        alert_count = summary.get("total_new", 0)
        tabs = ft.Tabs(
            selected_index=self._tab_idx,
            animation_duration=200,
            on_change=self._on_tab_change,
            expand=True,
            tabs=[
                ft.Tab(
                    text=f"Inventario ({len(self._inventory)})",
                    icon=ft.icons.INVENTORY_2_ROUNDED,
                    content=self._build_inventory_tab(summary),
                ),
                ft.Tab(
                    text=f"Alertas ({alert_count})" if alert_count else "Alertas",
                    icon=ft.icons.NOTIFICATIONS_ROUNDED,
                    content=self._build_alerts_tab(),
                ),
            ],
        )

        return ft.Container(
            content=ft.Column([
                AppTheme.page_header(
                    "Inventario",
                    f"{len(self._inventory)} productos · {alert_count} alerta(s) activa(s)",
                    c,
                    action=refresh_btn,
                ),
                ft.Container(height=12),
                tabs,
            ], expand=True),
            expand=True,
            padding=ft.padding.all(28),
            bgcolor=c["bg"],
        )

    # ================================================================== #
    # Tab: Inventario                                                     #
    # ================================================================== #

    def _build_inventory_tab(self, summary: dict) -> ft.Container:
        c = self.colors
        self._render_inventory_rows()

        # Banner de stock bajo
        banner = ft.Container(height=0)
        if summary.get("total_new", 0) > 0:
            banner = self._build_alert_banner(summary)

        col_header = ft.Container(
            content=ft.Row([
                ft.Text("Producto",  size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=3),
                ft.Text("Barcode",   size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=2),
                ft.Text("Stock",     size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=1),
                ft.Text("Mín / Máx", size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=2),
                ft.Text("Estado",    size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=1),
                ft.Text("Acciones",  size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, width=130),
            ]),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=c["surface"],
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
        )

        table = ft.Container(
            content=ft.Column(
                [col_header, ft.Container(height=1, bgcolor=c["border"]), self._inv_col],
                spacing=0, expand=True,
            ),
            bgcolor=c["card"],
            border_radius=10,
            border=ft.border.all(1, c["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        return ft.Container(
            content=ft.Column([
                banner,
                ft.Container(height=8) if summary.get("total_new", 0) > 0 else ft.Container(height=0),
                table,
            ], expand=True),
            expand=True,
            padding=ft.padding.only(top=12),
        )

    def _render_inventory_rows(self, data: list = None): #type: ignore
        c    = self.colors
        rows = data if data is not None else self._inventory
        self._inv_col.controls.clear()

        if not rows:
            self._inv_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.INVENTORY_ROUNDED,
                                color=c["text_secondary"], size=48),
                        ft.Text("Sin inventario registrado",
                                color=c["text_secondary"]),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.alignment.center, height=160,
                )
            )
            return

        for item in rows:
            # ── Campos desde RPC aplanada ──────────────────────────────
            product_id   = item.get("product_id", "")
            name         = item.get("product_name", "—")
            barcode      = item.get("barcode", "—")
            category     = item.get("category_name", "—")
            stock_act    = item.get("stock_actual", 0)
            stock_min    = item.get("stock_minimo", 5)
            stock_max    = item.get("stock_maximo", 100)
            status_key   = item.get("stock_status", "ok")
            active_alerts= item.get("active_alerts", 0)

            status_text, status_color = _STATUS_MAP.get(status_key, ("—", c["text"]))

            is_problem = status_key in ("low", "out_of_stock")

            row = ft.Container(
                content=ft.Row([
                    # Producto
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.icons.INVENTORY_2_ROUNDED,
                                            color=AppTheme.ACCENT, size=15),
                            width=28, height=28, border_radius=6,
                            bgcolor=f"{AppTheme.ACCENT}18",
                            alignment=ft.alignment.center,
                        ),
                        ft.Column([
                            ft.Text(name, size=13, color=c["text"],
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(category, size=10, color=c["text_secondary"]),
                        ], spacing=1, tight=True, expand=True),
                    ], expand=3, spacing=8),

                    # Barcode
                    ft.Text(barcode, size=11, color=c["text_secondary"],
                            font_family="monospace", expand=2,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),

                    # Stock actual
                    ft.Row([
                        ft.Text(
                            str(stock_act),
                            size=15, weight=ft.FontWeight.BOLD,
                            color=AppTheme.ERROR if is_problem else c["text"],
                        ),
                        # Badge de alerta activa
                        ft.Container(
                            content=ft.Text(str(active_alerts), size=9, color="white"),
                            bgcolor=AppTheme.ERROR,
                            border_radius=20,
                            padding=ft.padding.symmetric(horizontal=5, vertical=1),
                            visible=active_alerts > 0,
                        ),
                    ], expand=1, spacing=4),

                    # Mín / Máx
                    ft.Text(f"{stock_min} / {stock_max}", size=12,
                            color=c["text_secondary"], expand=2),

                    # Badge de estado
                    ft.Container(
                        content=ft.Text(status_text, size=11, color="white"),
                        bgcolor=status_color,
                        border_radius=20,
                        padding=ft.padding.symmetric(horizontal=10, vertical=3),
                        expand=1,
                    ),

                    # Acciones
                    ft.Row([
                        ft.IconButton(
                            ft.icons.EDIT_NOTE_ROUNDED,
                            icon_size=16, icon_color=AppTheme.ACCENT,
                            tooltip="Ajustar stock",
                            on_click=lambda e, i=item:
                                self._show_adjust_dialog(i),
                        ),
                        ft.IconButton(
                            ft.icons.TUNE_ROUNDED,
                            icon_size=16, icon_color=AppTheme.BLUE,
                            tooltip="Configurar umbrales",
                            on_click=lambda e, i=item:
                                self._show_threshold_dialog(i),
                        ),
                        ft.IconButton(
                            ft.icons.HISTORY_ROUNDED,
                            icon_size=16, icon_color=c["text_secondary"],
                            tooltip="Ver historial",
                            on_click=lambda e, pid=product_id, n=name:
                                self._show_kardex_dialog(pid, n),
                        ),
                    ], spacing=0, width=130),

                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                bgcolor=f"{AppTheme.WARNING}08" if is_problem else "transparent",
                border=ft.border.only(
                    bottom=ft.border.BorderSide(1, c["divider"]),
                    left=ft.border.BorderSide(
                        3, AppTheme.ERROR if status_key == "out_of_stock"
                        else AppTheme.WARNING if status_key == "low"
                        else "transparent"
                    ),
                ),
            )
            self._inv_col.controls.append(row)

    # ================================================================== #
    # Tab: Alertas                                                        #
    # ================================================================== #

    def _build_alerts_tab(self) -> ft.Container:
        c = self.colors
        self._render_alert_rows()

        col_header = ft.Container(
            content=ft.Row([
                ft.Text("Tipo",     size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=1),
                ft.Text("Producto", size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=3),
                ft.Text("Stock",    size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=1),
                ft.Text("Mínimo",   size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, expand=1),
                ft.Text("Acciones", size=11, color=c["text_secondary"],
                        weight=ft.FontWeight.W_600, width=180),
            ]),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=c["surface"],
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
        )

        table = ft.Container(
            content=ft.Column(
                [col_header, ft.Container(height=1, bgcolor=c["border"]), self._alert_col],
                spacing=0, expand=True,
            ),
            bgcolor=c["card"],
            border_radius=10,
            border=ft.border.all(1, c["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        return ft.Container(
            content=ft.Column([table], expand=True),
            expand=True,
            padding=ft.padding.only(top=12),
        )

    def _render_alert_rows(self, data: list = None): #type: ignore
        c     = self.colors
        rows  = data if data is not None else self._alerts
        self._alert_col.controls.clear()

        active = [a for a in rows if a.get("status") == "new"]

        if not active:
            self._alert_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                color=AppTheme.SUCCESS, size=48),
                        ft.Text("Sin alertas activas", color=c["text_secondary"]),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.alignment.center, height=160,
                )
            )
            return

        for alert in active:
            alert_id    = alert.get("id", "")
            alert_type  = alert.get("alert_type", "low_stock")
            product_name= alert.get("product_name", "—")
            stock_act   = alert.get("stock_actual", 0)
            stock_min   = alert.get("stock_minimo", 0)

            type_text, type_color = _ALERT_TYPE_MAP.get(alert_type, ("—", c["text"]))

            row = ft.Container(
                content=ft.Row([
                    # Tipo badge
                    ft.Container(
                        content=ft.Text(type_text, size=11, color="white"),
                        bgcolor=type_color,
                        border_radius=20,
                        padding=ft.padding.symmetric(horizontal=10, vertical=3),
                        expand=1,
                    ),

                    # Producto
                    ft.Text(product_name, size=13, color=c["text"], expand=3,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),

                    # Stock
                    ft.Text(str(stock_act), size=13,
                            color=AppTheme.ERROR if stock_act == 0 else AppTheme.WARNING,
                            weight=ft.FontWeight.BOLD, expand=1),

                    # Mínimo
                    ft.Text(str(stock_min), size=13,
                            color=c["text_secondary"], expand=1),

                    # Acciones
                    ft.Row([
                        ft.TextButton(
                            "Reconocer",
                            style=ft.ButtonStyle(color=AppTheme.ACCENT),
                            on_click=lambda e, aid=alert_id:
                                self._on_acknowledge(aid),
                        ),
                        ft.TextButton(
                            "Resolver",
                            style=ft.ButtonStyle(color=AppTheme.SUCCESS),
                            on_click=lambda e, aid=alert_id:
                                self._on_resolve(aid),
                        ),
                        ft.IconButton(
                            ft.icons.CLOSE_ROUNDED,
                            icon_size=14, icon_color=c["text_secondary"],
                            tooltip="Ignorar",
                            on_click=lambda e, aid=alert_id:
                                self._on_ignore(aid),
                        ),
                    ], spacing=0, width=180),

                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                border=ft.border.only(
                    bottom=ft.border.BorderSide(1, c["divider"]),
                ),
            )
            self._alert_col.controls.append(row)

    # ================================================================== #
    # Banner de alertas                                                   #
    # ================================================================== #

    def _build_alert_banner(self, summary: dict) -> ft.Container:
        c         = self.colors
        total     = summary.get("total_new", 0)
        critical  = summary.get("critical", 0)
        warning   = summary.get("warning", 0)
        top_items = summary.get("top_critical", [])

        parts = []
        if critical: parts.append(f"{critical} agotado(s)")
        if warning:  parts.append(f"{warning} stock bajo")
        detail = ", ".join(parts) or f"{total} alerta(s)"

        preview = ", ".join(
            a.get("product_name", "—") for a in top_items[:3]
        )
        if len(top_items) > 3:
            preview += f" y {total - 3} más"

        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color="white", size=20),
                ft.Column([
                    ft.Text(f"⚠  {detail}", color="white",
                            size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(preview, color="white", size=11, opacity=0.9),
                ], spacing=2, tight=True, expand=True),
                ft.TextButton(
                    "Ver alertas",
                    style=ft.ButtonStyle(color="white"),
                    on_click=lambda e: self._switch_to_alerts_tab(),
                ),
            ], spacing=12),
            bgcolor=AppTheme.WARNING,
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
        )

    # ================================================================== #
    # Dialog: Ajustar stock                                               #
    # ================================================================== #

    def _show_adjust_dialog(self, item: dict):
        c           = self.colors
        product_id  = item.get("product_id", "")
        name        = item.get("product_name", "—")
        stock_act   = item.get("stock_actual", 0)
        stock_min   = item.get("stock_minimo", 5)

        stock_f = AppTheme.make_text_field("Nuevo stock *", colors=c,
                                           value=str(stock_act))
        minimo_f = AppTheme.make_text_field("Stock mínimo", colors=c,
                                            value=str(stock_min))
        notas_f  = AppTheme.make_text_field("Motivo del ajuste", colors=c)

        def on_save(e):
            try:
                nuevo  = int(stock_f.value or 0)
                minimo = int(minimo_f.value or stock_min)
            except ValueError:
                self.app.show_snackbar("Valores numéricos inválidos", error=True)
                return
            ok = self.ctrl.adjust_stock(product_id, nuevo, minimo,
                                        notas_f.value or "")
            if ok:
                dialog.open = False
                self._load_data()
                self._render_inventory_rows()
                self._render_alert_rows()
                self.page.update()

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.EDIT_NOTE_ROUNDED, color=AppTheme.ACCENT),
                ft.Text(f"Ajustar Stock — {name}", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Text("Stock actual:", size=13,
                                    color=c["text_secondary"]),
                            ft.Text(str(stock_act), size=18,
                                    weight=ft.FontWeight.BOLD, color=c["text"]),
                        ], spacing=8),
                        padding=ft.padding.symmetric(vertical=8),
                    ),
                    ft.Row([stock_f, minimo_f], spacing=10),
                    notas_f,
                ], spacing=10, tight=True),
                width=400,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Guardar", color="white",
                                    weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(), border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_save, ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ================================================================== #
    # Dialog: Configurar umbrales (NUEVO)                                 #
    # ================================================================== #

    def _show_threshold_dialog(self, item: dict):
        """
        Modal para editar stock_minimo, stock_maximo, reorder_point y
        reorder_quantity. Carga el threshold existente del producto.

        DECISIÓN: cargamos el threshold desde el controller (que llama al
        servicio con defaults si no existe). No reutilizamos los datos del
        item porque la RPC solo trae min/max, no reorder.
        """
        c          = self.colors
        product_id = item.get("product_id", "")
        name       = item.get("product_name", "—")

        th = self.ctrl.get_threshold_for_product(product_id)

        min_f     = AppTheme.make_text_field("Stock mínimo *", colors=c,
                        value=str(th.get("stock_minimo", 5)))
        max_f     = AppTheme.make_text_field("Stock máximo *", colors=c,
                        value=str(th.get("stock_maximo", 100)))
        reorder_f = AppTheme.make_text_field("Punto de reorden", colors=c,
                        value=str(th.get("reorder_point", 10)))
        qty_f     = AppTheme.make_text_field("Cantidad a reponer", colors=c,
                        value=str(th.get("reorder_quantity", 50)))
        alert_low = ft.Checkbox(label="Alertar cuando stock esté bajo",
                                value=th.get("alert_on_low_stock", True))
        alert_over = ft.Checkbox(label="Alertar cuando haya exceso de stock",
                                 value=th.get("alert_on_overstock", False))

        def on_save(e):
            try:
                s_min = int(min_f.value or 0)
                s_max = int(max_f.value or 0)
                rp    = int(reorder_f.value or s_min)
                rq    = int(qty_f.value or 50)
            except ValueError:
                self.app.show_snackbar("Valores numéricos inválidos", error=True)
                return
            ok = self.ctrl.update_threshold(
                product_id, s_min, s_max, rp, rq,
                alert_low.value, alert_over.value,
            )
            if ok:
                dialog.open = False
                self._load_data()
                self._render_inventory_rows()
                self.page.update()

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.TUNE_ROUNDED, color=AppTheme.BLUE),
                ft.Text(f"Umbrales — {name}", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Niveles de stock", size=12,
                            color=c["text_secondary"],
                            weight=ft.FontWeight.W_600),
                    ft.Row([min_f, max_f], spacing=10),
                    ft.Text("Reorden automático", size=12,
                            color=c["text_secondary"],
                            weight=ft.FontWeight.W_600),
                    ft.Row([reorder_f, qty_f], spacing=10),
                    ft.Text("Alertas", size=12,
                            color=c["text_secondary"],
                            weight=ft.FontWeight.W_600),
                    alert_low,
                    alert_over,
                ], spacing=10, tight=True),
                width=440,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Guardar umbrales", color="white",
                                    weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(), border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_save, ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ================================================================== #
    # Dialog: Historial / Kardex (mejorado)                              #
    # ================================================================== #

    def _show_kardex_dialog(self, product_id: str, name: str):
        c        = self.colors
        kardex   = self.ctrl.get_kardex(product_id)
        mov_log  = self.ctrl.get_movements_log(product_id)

        def _build_kardex_rows(items: list) -> ft.Column:
            if not items:
                return ft.Column([
                    ft.Text("Sin historial", color=c["text_secondary"],
                            size=13)
                ])
            controls = []
            for k in items:
                tipo  = k.get("tipo", k.get("movement_type", "—"))
                qty   = k.get("cantidad", k.get("quantity_change", 0))
                ant   = k.get("saldo_anterior", k.get("quantity_before", "—"))
                post  = k.get("saldo_posterior", k.get("quantity_after", "—"))
                date  = str(k.get("created_at", ""))[:16]
                nota  = k.get("notas", k.get("notes", ""))

                tipo_color = (AppTheme.SUCCESS if tipo in ("entrada", "inicio", "purchase")
                              else AppTheme.ERROR if tipo in ("salida", "sale")
                              else c["text_secondary"])

                controls.append(ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(tipo, size=10, color="white"),
                            bgcolor=tipo_color, border_radius=12,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            width=80,
                        ),
                        ft.Text(f"{ant} → {post}", size=12,
                                color=c["text"], width=90),
                        ft.Text(f"Δ {qty:+}" if isinstance(qty, int) else str(qty),
                                size=12, color=tipo_color, width=60),
                        ft.Text(nota or "—", size=11,
                                color=c["text_secondary"], expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(date, size=10, color=c["text_secondary"], width=110),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=6, horizontal=4),
                    border=ft.border.only(
                        bottom=ft.border.BorderSide(1, c["divider"])
                    ),
                ))
            return ft.Column(controls, spacing=0, scroll=ft.ScrollMode.AUTO)

        content = ft.Tabs(
            animation_duration=150,
            tabs=[
                ft.Tab(text="Kardex",
                       content=ft.Container(
                           content=_build_kardex_rows(kardex),
                           height=300, padding=ft.padding.only(top=8),
                       )),
                ft.Tab(text="Movimientos",
                       content=ft.Container(
                           content=_build_kardex_rows(mov_log),
                           height=300, padding=ft.padding.only(top=8),
                       )),
            ],
        )

        def on_close(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.HISTORY_ROUNDED, color=AppTheme.BLUE),
                ft.Text(f"Historial — {name}", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(content=content, width=620),
            actions=[ft.TextButton("Cerrar", on_click=on_close)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ================================================================== #
    # Acciones de alertas                                                 #
    # ================================================================== #

    def _on_acknowledge(self, alert_id: str):
        ok = self.ctrl.acknowledge_alert(alert_id)
        if ok:
            self._alerts = self.ctrl.get_new_alerts()
            self._render_alert_rows()
            self.page.update()

    def _on_resolve(self, alert_id: str):
        ok = self.ctrl.resolve_alert(alert_id)
        if ok:
            self._alerts = self.ctrl.get_new_alerts()
            self._render_alert_rows()
            self.page.update()

    def _on_ignore(self, alert_id: str):
        ok = self.ctrl.ignore_alert(alert_id)
        if ok:
            self._alerts = self.ctrl.get_new_alerts()
            self._render_alert_rows()
            self.page.update()

    # ================================================================== #
    # Helpers                                                             #
    # ================================================================== #

    def _load_data(self):
        """Recarga inventario y alertas del controller."""
        self._inventory = self.ctrl.get_inventory()
        self._alerts    = self.ctrl.get_new_alerts()

    def _refresh(self, e=None):
        """Recarga completa con regeneración de alertas."""
        self.ctrl.generate_alerts()
        self._load_data()
        self._render_inventory_rows()
        self._render_alert_rows()
        self.page.update()

    def _on_tab_change(self, e):
        self._tab_idx = e.control.selected_index

    def _switch_to_alerts_tab(self):
        """Desde el banner, navega al tab de Alertas."""
        self._tab_idx = 1
        # Rebuild completo para reflejar el tab activo
        # (Flet no expone set_selected_index sin rebuild)
        new_content = self.build()
        # La vista se reemplaza vía app.navigate_to si existe el método,
        # de lo contrario el usuario puede hacer clic en el tab directamente.
        self.page.update()