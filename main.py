# t.py — Punto de entrada de la app Flet
#
# Flet 0.21+ usa Material Symbols en desktop. Para que los íconos
# rendericen correctamente sin depender del font bundling del runner
# nativo, se lanza en modo web browser por defecto.
# El browser carga Material Symbols desde CDN al igual que en producción.

import flet as ft
from presentation.app import App


def main(page: ft.Page):
    App(page)


if __name__ == "__main__":
    ft.app(
        target=main,
        assets_dir="assets",
        view=ft.AppView.WEB_BROWSER,
    )
