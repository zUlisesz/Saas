# main.py

import flet as ft
from presentation.app import App


def main(page: ft.Page):
    App(page)


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")