# presentation/views/inventory_view.py
#
# ============================================================================
# FASE 5 — Inventario Inteligente: rediseño completo con tabs
# ============================================================================
#
# ESTRUCTURA NUEVA: 4 tabs
#   [Inventario]  — tabla principal con stock_status visual + acciones por fila
#   [Alertas]     — panel de alertas con lifecycle (new→ack→resolved/ignored)
#   [Reorden]     — lista de productos que necesitan compra, con cantidad sugerida
#   [Umbrales]    — configuración de min/max/reorder por producto
#
# CAMBIOS RESPECTO A VERSIÓN PRE-F5:
#   - Tab "Inventario" ahora usa get_inventory_full() (RPC con stock_status)
#     en lugar de get_inventory() + classify_inventory() en Python.
#   - La columna "Estado" muestra chips de color: ok/warning/critical/out_of_stock.
#   - Botón "Entrada stock" (nueva compra) además del ajuste manual.
#   - Tab "Alertas" es completamente nueva: lista con acciones ack/resolve/ignore.
#   - Tab "Reorden" es completamente nueva: tabla con cantidad a comprar.
#   - Tab "Umbrales" es completamente nueva: formulario por producto.
#
# ELEMENTOS CONSERVADOS:
#   - Dialog de ajuste de stock (expandido con campo notas).
#   - Dialog de kardex (sin cambios).
#   - Banner de stock bajo en la tab de Alertas (reemplaza al header global).
#   - _refresh(): sigue navegando a "inventory" para forzar rebuild.
#
# DECISIÓN DE DISEÑO:
#   Usar ft.Tabs nativo de Flet (no implementación propia) para mantener
#   consistencia con otros patrones de la app. El tab index se inicializa
#   en 0 (Inventario) y si llega _initial_tab desde app.navigate_to con
#   parámetro, se puede fijar en Alertas.
#
# PATRÓN SEGUIDO:
#   Igual que ProductsView/SalesView: __init__ recibe dependencias inyectadas,
#   build() construye y devuelve ft.Container. Sin lógica de negocio.

from __future__ import annotations

import flet as ft
from presentation.theme import AppTheme


# Paleta de colores por estado de stock
STATUS_COLORS = {
    "ok":           ("#00D9A3", ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED),
    "warning":      ("#FFB347", ft.icons.WARNING_AMBER_ROUNDED),
    "critical":     ("#FF5F7E", ft.icons.ERROR_OUTLINE_ROUNDED),
    "out_of_stock": ("#FF5F7E", ft.icons.REMOVE_SHOPPING_CART_ROUNDED),
}
STATUS_LABELS = {
    "ok":           "OK",
    "warning":      "Bajo",
    "critical":     "Crítico",
    "out_of_stock": "Agotado",
}
ALERT_TYPE_LABELS = {
    "low_stock":   "Stock bajo",
    "out_of_stock":"Sin stock",
    "overstock":   "Sobre stock",
    "expiring":    "Por vencer",
}


