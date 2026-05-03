# presentation/views/pos_view.py
#
# CAMBIOS (Fase 4 — Código de Barras + Fase 6 — Recargas):
#
# FASE 4:
#   1. Se añade un campo de búsqueda por barcode (además de la búsqueda textual).
#      En el POS real, un lector USB actúa como teclado: el cajero escanea y
#      el campo recibe el código automáticamente. Al presionar Enter se busca.
#   2. find_by_barcode() integrado en _on_barcode_scan():
#      • Si encuentra el producto → lo añade al carrito con feedback visual
#      • Si no encuentra → muestra snackbar de error
#   3. ProductsView ahora muestra el campo barcode al crear/editar.
#
# FASE 6:
#   1. PosView tiene dos tabs: "Venta" (flujo normal) y "Recargas".
#   2. La tab de Recargas tiene: Dropdown operadora → chips de monto → campo teléfono
#   3. El botón "Recargar" llama a recharge_controller.process_recharge().
#   4. Si ticket_service está disponible, genera un "comprobante" de recarga.
#
# PRINCIPIO: pos_view recibe los controllers inyectados.
# Nunca instancia servicios ni repositorios directamente.

import threading
import flet as ft
from presentation.theme import AppTheme


class PosView:

    def __init__(self, page, colors, is_dark,
                 sale_controller, product_controller,
                 ticket_service=None, app=None,
                 recharge_controller=None):       # NUEVO Fase 6
        self.page                = page
        self.colors              = colors
        self.is_dark             = is_dark
        self.sale_controller     = sale_controller
        self.product_controller  = product_controller
        self.ticket_service      = ticket_service
        self.app                 = app
        self.recharge_ctrl       = recharge_controller  # NUEVO Fase 6

        self.cart:              list[dict] = []
        self.all_products:      list[dict] = []
        self.filtered_products: list[dict] = []

        self._search_timer:    threading.Timer | None = None
        self._cart_item_refs:  dict = {}  # pid -> {"qty": ft.Text, "sub": ft.Text}
        self._recharge_history_col = ft.Column(spacing=4)  # Fase 6

        self._cart_col       = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, expand=True)
        self._total_text     = ft.Text("$0.00", size=26, weight=ft.FontWeight.BOLD, color="white")
        self._subtotal_text  = ft.Text("Subtotal: $0.00", size=13)
        self._item_count_text= ft.Text("0 ítems", size=12)
        self._product_grid   = ft.GridView(
            expand=True, runs_count=3, max_extent=170, spacing=10, run_spacing=10,
        )
        self._search_field   = AppTheme.make_text_field(
            "Buscar producto...", colors=colors, width=None
        )
        self._search_field.expand = True

        # NUEVO Fase 4: campo de barcode separado
        self._barcode_field = AppTheme.make_text_field(
            "Escanear código de barras", colors=colors, width=None
        )
        self._barcode_field.expand = True
        self._barcode_field.prefix_icon = ft.icons.QR_CODE_SCANNER_ROUNDED

    # ─────────────────────────────────────────────────────────────
    def build(self):
        self._load_products()
        self._search_field.on_change   = self._on_search
        self._search_field.prefix_icon = ft.icons.SEARCH_ROUNDED

        # NUEVO Fase 4: el barcode se dispara al presionar Enter (simulando scanner)
        self._barcode_field.on_submit = self._on_barcode_scan

        # NUEVO Fase 6: construir la pestaña de recargas
        has_recharge = self.recharge_ctrl is not None

        left_content = self._build_left_content(has_recharge)

        return ft.Row(
            [
                left_content,
                ft.Container(width=1, bgcolor=self.colors["border"]),
                self._build_cart_panel(),
            ],
            expand=True, spacing=0,
        )

    # ─────────────────────────────────────────────────────────────
    # Contenido izquierdo — con tabs si hay recargas
    # ─────────────────────────────────────────────────────────────
    def _build_left_content(self, has_recharge: bool):
        c = self.colors

        venta_tab = ft.Column(
            [
                ft.Text("Productos", size=16, weight=ft.FontWeight.BOLD, color=c["text"]),
                ft.Container(height=8),
                # NUEVO Fase 4: fila con búsqueda texto + barcode
                ft.Row([self._search_field, self._barcode_field], spacing=10),
                ft.Container(height=10),
                self._product_grid,
            ],
            expand=True,
        )

        if not has_recharge:
            return ft.Container(
                content=venta_tab,
                expand=True,
                padding=ft.padding.all(20),
                bgcolor=c["bg"],
            )

        # NUEVO Fase 6: Tabs Venta / Recargas
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(
                    text="Venta",
                    icon=ft.icons.SHOPPING_CART_ROUNDED,
                    content=ft.Container(
                        content=venta_tab,
                        padding=ft.padding.only(top=16),
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Recargas",
                    icon=ft.icons.PHONE_ANDROID_ROUNDED,
                    content=ft.Container(
                        content=self._build_recharge_tab(),
                        padding=ft.padding.only(top=16),
                        expand=True,
                    ),
                ),
            ],
            expand=True,
        )

        return ft.Container(
            content=tabs, expand=True,
            padding=ft.padding.all(20),
            bgcolor=c["bg"],
        )

    # ─────────────────────────────────────────────────────────────
    # NUEVO Fase 6 — Tab de recargas
    # ─────────────────────────────────────────────────────────────
    def _build_recharge_tab(self):
        c         = self.colors
        operators = self.recharge_ctrl.get_operators() if self.recharge_ctrl else []

        # Estado local de la tab (refs mutables)
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
                self.app.show_snackbar("Selecciona una operadora", error=True)  # type: ignore
                return
            if not amount:
                self.app.show_snackbar("Selecciona un monto", error=True)  # type: ignore
                return
            if not phone:
                self.app.show_snackbar("Ingresa el número de teléfono", error=True)  # type: ignore
                return
            if not self.recharge_ctrl.is_valid_phone(phone):
                self.app.show_snackbar("Número inválido: debe tener 8-12 dígitos", error=True)  # type: ignore
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

        # Carga inicial del historial en background — evita bloquear el hilo de UI
        # y previene conflictos de conexión con operaciones Supabase en curso.
        if self.recharge_ctrl:
            threading.Thread(target=self._async_load_recharge_history, daemon=True).start()

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
    # NUEVO Fase 6 — Diálogo de confirmación de recarga
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
    # NUEVO Fase 6 — Historial de recargas
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

    # ─────────────────────────────────────────────────────────────
    # NUEVO Fase 4 — Barcode scan
    # ─────────────────────────────────────────────────────────────
    def _on_barcode_scan(self, e):
        """
        Se dispara cuando el cajero presiona Enter en el campo de barcode.
        Compatible con lectores USB (actúan como teclado y terminan con Enter).
        """
        barcode = (self._barcode_field.value or "").strip()
        if not barcode:
            return

        product = self.product_controller.find_by_barcode(barcode)
        if product:
            self._add_to_cart(product)
            self.app.show_snackbar(f"✓ {product.get('name', '')} agregado al carrito")# type: ignore
        else:
            self.app.show_snackbar(f"Código '{barcode}' no encontrado", error=True) #type: ignore

        # Limpiar y re-enfocar para escaneo continuo
        self._barcode_field.value = ""
        self._barcode_field.focus()
        self.page.update()

    # ─────────────────────────────────────────────────────────────
    # Products
    # ─────────────────────────────────────────────────────────────
    def _load_products(self):
        self._product_grid.controls.clear()
        self._product_grid.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.ProgressRing(width=24, height=24, stroke_width=2,
                                    color=AppTheme.ACCENT),
                    ft.Text("Cargando productos...", size=12,
                            color=self.colors["text_secondary"]),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                alignment=ft.alignment.center, expand=True,
            )
        )
        self.page.update()

        def fetch():
            products = self.product_controller.get_products()
            self.all_products      = products
            self.filtered_products = list(products)
            self._render_products()

        threading.Thread(target=fetch, daemon=True).start()

    def _on_search(self, e):
        if self._search_timer:
            self._search_timer.cancel()
        value = e.control.value
        self._search_timer = threading.Timer(0.25, self._do_search, args=[value])
        self._search_timer.daemon = True
        self._search_timer.start()

    def _do_search(self, value: str):
        q = (value or "").lower().strip()
        self.filtered_products = (
            [p for p in self.all_products
             if q in p.get("name", "").lower()
             or q in (p.get("barcode") or "").lower()]
            if q else list(self.all_products)
        )
        self._render_products()

    def _render_products(self):
        self._product_grid.controls.clear()
        for p in self.filtered_products:
            self._product_grid.controls.append(self._product_card(p))
        self.page.update()

    def _product_card(self, product: dict):
        c        = self.colors
        name     = product.get("name", "")
        price    = float(product.get("price", 0))
        category = (product.get("categories") or {}).get("name", "")
        barcode  = product.get("barcode") or ""

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(ft.icons.INVENTORY_2_ROUNDED,
                                        color=AppTheme.ACCENT, size=28),
                        width=48, height=48, border_radius=12,
                        bgcolor=f"{AppTheme.ACCENT}18", alignment=ft.alignment.center,
                    ),
                    ft.Text(name, size=13, weight=ft.FontWeight.W_500, color=c["text"],
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(category, size=11, color=c["text_secondary"],
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(f"${price:,.2f}", size=15, weight=ft.FontWeight.BOLD,
                            color=AppTheme.ACCENT, text_align=ft.TextAlign.CENTER),
                    # NUEVO Fase 4: badge de barcode o aviso PENDING
                    ft.Container(
                        content=ft.Text(
                            "Sin código", size=9, color=AppTheme.ERROR,
                            weight=ft.FontWeight.W_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        bgcolor=f"{AppTheme.ERROR}20",
                        border_radius=6,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    ) if (not barcode or barcode.startswith("PENDING-")) else ft.Text(
                        barcode[:13], size=9, color=c["text_secondary"],
                        font_family="monospace", text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER, spacing=5,
            ),
            bgcolor=c["card"], border_radius=14,
            border=ft.border.all(1, c["border"]),
            padding=ft.padding.all(12),
            on_click=lambda e, prod=product: self._add_to_cart(prod),
            ink=True, alignment=ft.alignment.center,
        )

    # ─────────────────────────────────────────────────────────────
    # Cart
    # ─────────────────────────────────────────────────────────────
    def _build_cart_panel(self):
        c = self.colors

        checkout_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.icons.SHOPPING_CART_CHECKOUT_ROUNDED, color="white", size=20),
                    ft.Column([
                        ft.Text("Cobrar", color="white", size=14,
                                weight=ft.FontWeight.W_600),
                        self._total_text,
                    ], spacing=0, tight=True),
                ],
                alignment=ft.MainAxisAlignment.CENTER, spacing=12,
            ),
            gradient=AppTheme.gradient_primary(),
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            on_click=self._show_checkout_dialog,
            ink=True,
        )

        clear_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.icons.DELETE_SWEEP_ROUNDED, color=AppTheme.ERROR, size=16),
                 ft.Text("Vaciar", color=AppTheme.ERROR, size=13)],
                spacing=6, tight=True,
            ),
            on_click=self._clear_cart, ink=True, border_radius=8,
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
        )

        header = ft.Row([
            ft.Column([
                ft.Text("Carrito", size=16, weight=ft.FontWeight.BOLD, color=c["text"]),
                self._item_count_text,
            ], spacing=2, tight=True, expand=True),
            clear_btn,
        ])

        return ft.Container(
            content=ft.Column([
                ft.Container(content=header,
                             padding=ft.padding.symmetric(horizontal=20, vertical=16)),
                ft.Container(height=1, bgcolor=c["border"]),
                ft.Container(content=self._cart_col, expand=True,
                             padding=ft.padding.symmetric(horizontal=12, vertical=12)),
                ft.Container(height=1, bgcolor=c["border"]),
                ft.Container(
                    content=ft.Column([self._subtotal_text,
                                       ft.Container(height=8), checkout_btn]),
                    padding=ft.padding.all(16),
                ),
            ], expand=True, spacing=0),
            width=300, bgcolor=c["card"],
        )

    def _add_to_cart(self, product: dict):
        pid = product["id"]
        for item in self.cart:
            if item["id"] == pid:
                item["quantity"] += 1
                item["subtotal"] = item["quantity"] * item["price"]
                self._refresh_cart()
                return
        self.cart.append({
            "id":       pid,
            "name":     product.get("name", ""),
            "price":    float(product.get("price", 0)),
            "quantity": 1,
            "subtotal": float(product.get("price", 0)),
        })
        self._refresh_cart()

    def _remove_from_cart(self, product_id: str):
        self.cart = [i for i in self.cart if i["id"] != product_id]
        self._refresh_cart()

    def _update_quantity(self, product_id: str, delta: int):
        for item in self.cart:
            if item["id"] == product_id:
                item["quantity"] = max(1, item["quantity"] + delta)
                item["subtotal"] = item["quantity"] * item["price"]
                refs = self._cart_item_refs.get(product_id)
                if refs:
                    refs["qty"].value = str(item["quantity"])
                    refs["sub"].value = f"${item['subtotal']:,.2f}"
                break
        self._update_totals()

    def _update_totals(self):
        total = sum(i["subtotal"] for i in self.cart)
        count = sum(i["quantity"] for i in self.cart)
        self._total_text.value      = f"${total:,.2f}"
        self._subtotal_text.value   = f"Subtotal: ${total:,.2f}"
        self._item_count_text.value = f"{count} ítem{'s' if count != 1 else ''}"
        self.page.update()

    def _clear_cart(self, e=None):
        self.cart.clear()
        self._refresh_cart()

    def _refresh_cart(self):
        c = self.colors
        self._cart_item_refs.clear()
        self._cart_col.controls.clear()

        if not self.cart:
            self._cart_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SHOPPING_CART_ROUNDED,
                                color=c["text_secondary"], size=40),
                        ft.Text("El carrito está vacío",
                                color=c["text_secondary"], size=13),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.alignment.center, expand=True,
                    padding=ft.padding.symmetric(vertical=40),
                )
            )
        else:
            for item in self.cart:
                self._cart_col.controls.append(self._cart_item_row(item))

        total = sum(i["subtotal"] for i in self.cart)
        count = sum(i["quantity"] for i in self.cart)
        self._total_text.value      = f"${total:,.2f}"
        self._subtotal_text.value   = f"Subtotal: ${total:,.2f}"
        self._item_count_text.value = f"{count} ítem{'s' if count != 1 else ''}"
        self._subtotal_text.color   = c["text_secondary"]
        self.page.update()

    def _cart_item_row(self, item: dict):
        c        = self.colors
        qty_text = ft.Text(str(item["quantity"]), size=13, weight=ft.FontWeight.BOLD,
                           color=c["text"], width=20, text_align=ft.TextAlign.CENTER)
        sub_text = ft.Text(f"${item['subtotal']:,.2f}", size=13,
                           weight=ft.FontWeight.BOLD, color=AppTheme.ACCENT)
        self._cart_item_refs[item["id"]] = {"qty": qty_text, "sub": sub_text}

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(item["name"], size=13, weight=ft.FontWeight.W_500,
                            color=c["text"], max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS, width=100),
                    ft.Text(f"${item['price']:,.2f} c/u", size=11,
                            color=c["text_secondary"]),
                ], spacing=2, tight=True, expand=True),
                ft.Row([
                    ft.IconButton(
                        ft.icons.REMOVE_ROUNDED, icon_size=14,
                        on_click=lambda e, pid=item["id"]: self._update_quantity(pid, -1),
                        icon_color=c["text_secondary"],
                        style=ft.ButtonStyle(padding=ft.padding.all(4)),
                    ),
                    qty_text,
                    ft.IconButton(
                        ft.icons.ADD_ROUNDED, icon_size=14,
                        on_click=lambda e, pid=item["id"]: self._update_quantity(pid, 1),
                        icon_color=AppTheme.ACCENT,
                        style=ft.ButtonStyle(padding=ft.padding.all(4)),
                    ),
                ], spacing=0, tight=True),
                ft.Column([
                    sub_text,
                    ft.IconButton(
                        ft.icons.CLOSE_ROUNDED, icon_size=14,
                        on_click=lambda e, pid=item["id"]: self._remove_from_cart(pid),
                        icon_color=AppTheme.ERROR,
                        style=ft.ButtonStyle(padding=ft.padding.all(2)),
                    ),
                ], spacing=0, tight=True,
                   horizontal_alignment=ft.CrossAxisAlignment.END),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=c["surface"] if self.is_dark else c["bg"],
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, c["border"]),
        )

    # ─────────────────────────────────────────────────────────────
    # Checkout
    # ─────────────────────────────────────────────────────────────
    def _show_checkout_dialog(self, e):
        if not self.cart:
            self.app.show_snackbar("El carrito está vacío", error=True)
            return

        c            = self.colors
        total        = sum(i["subtotal"] for i in self.cart)
        method_ref   = ft.Ref[ft.RadioGroup]()
        amount_field = AppTheme.make_text_field("Monto recibido", f"{total:.2f}", colors=c)
        change_text  = ft.Text("Cambio: $0.00", size=14, color=AppTheme.SUCCESS,
                               weight=ft.FontWeight.W_600)

        def on_amount_change(ev):
            try:
                received = float(amount_field.value or 0)
                change   = received - total
                change_text.value = f"Cambio: ${max(0, change):,.2f}"
                change_text.color = AppTheme.SUCCESS if change >= 0 else AppTheme.ERROR
            except ValueError:
                change_text.value = "Cambio: $0.00"
            change_text.update()

        amount_field.on_change = on_amount_change

        def on_confirm(ev):
            method   = method_ref.current.value or "cash"
            received = float(amount_field.value or 0)
            dialog.open = False
            self.page.update()

            cart_snapshot = list(self.cart)
            result = self.sale_controller.create_sale(self.cart, method, received)
            if result:
                self.cart.clear()
                self._refresh_cart()
                self._show_receipt(result, method, cart_snapshot)

        def on_cancel(ev):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.icons.PAYMENT_ROUNDED, color=AppTheme.ACCENT),
                ft.Text("Procesar Pago", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Total a cobrar", size=13, color=c["text_secondary"]),
                            ft.Text(f"${total:,.2f}", size=32,
                                    weight=ft.FontWeight.BOLD, color=AppTheme.ACCENT),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        alignment=ft.alignment.center,
                        padding=ft.padding.symmetric(vertical=16),
                    ),
                    ft.Text("Método de pago", size=13, color=c["text_secondary"]),
                    ft.RadioGroup(
                        ref=method_ref, value="cash",
                        content=ft.Row([
                            ft.Radio(value="cash",     label="Efectivo"),
                            ft.Radio(value="card",     label="Tarjeta"),
                            ft.Radio(value="transfer", label="Transferencia"),
                        ], spacing=12),
                    ),
                    ft.Container(height=8),
                    amount_field,
                    ft.Container(height=8),
                    change_text,
                ], spacing=8, tight=True),
                width=340,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Confirmar Pago", color="white",
                                    weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_primary(), border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=on_confirm, ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _show_receipt(self, result: dict, method: str, cart_snapshot: list):
        sale          = result["sale"]
        total         = result["total"]
        change        = result.get("change", 0)
        method_labels = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia"}
        method_label  = method_labels.get(method, method)

        ticket_info_text = None
        if self.ticket_service:
            try:
                ticket_data = self.ticket_service.generate({
                    "items": [{"name": i.get("name", ""), "qty": i.get("quantity", 1),
                               "price": i.get("price", 0)} for i in cart_snapshot],
                    "total": total, "payment_method": method,
                    "sale_id": sale.get("id"),
                })
                pdf_path = self.ticket_service.export_pdf(ticket_data)
                ticket_info_text = ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.PICTURE_AS_PDF_ROUNDED,
                                color=AppTheme.ERROR, size=16),
                        ft.Column([
                            ft.Text(f"Folio: {ticket_data['folio']}", size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=self.colors["text"]),
                            ft.Text(pdf_path, size=10,
                                    color=self.colors["text_secondary"],
                                    overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                        ], spacing=2, tight=True, expand=True),
                    ], spacing=8),
                    bgcolor=f"{AppTheme.ERROR}15", border_radius=8,
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                )
            except Exception as ex:
                ticket_info_text = ft.Text(f"PDF no generado: {ex}",
                                           size=11, color=AppTheme.WARNING)

        items_col = ft.Column([
            ft.Row([
                ft.Text(item["name"], size=13, expand=True),
                ft.Text(f"{item['quantity']}x", size=12, color="#8B8FA8"),
                ft.Text(f"${item['subtotal']:,.2f}", size=13,
                        weight=ft.FontWeight.W_600),
            ]) for item in cart_snapshot
        ], spacing=6)

        def close(e):
            dialog.open = False
            self.page.update()

        content = [
            items_col, ft.Divider(),
            ft.Row([ft.Text("Método:", size=13),
                    ft.Text(method_label, size=13, weight=ft.FontWeight.W_600)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Total:", size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(f"${total:,.2f}", size=14, weight=ft.FontWeight.BOLD,
                            color=AppTheme.ACCENT)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([ft.Text("Cambio:", size=13),
                    ft.Text(f"${change:,.2f}", size=13, weight=ft.FontWeight.W_600,
                            color=AppTheme.SUCCESS)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]
        if ticket_info_text:
            content += [ft.Container(height=8), ticket_info_text]

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.icons.CHECK_CIRCLE_ROUNDED, color=AppTheme.SUCCESS),
                ft.Text("Ticket de Venta", weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column(content, spacing=8, tight=True),
                width=340,
            ),
            actions=[ft.Container(
                content=ft.Text("Nueva venta", color="white",
                                weight=ft.FontWeight.W_600),
                gradient=AppTheme.gradient_success(), border_radius=8,
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
                on_click=close, ink=True,
            )],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        self.page.dialog = dialog
        dialog.open      = True
        self.page.update()