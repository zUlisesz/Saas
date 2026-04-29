# presentation/views/products_view.py
#
# PATCH sobre la versión Fase 5:
#
# FIX gen_btn siempre visible:
#   ANTES: visible=is_edit  → invisible en creación nueva
#   AHORA: visible=True     → siempre visible
#   Para nuevos productos usa uuid4() como seed → EAN-13 válido.

import threading
import flet as ft
import uuid as _uuid
from presentation.theme import AppTheme


class ProductsView:

    def __init__(self, page, colors, is_dark,
                 product_controller, category_controller, app):
        self.page            = page
        self.colors          = colors
        self.is_dark         = is_dark
        self.product_ctrl    = product_controller
        self.category_ctrl   = category_controller
        self.app             = app
        self._products:   list[dict] = []
        self._categories: list[dict] = []
        self._filter_timer: threading.Timer | None = None
        self._table_rows = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

    def build(self):
        self._products   = self.product_ctrl.get_products()
        self._categories = self.category_ctrl.get_categories()
        self._render_rows()

        search = AppTheme.make_text_field("Buscar producto...", colors=self.colors)
        search.expand = True
        search.prefix_icon = ft.icons.SEARCH_ROUNDED
        search.on_change = lambda e: self._filter(e.control.value)

        add_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.icons.ADD_ROUNDED, color="white", size=18),
                 ft.Text("Nuevo Producto", color="white", weight=ft.FontWeight.W_600)],
                spacing=6, tight=True,
            ),
            gradient=AppTheme.gradient_primary(),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=18, vertical=11),
            on_click=lambda e: self._show_form_dialog(),
            ink=True,
        )

        pending = self.product_ctrl.get_pending_products()
        bulk_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.icons.QR_CODE_ROUNDED, color="white", size=16),
                 ft.Text(f"Asignar {len(pending)} códigos", color="white", size=12,
                         weight=ft.FontWeight.W_600)],
                spacing=6, tight=True,
            ),
            gradient=AppTheme.gradient_warning(),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=14, vertical=9),
            on_click=lambda e: self._on_bulk_barcode(),
            ink=True,
            visible=len(pending) > 0,
        )

        header = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Productos", size=22, weight=ft.FontWeight.BOLD,
                                color=self.colors["text"]),
                        ft.Text(f"{len(self._products)} productos registrados",
                                size=13, color=self.colors["text_secondary"]),
                    ], spacing=2, tight=True, expand=True,
                ),
                bulk_btn,
                add_btn,
            ],
        )

        col_header = ft.Container(
            content=ft.Row(
                [
                    ft.Text("Nombre",    size=12, color=self.colors["text_secondary"],
                            weight=ft.FontWeight.W_600, expand=3),
                    ft.Text("Categoría", size=12, color=self.colors["text_secondary"],
                            weight=ft.FontWeight.W_600, expand=2),
                    ft.Text("Precio",    size=12, color=self.colors["text_secondary"],
                            weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Costo",     size=12, color=self.colors["text_secondary"],
                            weight=ft.FontWeight.W_600, expand=1),
                    ft.Text("Acciones",  size=12, color=self.colors["text_secondary"],
                            weight=ft.FontWeight.W_600, width=100),
                ],
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            bgcolor=self.colors["surface"],
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
        )

        table_container = ft.Container(
            content=ft.Column(
                [col_header,
                 ft.Container(height=1, bgcolor=self.colors["border"]),
                 self._table_rows],
                spacing=0, expand=True,
            ),
            bgcolor=self.colors["card"],
            border_radius=12,
            border=ft.border.all(1, self.colors["border"]),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        return ft.Container(
            content=ft.Column(
                [header, ft.Container(height=8), search,
                 ft.Container(height=12), table_container],
                spacing=8, expand=True,
            ),
            expand=True,
            padding=ft.padding.all(28),
            bgcolor=self.colors["bg"],
        )

    def _render_rows(self, products=None):
        c    = self.colors
        data = products if products is not None else self._products
        self._table_rows.controls.clear()

        if not data:
            self._table_rows.controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.Icon(ft.icons.INVENTORY_2_ROUNDED,
                                 color=c["text_secondary"], size=48),
                         ft.Text("Sin productos", color=c["text_secondary"])],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                    ),
                    alignment=ft.alignment.center, height=160,
                )
            )
            return

        for p in data:
            name     = p.get("name", "")
            price    = float(p.get("price") or 0)
            cost     = float(p.get("cost") or 0)
            category = (p.get("categories") or {}).get("name", "—")
            barcode  = p.get("barcode") or ""

            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Icon(
                                        ft.icons.QR_CODE_ROUNDED if barcode
                                        else ft.icons.INVENTORY_2_ROUNDED,
                                        color=AppTheme.ACCENT, size=16,
                                    ),
                                    width=32, height=32, border_radius=8,
                                    bgcolor=f"{AppTheme.ACCENT}18",
                                    alignment=ft.alignment.center,
                                ),
                                ft.Text(name, size=13, color=c["text"],
                                        weight=ft.FontWeight.W_500, expand=True,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                            ],
                            expand=3, spacing=10,
                        ),
                        ft.Container(
                            content=ft.Text(category, size=12, color="white"),
                            bgcolor=f"{AppTheme.ACCENT}80", border_radius=20,
                            padding=ft.padding.symmetric(horizontal=10, vertical=3),
                            expand=2,
                        ),
                        ft.Text(f"${price:,.2f}", size=13, color=c["text"],
                                weight=ft.FontWeight.W_600, expand=1),
                        ft.Text(f"${cost:,.2f}", size=12,
                                color=c["text_secondary"], expand=1),
                        ft.Row(
                            [
                                ft.IconButton(
                                    ft.icons.EDIT_ROUNDED, icon_size=16,
                                    icon_color=AppTheme.ACCENT, tooltip="Editar",
                                    on_click=lambda e, prod=p: self._show_form_dialog(prod),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ),
                                ft.IconButton(
                                    ft.icons.DELETE_ROUNDED, icon_size=16,
                                    icon_color=AppTheme.ERROR, tooltip="Eliminar",
                                    on_click=lambda e, pid=p["id"]: self._confirm_delete(pid),
                                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                                ),
                            ],
                            spacing=0, width=100,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                bgcolor="transparent",
                border=ft.border.only(bottom=ft.border.BorderSide(1, c["divider"])),
            )
            self._table_rows.controls.append(row)

        self.page.update()

    def _filter(self, query: str):
        if self._filter_timer:
            self._filter_timer.cancel()
        self._filter_timer = threading.Timer(0.25, self._do_filter, args=[query])
        self._filter_timer.daemon = True
        self._filter_timer.start()

    def _do_filter(self, query: str):
        q = (query or "").lower().strip()
        filtered = (
            [p for p in self._products
             if q in p.get("name", "").lower()
             or q in (p.get("barcode") or "").lower()
             or q in (p.get("sku") or "").lower()]
            if q else list(self._products)
        )
        self._render_rows(filtered)

    # ================================================================== #
    # FORMULARIO                                                          #
    # ================================================================== #

    def _show_form_dialog(self, product: dict | None = None):
        c       = self.colors
        is_edit = product is not None

        name_f = AppTheme.make_text_field(
            "Nombre *", colors=c,
            value=product.get("name", "") if is_edit else "",
        )
        price_f = AppTheme.make_text_field(
            "Precio de venta *", colors=c,
            value=str(product.get("price", "")) if is_edit else "",
        )
        price_f.keyboard_type = ft.KeyboardType.NUMBER

        cost_f = AppTheme.make_text_field(
            "Costo", colors=c,
            value=str(product.get("cost", "")) if is_edit else "",
        )
        cost_f.keyboard_type = ft.KeyboardType.NUMBER

        sku_f = AppTheme.make_text_field(
            "SKU", colors=c,
            value=product.get("sku", "") if is_edit else "",
        )

        # Categoría
        cat_options = [ft.dropdown.Option(key="", text="Sin categoría")]
        for cat in self._categories:
            cat_options.append(ft.dropdown.Option(key=cat["id"], text=cat["name"]))

        cat_dd = ft.Dropdown(
            options=cat_options,
            value=(product.get("category_id") or "") if is_edit else "",
            border_radius=12,
            border_color=c["border"],
            focused_border_color=AppTheme.ACCENT,
            label="Categoría",
            label_style=ft.TextStyle(color=c["text_secondary"], size=13),
            text_style=ft.TextStyle(color=c["text"]),
            bgcolor=c["input_fill"],
        )

        # Barcode
        barcode_f = AppTheme.make_text_field(
            "Código de barras", colors=c,
            value=product.get("barcode", "") if is_edit else "",
        )
        barcode_f.expand = True

        barcode_type_dd = ft.Dropdown(
            options=[
                ft.dropdown.Option("ean13",   "EAN-13"),
                ft.dropdown.Option("ean8",    "EAN-8"),
                ft.dropdown.Option("upc",     "UPC-A"),
                ft.dropdown.Option("code128", "Code 128"),
            ],
            value=(product.get("barcode_type") or "ean13") if is_edit else "ean13",
            width=130,
            border_radius=10,
            border_color=c["border"],
            focused_border_color=AppTheme.ACCENT,
            bgcolor=c["input_fill"],
            text_style=ft.TextStyle(color=c["text"]),
        )

        # ── Botón generar — SIEMPRE visible (FIX) ───────────────────
        def on_generate_barcode(e):
            # Usar product_id si existe (edición) o uuid4 como seed (creación)
            seed_id = product["id"] if (is_edit and product) else str(_uuid.uuid4())
            code = self.product_ctrl.generate_barcode(
                seed_id, barcode_type_dd.value or "ean13",
            )
            if code:
                barcode_f.value = code
                barcode_f.update()

        gen_btn = ft.IconButton(
            ft.icons.AUTO_AWESOME_ROUNDED,
            icon_color=AppTheme.ACCENT,
            tooltip="Generar código automático",
            on_click=on_generate_barcode,
            visible=True,   # FIX: era visible=is_edit
        )

        # ── Inventario inicial (solo creación) ───────────────────────
        stock_inicial_f = AppTheme.make_text_field(
            "Stock inicial", colors=c, value="0",
        )
        stock_inicial_f.keyboard_type = ft.KeyboardType.NUMBER
        stock_inicial_f.suffix_text   = "uds."
        stock_inicial_f.helper_text   = "Unidades disponibles ahora"

        stock_minimo_f = AppTheme.make_text_field(
            "Stock mínimo (alerta)", colors=c, value="5",
        )
        stock_minimo_f.keyboard_type = ft.KeyboardType.NUMBER
        stock_minimo_f.suffix_text   = "uds."
        stock_minimo_f.helper_text   = "Nivel para generar alerta"

        inventory_section = ft.Container(
            visible=not is_edit,
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.icons.WAREHOUSE_ROUNDED,
                                        size=14, color=AppTheme.ACCENT),
                                ft.Text("Inventario inicial", size=13,
                                        color=c["text"], weight=ft.FontWeight.W_600),
                            ],
                            spacing=6,
                        ),
                        padding=ft.padding.only(top=10, bottom=2),
                    ),
                    ft.Row([stock_inicial_f, stock_minimo_f], spacing=12),
                ],
                spacing=4,
            ),
        )

        # ── Save ────────────────────────────────────────────────────
        def on_save(e):
            data = {
                "name":         name_f.value or "",
                "price":        price_f.value or "0",
                "cost":         cost_f.value or "0",
                "sku":          sku_f.value or "",
                "category_id":  cat_dd.value or None,
                "barcode":      barcode_f.value or None,
                "barcode_type": barcode_type_dd.value or "ean13",
            }

            if not is_edit:
                try:
                    data["stock_inicial"] = int(stock_inicial_f.value or 0)
                    data["stock_minimo"]  = int(stock_minimo_f.value or 5)
                except ValueError:
                    self.app.show_snackbar(
                        "Stock inicial y mínimo deben ser números enteros",
                        error=True,
                    )
                    return

            if is_edit and product:
                ok = self.product_ctrl.update_product(product["id"], data)
            else:
                ok = self.product_ctrl.create_product(data)

            if ok:
                dialog.open = False
                self.page.update()
                self._products = self.product_ctrl.get_products()
                self._render_rows()

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(
                        ft.icons.EDIT_ROUNDED if is_edit
                        else ft.icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                        color=AppTheme.ACCENT,
                    ),
                    ft.Text(
                        "Editar Producto" if is_edit else "Nuevo Producto",
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        name_f,
                        ft.Container(height=6),
                        ft.Row([price_f, cost_f], spacing=12),
                        ft.Container(height=6),
                        ft.Row([sku_f, cat_dd], spacing=12),
                        ft.Container(height=6),
                        ft.Row(
                            [barcode_f, barcode_type_dd, gen_btn],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        inventory_section,
                    ],
                    spacing=4,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=460,
                padding=ft.padding.only(top=4),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text(
                        "Guardar" if is_edit else "Crear producto",
                        color="white", weight=ft.FontWeight.W_600,
                    ),
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

    def _confirm_delete(self, product_id: str):
        c = self.colors

        def do_delete(e):
            self.product_ctrl.delete_product(product_id)
            dialog.open = False
            self.page.update()
            self._products = self.product_ctrl.get_products()
            self._render_rows()

        def cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("¿Eliminar producto?", weight=ft.FontWeight.BOLD),
            content=ft.Text("Esta acción no se puede deshacer."),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel),
                ft.Container(
                    content=ft.Text("Eliminar", color="white",
                                    weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_error(),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=do_delete, ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open      = True
        self.page.update()

    def _on_bulk_barcode(self):
        self.product_ctrl.assign_barcodes_bulk()
        self._products = self.product_ctrl.get_products()
        self._render_rows()

    def _refresh(self, e):
        self.app.navigate_to("products")