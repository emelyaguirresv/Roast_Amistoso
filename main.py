import os
import importlib
import flet as ft
import apps


def main(page: ft.Page):
    page.title = "Roast amistoso"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#24113D"
    page.padding = 24
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    module = importlib.import_module("apps.roast")
    page.add(module.vista(page))


if __name__ == "__main__":
    # En publicación se usa el puerto de la plataforma; en local, puerto 7861.
    publicado = bool(os.getenv("PORT"))
    host = "0.0.0.0" if publicado else "127.0.0.1"
    port = int(os.getenv("PORT", "7861"))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host=host, port=port)