class InventoryView:

    def __init__(
        self,
        page,
        colors,
        is_dark,
        inventory_controller,
        app,
        initial_tab: int = 0,       # 0=Inventario, 1=Alertas, 2=Reorden, 3=Umbrales
    ):
        self.page      = page
        self.colors    = colors
        self.is_dark   = is_dark
        self.ctrl      = inventory_controller
        self.app       = app
        self._tab      = initial_tab

        # Estado interno (cargado en build)
        self._inventory: list[dict] = []
        self._alerts:    list[dict] = []
        self._reorder:   list[dict] = []
        self._thresholds: dict[str, dict] = {}   # {product_id: threshold}

        # Columna mutable de filas (se rebuiltea al filtrar)
        self._rows_col    = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self._alerts_col  = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self._reorder_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

    # ================================================================== #
    # BUILD PRINCIPAL                                                    #
    # ================================================================== #

    def build(self):
        c = self.colors

        # Cargar datos
        self._inventory  = self.ctrl.get_inventory_full()
        alerts_count     = self.ctrl.get_alerts_count(status="new")
        self._alerts     = self.ctrl.get_alerts(status="new")
        self._reorder    = self.ctrl.get_reorder_list()
        self._thresholds = {
            t["product_id"]: t for t in self.ctrl.get_thresholds()
        }

        # Refresh
        refresh_btn = ft.IconButton(
            ft.icons.REFRESH_ROUNDED,
            icon_color=AppTheme.ACCENT,
            tooltip="Actualizar inventario",
            on_click=self._refresh,
        )

        # KPI rápidos
        kpi_row = self._build_kpi_row(alerts_count)

        # Tabs
        tabs = ft.Tabs(
            selected_index=self._tab,
            animation_duration=200,
            tab_alignment=ft.TabAlignment.START,
            label_color=AppTheme.ACCENT,
            unselected_label_color=c["text_secondary"],
            indicator_color=AppTheme.ACCENT,
            indicator_tab_size=False,
            tabs=[
                ft.Tab(
                    text="Inventario",
                    icon=ft.icons.WAREHOUSE_ROUNDED,
                    content=self._build_tab_inventario(),
                ),
                ft.Tab(
                    text=f"Alertas ({alerts_count})" if alerts_count else "Alertas",
                    icon=ft.icons.NOTIFICATIONS_ACTIVE_ROUNDED
                         if alerts_count else ft.icons.NOTIFICATIONS_NONE_ROUNDED,
                    content=self._build_tab_alertas(),
                ),
                ft.Tab(
                    text=f"Reorden ({len(self._reorder)})" if self._reorder else "Reorden",
                    icon=ft.icons.SHOPPING_CART_ROUNDED,
                    content=self._build_tab_reorden(),
                ),
                ft.Tab(
                    text="Umbrales",
                    icon=ft.icons.TUNE_ROUNDED,
                    content=self._build_tab_umbrales(),
                ),
            ],
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                [
                    AppTheme.page_header(
                        "Inventario",
                        f"{len(self._inventory)} productos · {alerts_count} alertas activas",
                        c,
                        action=refresh_btn,
                    ),
                    ft.Container(height=12),
                    kpi_row,
                    ft.Container(height=16),
                    tabs,
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.padding.all(28),
            bgcolor=c["bg"],
        )

    # ================================================================== #
    # KPI ROW                                                            #
    # ================================================================== #

    def _build_kpi_row(self, alerts_count: int) -> ft.Row:
        c = self.colors
        total   = len(self._inventory)
        ok_cnt  = sum(1 for i in self._inventory if i.get("stock_status") == "ok")
        warn_cnt = sum(1 for i in self._inventory if i.get("stock_status") in ("warning","critical","out_of_stock"))
        oos_cnt  = sum(1 for i in self._inventory if i.get("stock_status") == "out_of_stock")

        return ft.Row(
            [
                AppTheme.stat_card("Total productos",  str(total),    ft.icons.WAREHOUSE_ROUNDED,          AppTheme.gradient_info(),    c),
                AppTheme.stat_card("En stock OK",       str(ok_cnt),   ft.icons.CHECK_CIRCLE_ROUNDED,        AppTheme.gradient_success(), c),
                AppTheme.stat_card("Stock bajo/crítico",str(warn_cnt), ft.icons.WARNING_AMBER_ROUNDED,       AppTheme.gradient_warning(), c),
                AppTheme.stat_card("Agotados",          str(oos_cnt),  ft.icons.REMOVE_SHOPPING_CART_ROUNDED, AppTheme.gradient_error(),   c),
            ],
            spacing=12,
        )

    # ================================================================== #
    # TAB 1: INVENTARIO                                                  #
    # ================================================================== #

    def _build_tab_inventario(self) -> ft.Container:
        c = self.colors

        search = AppTheme.make_text_field("Buscar producto...", colors=c)
        search.expand = True
        search.prefix_icon = ft.icons.SEARCH_ROUNDED
        search.on_change = lambda e: self._filter_inventory(e.control.value)

        # Dropdown de filtro por status
        status_dd = ft.Dropdown(
            options=[
                ft.dropdown.Option("", "Todos"),
                ft.dropdown.Option("ok",           "OK"),
                ft.dropdown.Option("warning",       "Stock bajo"),
                ft.dropdown.Option("critical",      "Crítico"),
                ft.dropdown.Option("out_of_stock",  "Agotado"),
            ],
            value="",
            width=160,
            bgcolor=c["input_fill"],
            border_color=c["border"],
            color=c["text"],
            on_change=lambda e: self._filter_inventory_by_status(e.control.value),
        )

        col_header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Producto",      size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=3),
                    ft.Text("SKU",           size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Stock actual",  size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Mín / Máx",    size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Estado",        size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Acciones",      size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=c["surface"],
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
        )

        self._render_inventory_rows()

        table = ft.Container(
            content=ft.Column(
                [col_header, self._rows_col],
                spacing=0,
                expand=True,
            ),
            bgcolor=c["surface"],
            border_radius=12,
            border=ft.border.all(1, c["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=12),
                    ft.Row([search, status_dd], spacing=10),
                    ft.Container(height=12),
                    table,
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.padding.only(top=4),
        )

    def _render_inventory_rows(self, items: list = None):  # type: ignore
        c    = self.colors
        data = items if items is not None else self._inventory
        self._rows_col.controls.clear()

        if not data:
            self._rows_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.icons.WAREHOUSE_ROUNDED, size=48, color=c["text_secondary"]),
                            ft.Text("Sin productos en inventario", color=c["text_secondary"]),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=ft.padding.all(40),
                )
            )
            return

        for item in data:
            status       = item.get("stock_status", "ok")
            color, icon  = STATUS_COLORS.get(status, ("#8B8FA8", ft.icons.CIRCLE_OUTLINED))
            label        = STATUS_LABELS.get(status, status)
            stock        = item.get("stock_actual", 0)
            min_s        = item.get("stock_minimo", 0)
            max_s        = item.get("stock_maximo", 0)
            name         = item.get("product_name", "—")
            sku          = item.get("sku", "—")
            pid          = item.get("product_id", "")

            status_chip = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=12, color=color),
                        ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
                    ],
                    spacing=4, tight=True,
                ),
                bgcolor=f"{color}20",
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
            )

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(name,            size=13, color=c["text"],           expand=3, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(sku or "—",      size=12, color=c["text_secondary"], expand=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(str(stock),      size=14, color=color,               expand=2, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{min_s} / {max_s}", size=12, color=c["text_secondary"], expand=2),
                        ft.Container(content=status_chip, expand=2),
                        ft.Row(
                            [
                                ft.IconButton(
                                    ft.icons.EDIT_ROUNDED,
                                    icon_size=16,
                                    icon_color=AppTheme.ACCENT,
                                    tooltip="Ajustar stock",
                                    on_click=lambda e, i=item: self._show_adjust_dialog(i),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ),
                                ft.IconButton(
                                    ft.icons.ADD_SHOPPING_CART_ROUNDED,
                                    icon_size=16,
                                    icon_color=AppTheme.SUCCESS,
                                    tooltip="Entrada de compra",
                                    on_click=lambda e, i=item: self._show_purchase_dialog(i),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ),
                                ft.IconButton(
                                    ft.icons.HISTORY_ROUNDED,
                                    icon_size=16,
                                    icon_color=AppTheme.BLUE,
                                    tooltip="Ver kardex",
                                    on_click=lambda e, i=item: self._show_kardex_dialog(i),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ),
                            ],
                            spacing=0,
                            expand=2,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
                on_hover=lambda e: setattr(e.control, "bgcolor",
                    c["hover"] if e.data == "true" else "transparent"),
                animate=ft.animation.Animation(150, ft.AnimationCurve.EASE_OUT),
            )
            self._rows_col.controls.append(row)

        try:
            self._rows_col.update()
        except Exception:
            pass

    def _filter_inventory(self, query: str):
        q = (query or "").lower()
        filtered = [
            i for i in self._inventory
            if q in i.get("product_name", "").lower()
            or q in (i.get("sku") or "").lower()
            or q in (i.get("barcode") or "").lower()
        ]
        self._render_inventory_rows(filtered)

    def _filter_inventory_by_status(self, status: str):
        filtered = (
            [i for i in self._inventory if i.get("stock_status") == status]
            if status else self._inventory
        )
        self._render_inventory_rows(filtered)

    # ================================================================== #
    # TAB 2: ALERTAS                                                     #
    # ================================================================== #

    def _build_tab_alertas(self) -> ft.Container:
        c = self.colors

        # Botones de cabecera
        gen_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.icons.REFRESH_ROUNDED, color="white", size=15),
                 ft.Text("Generar alertas", color="white", size=12, weight=ft.FontWeight.W_600)],
                spacing=6, tight=True,
            ),
            gradient=AppTheme.gradient_primary(),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            on_click=self._on_generate_alerts,
            ink=True,
        )

        ack_all_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.icons.DONE_ALL_ROUNDED, color=AppTheme.SUCCESS, size=15),
                 ft.Text("Marcar todo visto", color=AppTheme.SUCCESS, size=12, weight=ft.FontWeight.W_600)],
                spacing=6, tight=True,
            ),
            bgcolor=f"{AppTheme.SUCCESS}18",
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            on_click=self._on_ack_all,
            ink=True,
        )

        # Filtro por status
        status_filter = ft.Dropdown(
            options=[
                ft.dropdown.Option("new",          "Sin revisar"),
                ft.dropdown.Option("acknowledged", "Revisadas"),
                ft.dropdown.Option("resolved",     "Resueltas"),
                ft.dropdown.Option("ignored",      "Ignoradas"),
            ],
            value="new",
            width=160,
            bgcolor=c["input_fill"],
            border_color=c["border"],
            color=c["text"],
            on_change=lambda e: self._reload_alerts(e.control.value),
        )

        self._render_alerts_rows()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=12),
                    ft.Row([status_filter, ft.Container(expand=True), ack_all_btn, gen_btn], spacing=10),
                    ft.Container(height=12),
                    ft.Container(
                        content=ft.Column(
                            [self._alerts_col],
                            expand=True,
                        ),
                        bgcolor=c["surface"],
                        border_radius=12,
                        border=ft.border.all(1, c["border"]),
                        expand=True,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        padding=ft.padding.all(8),
                    ),
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.padding.only(top=4),
        )

    def _render_alerts_rows(self, alerts: list = None):  # type: ignore
        c    = self.colors
        data = alerts if alerts is not None else self._alerts
        self._alerts_col.controls.clear()

        if not data:
            self._alerts_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.icons.NOTIFICATIONS_OFF_ROUNDED, size=48, color=c["text_secondary"]),
                            ft.Text("No hay alertas en este estado", color=c["text_secondary"]),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    alignment=ft.alignment.center,
                    padding=ft.padding.all(40),
                )
            )
            return

        for alert in data:
            atype    = alert.get("alert_type", "")
            severity = alert.get("severity", "warning")
            color    = AppTheme.ERROR if severity == "critical" else AppTheme.WARNING
            label    = ALERT_TYPE_LABELS.get(atype, atype)
            name     = alert.get("product_name", "Producto")
            stock    = alert.get("stock_actual", 0)
            minimo   = alert.get("stock_minimo", 0)
            maximo   = alert.get("stock_maximo", 0)
            aid      = alert.get("id", "")
            gen_at   = (alert.get("generated_at") or "")[:16].replace("T", " ")
            status   = alert.get("status", "new")

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(
                                ft.icons.ERROR_OUTLINE_ROUNDED if severity == "critical"
                                else ft.icons.WARNING_AMBER_ROUNDED,
                                color=color, size=22,
                            ),
                            width=40,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(name, size=13, color=c["text"], weight=ft.FontWeight.W_600),
                                        ft.Container(
                                            content=ft.Text(label, size=10, color=color, weight=ft.FontWeight.W_600),
                                            bgcolor=f"{color}20",
                                            border_radius=6,
                                            padding=ft.padding.symmetric(horizontal=7, vertical=3),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    f"Stock: {stock} | Mín: {minimo} | Máx: {maximo}  ·  {gen_at}",
                                    size=11,
                                    color=c["text_secondary"],
                                ),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        # Acciones (solo si status='new')
                        ft.Row(
                            [
                                ft.IconButton(
                                    ft.icons.VISIBILITY_ROUNDED,
                                    icon_size=16,
                                    icon_color=AppTheme.BLUE,
                                    tooltip="Marcar como vista",
                                    on_click=lambda e, aid=aid: self._on_ack(aid),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ) if status == "new" else ft.Container(width=32),
                                ft.IconButton(
                                    ft.icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                                    icon_size=16,
                                    icon_color=AppTheme.SUCCESS,
                                    tooltip="Marcar como resuelta",
                                    on_click=lambda e, aid=aid: self._on_resolve(aid),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ) if status != "resolved" else ft.Container(width=32),
                                ft.IconButton(
                                    ft.icons.CANCEL_OUTLINED,
                                    icon_size=16,
                                    icon_color=c["text_secondary"],
                                    tooltip="Ignorar",
                                    on_click=lambda e, aid=aid: self._on_ignore(aid),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ) if status not in ("resolved", "ignored") else ft.Container(width=32),
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
                bgcolor=c["card"],
                border_radius=10,
                border=ft.border.all(1, f"{color}40"),
            )
            self._alerts_col.controls.append(card)

        try:
            self._alerts_col.update()
        except Exception:
            pass

    def _reload_alerts(self, status: str):
        self._alerts = self.ctrl.get_alerts(status=status)
        self._render_alerts_rows()

    def _on_ack(self, alert_id: str):
        if self.ctrl.acknowledge_alert(alert_id):
            self._alerts = [a for a in self._alerts if a.get("id") != alert_id]
            self._render_alerts_rows()

    def _on_resolve(self, alert_id: str):
        if self.ctrl.resolve_alert(alert_id):
            self._alerts = [a for a in self._alerts if a.get("id") != alert_id]
            self._render_alerts_rows()

    def _on_ignore(self, alert_id: str):
        if self.ctrl.ignore_alert(alert_id):
            self._alerts = [a for a in self._alerts if a.get("id") != alert_id]
            self._render_alerts_rows()

    def _on_generate_alerts(self, e):
        self.ctrl.trigger_alerts()
        self._alerts = self.ctrl.get_alerts(status="new")
        self._render_alerts_rows()

    def _on_ack_all(self, e):
        self.ctrl.acknowledge_all_alerts()
        self._alerts = []
        self._render_alerts_rows()

    # ================================================================== #
    # TAB 3: REORDEN                                                     #
    # ================================================================== #

    def _build_tab_reorden(self) -> ft.Container:
        c = self.colors

        col_header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Producto",         size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=3),
                    ft.Text("Stock actual",      size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Punto reorden",     size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Cantidad sugerida", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Estado",            size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Acción",            size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=c["surface"],
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
        )

        self._render_reorder_rows()

        table = ft.Container(
            content=ft.Column(
                [col_header, self._reorder_col],
                spacing=0,
                expand=True,
            ),
            bgcolor=c["surface"],
            border_radius=12,
            border=ft.border.all(1, c["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        nota = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, size=15, color=c["text_secondary"]),
                    ft.Text(
                        "Productos con stock ≤ punto de reorden. Haz clic en  +  para registrar una entrada.",
                        size=12, color=c["text_secondary"],
                    ),
                ],
                spacing=6,
            ),
            padding=ft.padding.symmetric(horizontal=4, vertical=4),
        )

        return ft.Container(
            content=ft.Column([ft.Container(height=12), nota, ft.Container(height=8), table], expand=True),
            expand=True,
            padding=ft.padding.only(top=4),
        )

    def _render_reorder_rows(self, items: list = None):  # type: ignore
        c    = self.colors
        data = items if items is not None else self._reorder
        self._reorder_col.controls.clear()

        if not data:
            self._reorder_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.icons.THUMB_UP_ROUNDED, size=48, color=AppTheme.SUCCESS),
                            ft.Text("¡Todo el inventario está en orden!", color=c["text_secondary"]),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    alignment=ft.alignment.center,
                    padding=ft.padding.all(40),
                )
            )
            return

        for item in data:
            status        = item.get("stock_status", "warning")
            color, icon   = STATUS_COLORS.get(status, ("#FFB347", ft.icons.WARNING_AMBER_ROUNDED))
            label         = STATUS_LABELS.get(status, status)
            name          = item.get("product_name", "—")
            stock         = item.get("stock_actual", 0)
            reorder_pt    = item.get("reorder_point", 0)
            reorder_qty   = item.get("reorder_quantity", 0)
            pid           = item.get("product_id", "")

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(name,           size=13, color=c["text"],           expand=3, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(str(stock),     size=14, color=color,               expand=2, weight=ft.FontWeight.BOLD),
                        ft.Text(str(reorder_pt),size=13, color=c["text_secondary"], expand=2),
                        ft.Container(
                            content=ft.Text(
                                f"+{reorder_qty}",
                                size=13, color="white", weight=ft.FontWeight.BOLD,
                            ),
                            bgcolor=AppTheme.SUCCESS,
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            expand=2,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [ft.Icon(icon, size=12, color=color),
                                 ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600)],
                                spacing=4, tight=True,
                            ),
                            bgcolor=f"{color}20",
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            expand=2,
                        ),
                        ft.IconButton(
                            ft.icons.ADD_SHOPPING_CART_ROUNDED,
                            icon_size=16,
                            icon_color=AppTheme.SUCCESS,
                            tooltip=f"Registrar entrada de +{reorder_qty} unidades",
                            on_click=lambda e, i=item: self._show_purchase_dialog(i),
                            style=ft.ButtonStyle(padding=ft.padding.all(4)),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
            )
            self._reorder_col.controls.append(row)

        try:
            self._reorder_col.update()
        except Exception:
            pass

    # ================================================================== #
    # TAB 4: UMBRALES                                                    #
    # ================================================================== #

    def _build_tab_umbrales(self) -> ft.Container:
        c = self.colors

        info_box = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.icons.TUNE_ROUNDED, size=16, color=AppTheme.ACCENT),
                    ft.Text(
                        "Configura los niveles de stock de cada producto. "
                        "Haz clic en el ícono de edición para personalizar.",
                        size=12, color=c["text_secondary"],
                    ),
                ],
                spacing=8,
            ),
            bgcolor=f"{AppTheme.ACCENT}12",
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
        )

        col_header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Producto",    size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=3),
                    ft.Text("Mínimo",      size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Máximo",      size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Reorden en", size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Comprar",    size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Alertas",    size=12, color=c["text_secondary"], weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("",           size=12, expand=1),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=c["surface"],
            border_radius=ft.border_radius.only(top_left=10, top_right=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
        )

        rows_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._render_threshold_rows(rows_col)

        table = ft.Container(
            content=ft.Column([col_header, rows_col], spacing=0, expand=True),
            bgcolor=c["surface"],
            border_radius=12,
            border=ft.border.all(1, c["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        return ft.Container(
            content=ft.Column([ft.Container(height=12), info_box, ft.Container(height=12), table], expand=True),
            expand=True,
            padding=ft.padding.only(top=4),
        )

    def _render_threshold_rows(self, rows_col: ft.Column):
        c = self.colors
        rows_col.controls.clear()

        if not self._inventory:
            rows_col.controls.append(
                ft.Container(
                    content=ft.Text("Sin productos", color=c["text_secondary"]),
                    alignment=ft.alignment.center,
                    padding=ft.padding.all(30),
                )
            )
            return

        for item in self._inventory:
            pid  = item.get("product_id", "")
            name = item.get("product_name", "—")
            th   = self._thresholds.get(pid, {})

            min_v  = th.get("stock_minimo", item.get("stock_minimo", 10))
            max_v  = th.get("stock_maximo", 100)
            rp     = th.get("reorder_point", 20)
            rq     = th.get("reorder_quantity", 50)
            low_al = th.get("alert_on_low_stock", True)
            ov_al  = th.get("alert_on_overstock", False)

            alerts_text = " + ".join(filter(None, [
                "bajo" if low_al else "",
                "sobre" if ov_al else "",
            ])) or "ninguna"

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(name,             size=12, color=c["text"],           expand=3, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(str(min_v),        size=12, color=c["text_secondary"], expand=1),
                        ft.Text(str(max_v),        size=12, color=c["text_secondary"], expand=1),
                        ft.Text(str(rp),           size=12, color=c["text_secondary"], expand=1),
                        ft.Text(str(rq),           size=12, color=c["text_secondary"], expand=1),
                        ft.Text(alerts_text,       size=11, color=c["text_secondary"], expand=2),
                        ft.IconButton(
                            ft.icons.EDIT_ROUNDED,
                            icon_size=15,
                            icon_color=AppTheme.ACCENT,
                            tooltip="Configurar umbral",
                            on_click=lambda e, i=item, t=th: self._show_threshold_dialog(i, t),
                            style=ft.ButtonStyle(padding=ft.padding.all(4)),
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
            )
            rows_col.controls.append(row)

    # ================================================================== #
    # DIÁLOGOS                                                           #
    # ================================================================== #

    def _show_adjust_dialog(self, item: dict):
        c      = self.colors
        name   = item.get("product_name", "Producto")
        stock  = item.get("stock_actual", 0)
        pid    = item.get("product_id", "")
        min_v  = item.get("stock_minimo", 5)

        stock_f = AppTheme.make_text_field(
            "Nuevo stock *", colors=c, value=str(stock)
        )
        stock_f.keyboard_type = ft.KeyboardType.NUMBER

        minimo_f = AppTheme.make_text_field(
            "Stock mínimo (opcional)", colors=c, value=str(min_v)
        )
        minimo_f.keyboard_type = ft.KeyboardType.NUMBER

        notas_f = AppTheme.make_text_field(
            "Motivo del ajuste", colors=c,
        )

        def on_save(e):
            try:
                nuevo  = int(stock_f.value or 0)
                minimo = int(minimo_f.value) if minimo_f.value else None
                notas  = notas_f.value or ""
                ok = self.ctrl.adjust_stock(pid, nuevo, minimo, notas)
                if ok:
                    dialog.open = False
                    self.page.update()
                    # Actualizar fila sin reload completo
                    item["stock_actual"] = nuevo
                    if minimo is not None:
                        item["stock_minimo"] = minimo
                    self._refresh_inventory_inline()
            except ValueError:
                self.app.show_snackbar("Ingresa un número válido", error=True)

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.icons.EDIT_ROUNDED, color=AppTheme.ACCENT),
                 ft.Text(f"Ajustar stock — {name}", weight=ft.FontWeight.BOLD)],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"Stock actual: {stock}", size=13, color=c["text_secondary"]),
                        ft.Container(height=8),
                        stock_f,
                        ft.Container(height=8),
                        minimo_f,
                        ft.Container(height=8),
                        notas_f,
                    ],
                    spacing=4,
                    tight=True,
                ),
                width=360,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Guardar", color="white", weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_save,
                    ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open      = True
        self.page.update()

    def _show_purchase_dialog(self, item: dict):
        """Diálogo de entrada de stock por compra."""
        c      = self.colors
        name   = item.get("product_name", "Producto")
        pid    = item.get("product_id", "")
        rq     = item.get("reorder_quantity", 50)

        qty_f = AppTheme.make_text_field(
            "Cantidad a ingresar *", colors=c, value=str(rq)
        )
        qty_f.keyboard_type = ft.KeyboardType.NUMBER

        notas_f = AppTheme.make_text_field(
            "Referencia (factura, proveedor...)", colors=c,
        )

        def on_save(e):
            try:
                qty = int(qty_f.value or 0)
                if qty <= 0:
                    self.app.show_snackbar("La cantidad debe ser mayor a 0", error=True)
                    return
                ok = self.ctrl.purchase_stock(pid, qty, notas=notas_f.value or "")
                if ok:
                    dialog.open = False
                    self.page.update()
                    item["stock_actual"] = item.get("stock_actual", 0) + qty
                    self._refresh_inventory_inline()
            except ValueError:
                self.app.show_snackbar("Ingresa un número válido", error=True)

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.icons.ADD_SHOPPING_CART_ROUNDED, color=AppTheme.SUCCESS),
                 ft.Text(f"Entrada de stock — {name}", weight=ft.FontWeight.BOLD)],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column([qty_f, ft.Container(height=8), notas_f], spacing=4, tight=True),
                width=360,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Registrar entrada", color="white", weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_success(),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_save,
                    ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open      = True
        self.page.update()

    def _show_threshold_dialog(self, item: dict, threshold: dict):
        c    = self.colors
        name = item.get("product_name", "Producto")
        pid  = item.get("product_id", "")

        min_f = AppTheme.make_text_field("Stock mínimo *",       colors=c, value=str(threshold.get("stock_minimo", 10)))
        max_f = AppTheme.make_text_field("Stock máximo *",       colors=c, value=str(threshold.get("stock_maximo", 100)))
        rp_f  = AppTheme.make_text_field("Punto de reorden *",   colors=c, value=str(threshold.get("reorder_point", 20)))
        rq_f  = AppTheme.make_text_field("Cantidad a comprar *", colors=c, value=str(threshold.get("reorder_quantity", 50)))
        for f in (min_f, max_f, rp_f, rq_f):
            f.keyboard_type = ft.KeyboardType.NUMBER

        low_switch = ft.Switch(
            label="Alerta stock bajo",
            value=threshold.get("alert_on_low_stock", True),
            active_color=AppTheme.ACCENT,
        )
        over_switch = ft.Switch(
            label="Alerta sobre stock",
            value=threshold.get("alert_on_overstock", False),
            active_color=AppTheme.WARNING,
        )

        def on_save(e):
            try:
                ok = self.ctrl.set_threshold(
                    product_id=pid,
                    stock_minimo=int(min_f.value or 10),
                    stock_maximo=int(max_f.value or 100),
                    reorder_point=int(rp_f.value or 20),
                    reorder_quantity=int(rq_f.value or 50),
                    alert_on_low_stock=low_switch.value,
                    alert_on_overstock=over_switch.value,
                )
                if ok:
                    dialog.open = False
                    self.page.update()
                    # Actualizar cache local
                    self._thresholds[pid] = {
                        "stock_minimo":       int(min_f.value), #type: ignore
                        "stock_maximo":       int(max_f.value), #type: ignore
                        "reorder_point":      int(rp_f.value), #type: ignore
                        "reorder_quantity":   int(rq_f.value), #type: ignore
                        "alert_on_low_stock": low_switch.value,
                        "alert_on_overstock": over_switch.value,
                    }
            except ValueError:
                self.app.show_snackbar("Ingresa valores numéricos válidos", error=True)

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.icons.TUNE_ROUNDED, color=AppTheme.ACCENT),
                 ft.Text(f"Umbral — {name}", weight=ft.FontWeight.BOLD)],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row([min_f, max_f], spacing=12),
                        ft.Container(height=8),
                        ft.Row([rp_f, rq_f], spacing=12),
                        ft.Container(height=12),
                        ft.Text("Configuración de alertas", size=12, color=c["text_secondary"]),
                        ft.Container(height=4),
                        low_switch,
                        over_switch,
                    ],
                    spacing=4,
                    tight=True,
                ),
                width=400,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Guardar umbral", color="white", weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_save,
                    ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open      = True
        self.page.update()

    def _show_kardex_dialog(self, item: dict):
        c            = self.colors
        product_name = item.get("product_name", "Producto")
        pid          = item.get("product_id", "")
        history      = self.ctrl.get_kardex(pid, limit=50)

        TIPO_ICON = {
            "salida":  (ft.icons.ARROW_DOWNWARD_ROUNDED, AppTheme.ERROR),
            "entrada": (ft.icons.ARROW_UPWARD_ROUNDED,   AppTheme.SUCCESS),
            "ajuste":  (ft.icons.SWAP_VERT_ROUNDED,       AppTheme.ACCENT),
            "inicio":  (ft.icons.PLAY_ARROW_ROUNDED,      AppTheme.BLUE),
        }

        if not history:
            rows_content = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.icons.HISTORY_TOGGLE_OFF_ROUNDED, size=40, color=c["text_secondary"]),
                        ft.Text("Sin movimientos registrados", color=c["text_secondary"]),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                alignment=ft.alignment.center,
                height=200,
            )
        else:
            kardex_rows = []
            for k in history:
                tipo     = k.get("tipo", "")
                cantidad = k.get("cantidad", 0)
                saldo_ant= k.get("saldo_anterior", 0)
                saldo_pos= k.get("saldo_posterior", 0)
                notas    = k.get("notas", "")
                fecha    = (k.get("created_at") or "")[:16].replace("T", " ")
                icon_i, icon_c = TIPO_ICON.get(tipo, (ft.icons.CIRCLE, c["text_secondary"]))

                kardex_rows.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(icon_i, size=16, color=icon_c),
                                ft.Column(
                                    [
                                        ft.Text(notas or tipo, size=11, color=c["text"],
                                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(fecha, size=10, color=c["text_secondary"]),
                                    ],
                                    spacing=1, tight=True, expand=True,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"{'+' if cantidad > 0 else ''}{cantidad}",
                                            size=12, weight=ft.FontWeight.BOLD,
                                            color=AppTheme.SUCCESS if cantidad > 0 else AppTheme.ERROR,
                                        ),
                                        ft.Text(
                                            f"{saldo_ant} → {saldo_pos}",
                                            size=10, color=c["text_secondary"],
                                        ),
                                    ],
                                    spacing=1, tight=True,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(horizontal=10, vertical=8),
                        border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
                    )
                )

            rows_content = ft.Container(
                content=ft.Column(kardex_rows, spacing=0, scroll=ft.ScrollMode.AUTO),
                height=360,
            )

        def close(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [ft.Icon(ft.icons.HISTORY_ROUNDED, color=AppTheme.BLUE),
                 ft.Text(f"Kardex — {product_name}", weight=ft.FontWeight.BOLD)],
                spacing=8,
            ),
            content=ft.Container(content=rows_content, width=440),
            actions=[
                ft.Container(
                    content=ft.Text("Cerrar", color="white", weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=close,
                    ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open      = True
        self.page.update()

    # ================================================================== #
    # HELPERS                                                            #
    # ================================================================== #

    def _refresh_inventory_inline(self):
        """Re-renderiza las filas sin navegar (más rápido que _refresh)."""
        self._render_inventory_rows()
        try:
            self.page.update()
        except Exception:
            pass

    def _refresh(self, e):
        self.app.navigate_to("inventory")