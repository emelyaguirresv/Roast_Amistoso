import asyncio
import flet as ft
from ia import ia

INSTRUCCION = (
    'Responde SOLO con JSON válido y exactamente estos campos: '
    '{"broma1":"...","broma2":"...","broma3":"..."}. '
    'Escribe tres bromas amistosas, breves y originales sobre el hábito indicado. '
    'Que suenen naturales, cariñosas y fáciles de compartir entre amigos. '
    'Nunca insultes, humilles ni hagas bromas sobre apariencia, salud, origen, '
    'religión, discapacidad, identidad o situación económica. Si el hábito no '
    'permite una broma respetuosa, elige bromas suaves sobre lo cotidiano.'
)
MORADO = "#8B5CF6"
BLANCO = "#FFFFFF"


def vista():
    entrada = ft.TextField(
        label="¿Qué hábito vamos a roast-ear?",
        hint_text="Ejemplo: siempre llega cinco minutos tarde",
        multiline=True,
        min_lines=2,
        max_lines=3,
        border_color="#70539A",
        focused_border_color="#C4B5FD",
        color=BLANCO,
        label_style=ft.TextStyle(color="#E9D5FF"),
        hint_style=ft.TextStyle(color="#BDAED0"),
        bgcolor="#1B1426",
        border_radius=16,
        text_size=16,
    )
    resultados = ft.Column(spacing=12)
    estado = ft.Text(color="#D8CBEA", size=14)
    boton = ft.Button("Crear mi roast", icon=ft.Icons.AUTO_AWESOME)
    otra = ft.Button("Otra ronda", icon=ft.Icons.REFRESH)

    boton.style = ft.ButtonStyle(
        bgcolor=MORADO, color=BLANCO, padding=18,
        shape=ft.RoundedRectangleBorder(radius=14),
    )
    otra.style = ft.ButtonStyle(
        bgcolor="#332C3F", color=BLANCO, padding=18,
        shape=ft.RoundedRectangleBorder(radius=14),
    )

    def poner_ejemplo(e):
        entrada.value = e.control.data
        entrada.update()
        entrada.focus()

    ejemplos = ft.Row(
        [
            ft.Text("Prueba:", color="#BDAED0", size=13),
            ft.TextButton("vive pegado al celular", data="vive pegado al celular", on_click=poner_ejemplo),
            ft.TextButton("siempre llega tarde", data="siempre llega tarde", on_click=poner_ejemplo),
        ], wrap=True, spacing=4,
    )

    def poner_tarjetas(datos):
        controles = []
        for numero, campo in enumerate(("broma1", "broma2", "broma3"), start=1):
            frase = datos.get(campo)
            if isinstance(frase, str) and frase.strip():
                controles.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(f"0{numero}", color=BLANCO, weight=ft.FontWeight.BOLD),
                                    width=40, height=40, alignment=ft.Alignment(0, 0),
                                    bgcolor="#5B3A87", border_radius=12,
                                ),
                                ft.Text(frase.strip(), color=BLANCO, size=16, expand=True, selectable=True),
                            ], spacing=14,
                        ),
                        padding=16, bgcolor="#20182C",
                        border=ft.Border.all(1, "#49395D"), border_radius=16,
                    )
                )
        if len(controles) != 3:
            raise ValueError("La respuesta no incluyó las tres bromas.")
        resultados.controls = controles

    async def generar(e):
        rasgo = (entrada.value or "").strip()
        if not rasgo:
            estado.value = "Escribe un hábito primero para preparar las bromas."
            estado.color = "#FDE68A"
            estado.update()
            entrada.focus()
            return
        if len(rasgo) > 240:
            estado.value = "Hazlo más breve: máximo 240 caracteres."
            estado.color = "#FDE68A"
            estado.update()
            return

        boton.disabled = True
        otra.disabled = True
        estado.value = "La IA está preparando tres bromas…"
        estado.color = "#D8CBEA"
        resultados.controls.clear()
        boton.update()
        otra.update()
        estado.update()
        resultados.update()
        try:
            datos = await asyncio.to_thread(ia, INSTRUCCION, rasgo, True)
            if not isinstance(datos, dict):
                raise ValueError("Formato inesperado")
            poner_tarjetas(datos)
            estado.value = "¡Listo! Que la risa sea entre amigos 💜"
            estado.color = "#C4F1D0"
        except Exception as exc:
            estado.value = str(exc) if isinstance(exc, RuntimeError) else "No pudimos crear las bromas. Inténtalo de nuevo."
            estado.color = "#FFC6D2"
            resultados.controls.clear()
        finally:
            boton.disabled = False
            otra.disabled = False
            boton.update()
            otra.update()
            estado.update()
            resultados.update()

    boton.on_click = generar
    otra.on_click = generar

    panel = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("TU MOMENTO DE HUMOR", size=11, weight=ft.FontWeight.BOLD, color="#C4B5FD"),
                                ft.Text("Roast amistoso", size=25, weight=ft.FontWeight.BOLD, color=BLANCO),
                            ], spacing=5, expand=True,
                        ),
                        ft.Container(
                            content=ft.Row([ft.Icon(ft.Icons.SHIELD_MOON, color="#C4B5FD", size=16), ft.Text("Con cariño", color="#E9D5FF", size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                            padding=10, bgcolor="#332C3F", border_radius=20,
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text("Escribe un hábito cotidiano y crea tres bromas ligeras para compartir.", color="#CFC4DC", size=15),
                entrada,
                ejemplos,
                ft.Row([boton, otra], wrap=True, spacing=10),
                estado,
                resultados,
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINE, color="#C4B5FD", size=18),
                            ft.Text("La IA puede equivocarse. No uses datos privados y comparte solo bromas que se sientan amables.", color="#CFC4DC", size=12, expand=True),
                        ], spacing=10,
                    ),
                    padding=14, bgcolor="#191321", border_radius=14,
                ),
            ], spacing=16,
        ),
        padding=26, bgcolor="#241A32", border_radius=24,
        border=ft.Border.all(1, "#58466B"), col={"xs": 12, "lg": 7},
    )

    izquierda = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row([ft.Icon(ft.Icons.FAVORITE, color="#F0ABFC", size=16), ft.Text("HUMOR ENTRE AMIGOS", color="#E9D5FF", size=11, weight=ft.FontWeight.BOLD)], spacing=7),
                    padding=10, bgcolor="#2B2039", border_radius=20, width=190,
                ),
                ft.Text("Un roast suave.\nRisas reales.", size=42, weight=ft.FontWeight.BOLD, color=BLANCO),
                ft.Text("La herramienta perfecta para bromear con cariño y mantener la buena vibra.", size=17, color="#CFC4DC"),
                ft.Container(height=8),
                ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color="#C4B5FD", size=18), ft.Text("Tres ideas, hechas por IA", color=BLANCO, size=14)], spacing=10),
                ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, color="#C4B5FD", size=18), ft.Text("Sin insultos ni temas sensibles", color=BLANCO, size=14)], spacing=10),
                ft.Row([ft.Icon(ft.Icons.FAVORITE_BORDER, color="#C4B5FD", size=18), ft.Text("Siempre con respeto", color=BLANCO, size=14)], spacing=10),
            ], spacing=18, alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=28, col={"xs": 12, "lg": 5},
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row([ft.Icon(ft.Icons.MOOD, color="#C4B5FD", size=24), ft.Text("BUENA ONDA", color=BLANCO, size=15, weight=ft.FontWeight.BOLD)], spacing=9),
                        ft.Text("ROAST AMISTOSO  ·  IA", color="#9D8BAC", size=11, weight=ft.FontWeight.BOLD),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(height=24),
                ft.ResponsiveRow(controls=[izquierda, panel], spacing=20, run_spacing=20, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=16),
                ft.Text("HECHO PARA COMPARTIR UNA RISA 💜", color="#806D91", size=10, weight=ft.FontWeight.BOLD),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
        ),
        padding=ft.Padding.only(left=22, right=22, top=16, bottom=24),
        bgcolor="#100C16", expand=True,
    )

