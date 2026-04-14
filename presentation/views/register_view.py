# presentation/views/register_view.py

import flet as ft
from presentation.theme import AppTheme


class RegisterView:

    def __init__(self, page, colors, is_dark, auth_controller, app):
        self.page = page
        self.colors = colors
        self.is_dark = is_dark
        self.auth_controller = auth_controller
        self.app = app

        self.email_field = AppTheme.make_text_field(
            "Correo electrónico", "tu@empresa.com", colors=colors
        )
        self.password_field = AppTheme.make_text_field(
            "Contraseña", "Mínimo 6 caracteres", password=True, colors=colors
        )
        self.confirm_field = AppTheme.make_text_field(
            "Confirmar contraseña", "Repite tu contraseña", password=True, colors=colors
        )

    def build(self):
        c = self.colors

        def on_register(e):
            pwd = self.password_field.value or ""
            conf = self.confirm_field.value or ""
            if pwd != conf:
                self.app.show_snackbar("Las contraseñas no coinciden", error=True)
                return
            self.auth_controller.register(
                self.email_field.value or "",
                pwd,
            )

        register_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.icons.PERSON_ADD_ROUNDED, color="white", size=18),
                    ft.Text(
                        "Crear Cuenta",
                        color="white",
                        size=14,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            gradient=AppTheme.gradient_primary(),
            border_radius=12,
            padding=ft.padding.symmetric(vertical=14),
            on_click=on_register,
            ink=True,
        )

        form = ft.Column(
            [
                ft.Text("Crear cuenta", size=28, weight=ft.FontWeight.BOLD, color=c["text"]),
                ft.Text("Comienza con NexaPOS hoy", size=14, color=c["text_secondary"]),
                ft.Container(height=28),
                self.email_field,
                ft.Container(height=12),
                self.password_field,
                ft.Container(height=12),
                self.confirm_field,
                ft.Container(height=24),
                register_btn,
                ft.Container(height=12),
                ft.Row(
                    [
                        ft.Text("¿Ya tienes cuenta?", size=13, color=c["text_secondary"]),
                        ft.TextButton(
                            "Inicia sesión",
                            style=ft.ButtonStyle(color=AppTheme.ACCENT),
                            on_click=lambda e: self.app.navigate_to("login"),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
            ],
            width=340,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        left_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.icons.STORE_ROUNDED, color="white", size=72),
                    ft.Container(height=20),
                    ft.Text(
                        "Tu negocio,\nen la nube",
                        color="white",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Text(
                        "Regístrate y obtén tu propio\nespacio multitenant gratuito",
                        color="white",
                        size=15,
                        text_align=ft.TextAlign.CENTER,
                        opacity=0.9,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            gradient=AppTheme.gradient_auth_panel(),
            expand=1,
            alignment=ft.alignment.center,
            padding=ft.padding.all(48),
        )

        right_panel = ft.Container(
            content=form,
            expand=1,
            alignment=ft.alignment.center,
            bgcolor=c["bg"],
        )

        return ft.Container(
            content=ft.Row([left_panel, right_panel], expand=True, spacing=0),
            expand=True,
            bgcolor=c["bg"],
        )