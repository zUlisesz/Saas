# presentation/views/categories_view.py

import flet as ft
from presentation.theme import AppTheme


class CategoriesView:

    def __init__(self, page, colors, is_dark, category_controller, app):
        self.page = page
        self.colors = colors
        self.is_dark = is_dark
        self.ctrl = category_controller
        self.app = app
        self._categories: list[dict] = []
        self._grid = ft.GridView(runs_count=4, max_extent=200, spacing=12, run_spacing=12, expand=True)

    def build(self):
        self._categories = self.ctrl.get_categories()
        self._render_grid()

        add_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.icons.ADD_ROUNDED, color="white", size=18),
                 ft.Text("Nueva Categoría", color="white", weight=ft.FontWeight.W_600)],
                spacing=6, tight=True,
            ),
            gradient=AppTheme.gradient_primary(),
            border_radius=12,
            padding=ft.padding.symmetric(horizontal=18, vertical=11),
            on_click=lambda e: self._show_form_dialog(),
            ink=True,
        )

        return ft.Container(
            content=ft.Column(
                [
                    AppTheme.page_header(
                        "Categorías",
                        f"{len(self._categories)} categorías registradas",
                        self.colors,
                        action=add_btn,
                    ),
                    ft.Container(height=24),
                    self._grid,
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.padding.all(28),
            bgcolor=self.colors["bg"],
        )

    def _render_grid(self):
        c = self.colors
        self._grid.controls.clear()

        GRADIENTS = [
            AppTheme.gradient_primary(),
            AppTheme.gradient_success(),
            AppTheme.gradient_warning(),
            AppTheme.gradient_info(),
            AppTheme.gradient_error(),
        ]

        if not self._categories:
            self._grid.controls.append(
                ft.Container(
                    content=ft.Column(
                        [ft.Icon(ft.icons.CATEGORY_ROUNDED, color=c["text_secondary"], size=48),
                         ft.Text("Sin categorías", color=c["text_secondary"])],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                    ),
                    alignment=ft.alignment.center,
                )
            )
        else:
            for idx, cat in enumerate(self._categories):
                grad = GRADIENTS[idx % len(GRADIENTS)]
                self._grid.controls.append(self._category_card(cat, grad))

        self.page.update()

    def _category_card(self, cat: dict, gradient):
        c = self.colors
        name = cat.get("name", "")
        initial = name[0].upper() if name else "?"

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(initial, color="white", size=24, weight=ft.FontWeight.BOLD),
                        width=56, height=56,
                        border_radius=16,
                        gradient=gradient,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text(name, size=14, color=c["text"], weight=ft.FontWeight.W_600,
                            text_align=ft.TextAlign.CENTER, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(
                        [
                            ft.IconButton(
                                ft.icons.EDIT_ROUNDED, icon_size=15, icon_color=AppTheme.ACCENT,
                                tooltip="Editar",
                                on_click=lambda e, c=cat: self._show_form_dialog(c),
                                style=ft.ButtonStyle(padding=ft.padding.all(4)),
                            ),
                            ft.IconButton(
                                ft.icons.DELETE_ROUNDED, icon_size=15, icon_color=AppTheme.ERROR,
                                tooltip="Eliminar",
                                on_click=lambda e, cid=cat["id"]: self._confirm_delete(cid),
                                style=ft.ButtonStyle(padding=ft.padding.all(4)),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER, spacing=4,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor=c["card"],
            border_radius=16,
            border=ft.border.all(1, c["border"]),
            padding=ft.padding.all(16),
            alignment=ft.alignment.center,
        )

    def _show_form_dialog(self, category: dict | None = None):
        c = self.colors
        is_edit = category is not None
        name_f = AppTheme.make_text_field(
            "Nombre de categoría *", colors=c,
            value=category.get("name", "") if is_edit else "",
        )

        def on_save(e):
            if is_edit:
                ok = self.ctrl.update_category(category["id"], name_f.value or "")
            else:
                ok = self.ctrl.create_category(name_f.value or "")
            if ok:
                dialog.open = False
                self.page.update()
                self._categories = self.ctrl.get_categories()
                self._render_grid()

        def on_cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar Categoría" if is_edit else "Nueva Categoría", weight=ft.FontWeight.BOLD),
            content=ft.Container(content=name_f, width=300),
            actions=[
                ft.TextButton("Cancelar", on_click=on_cancel),
                ft.Container(
                    content=ft.Text("Guardar", color="white", weight=ft.FontWeight.W_600),
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

    def _confirm_delete(self, category_id: str):
        def do_delete(e):
            dialog.open = False
            self.page.update()
            ok = self.ctrl.delete_category(category_id)
            if ok:
                self._categories = self.ctrl.get_categories()
                self._render_grid()

        def cancel(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.icons.WARNING_ROUNDED, color=AppTheme.ERROR),
                          ft.Text("Eliminar Categoría", weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Text("¿Eliminar esta categoría? Los productos asociados quedarán sin categoría."),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel),
                ft.Container(
                    content=ft.Text("Eliminar", color="white", weight=ft.FontWeight.W_600),
                    gradient=AppTheme.gradient_error(), border_radius=8,
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                    on_click=do_delete, ink=True,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()