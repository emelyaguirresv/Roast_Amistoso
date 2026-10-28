import asyncio
import array
import math
from pathlib import Path
import sys

import flet as ft
import flet_audio as fta
from flet_audio_recorder import AudioEncoder, AudioRecorder, AudioRecorderConfiguration

from ia import ia
from multimedia import (
    generar_imagen,
    ia_media,
    pcm_a_wav,
    sintetizar_voz,
    transcribir_audio,
)

INSTRUCCION = (
    'Responde SOLO con JSON válido y exactamente estos campos: '
    '{"broma1":"...","broma2":"...","broma3":"..."}. '
    'Escribe tres bromas amistosas, breves y originales sobre el texto, hábito, anécdota u objeto indicado. '
    'Responde en el mismo idioma. Que suenen naturales, cariñosas y fáciles de compartir entre amigos. '
    'Nunca insultes, humilles ni hagas bromas sobre apariencia, salud, origen, religión, discapacidad, '
    'identidad o situación económica. No bromees sobre personas que aparezcan en una imagen; '
    'si hay una persona, enfócate solamente en un objeto cotidiano.'
)
INSTRUCCION_FOTO = INSTRUCCION + ' Basa las bromas en el objeto cotidiano principal de la foto.'
INSTRUCCION_VOZ = (
    'Transcribe fielmente lo que se escucha, detectando automáticamente el idioma. '
    'No traduzcas, resumas ni agregues explicaciones. Conserva nombres y expresiones habladas.'
)
INSTRUCCION_OCR = (
    'Lee el texto visible en la imagen. Devuelve únicamente el texto legible, '
    'conservando el orden y los saltos de línea. Si no hay texto legible, responde: No se encontró texto legible.'
)
MAX_TEXTO = 4000
LOGO_BYTES = (Path(__file__).resolve().parent.parent / "assets" / "labu-removebg-preview.png").read_bytes()


def vista(page: ft.Page):
    page.title = "Roast amistoso · chat"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#100C16"
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO

    selector = ft.FilePicker()
    fragmentos_audio = []
    estado = {
        "grabando": False,
        "tarea_limite": None,
        "adjunto": None,
        "audio": None,
        "voz_detectada": False,
        "silencio_ms": 0.0,
        "auto_cierre": False,
    }

    def recibir_audio(evento):
        chunk = evento.chunk
        if not chunk:
            return
        fragmentos_audio.append(chunk)
        if not estado["grabando"] or estado["auto_cierre"]:
            return
        muestras = array.array("h")
        muestras.frombytes(chunk[: len(chunk) & ~1])
        if not muestras:
            return
        if sys.byteorder == "big":
            muestras.byteswap()
        rms = math.sqrt(sum(muestra * muestra for muestra in muestras) / len(muestras))
        duracion_ms = len(muestras) * 1000 / 44100
        if rms >= 420:
            estado["voz_detectada"] = True
            estado["silencio_ms"] = 0.0
        elif estado["voz_detectada"]:
            estado["silencio_ms"] += duracion_ms
            if estado["silencio_ms"] >= 1400:
                estado["auto_cierre"] = True
                page.run_task(finalizar_grabacion, automatico=True)

    grabadora = AudioRecorder(on_stream=recibir_audio)
    page.services.extend([selector, grabadora])

    mensajes = ft.ListView(expand=True, spacing=16, padding=ft.Padding.symmetric(horizontal=16, vertical=18), auto_scroll=True)
    aviso = ft.Text("", size=13, color="#CFC4DC")
    entrada = ft.TextField(
        hint_text="Escribe un mensaje…",
        multiline=True,
        min_lines=1,
        max_lines=5,
        shift_enter=True,
        border=ft.InputBorder.NONE,
        color="#FFFFFF",
        hint_style=ft.TextStyle(color="#A99CB8"),
        text_size=16,
        expand=True,
        content_padding=ft.Padding.only(left=4, right=4, top=12, bottom=10),
        max_length=MAX_TEXTO,
    )
    vista_adjunto = ft.Container(visible=False, padding=ft.Padding.only(left=14, right=14, top=10))

    def avisar(mensaje, color="#CFC4DC"):
        aviso.value = mensaje
        aviso.color = color
        aviso.update()

    def agregar_mensaje(rol, texto="", imagen=None, nombre_imagen=None, actualizar=True, reproducible=False):
        usuario = rol == "user"
        partes = []
        if texto:
            partes.append(ft.Text(texto, color="#FFFFFF", size=15, selectable=True))
        if imagen:
            partes.append(
                ft.Image(
                    src=imagen,
                    width=min(420, max(240, (page.width or 900) * 0.65)),
                    height=300,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=14,
                    semantics_label=nombre_imagen or "Imagen adjunta o generada",
                )
            )
        if reproducible and texto:
            async def escuchar_respuesta(evento, frase=texto):
                await leer_en_voz_alta(evento, frase)

            partes.append(
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.VOLUME_UP,
                            icon_color="#D8B4FE",
                            tooltip="Escuchar estas bromas",
                            on_click=escuchar_respuesta,
                        ),
                        ft.Text("Escuchar bromas", size=12, color="#C4B5FD"),
                    ],
                    spacing=2,
                    alignment=ft.MainAxisAlignment.END,
                )
            )
        burbuja = ft.Container(
            content=ft.Column(partes, spacing=10, tight=True),
            padding=ft.Padding.symmetric(horizontal=16, vertical=13),
            bgcolor="#5B32A8" if usuario else "#211A2B",
            border=ft.Border.all(1, "#7651B8" if usuario else "#382D46"),
            border_radius=20,
            width=min(700, max(250, (page.width or 1000) * 0.78)),
        )
        avatar = (
            ft.Icon(ft.Icons.PERSON, color="#E9D5FF", size=17)
            if usuario
            else ft.Image(
                src=LOGO_BYTES,
                width=42,
                height=42,
                fit=ft.BoxFit.CONTAIN,
                semantics_label="Logo Labu",
            )
        )
        icono = ft.Container(
            content=avatar,
            width=42,
            height=42,
            alignment=ft.Alignment(0, 0),
            bgcolor="#382653" if usuario else "#332248",
            border_radius=21,
        )
        fila = ft.Row(
            controls=[icono, burbuja] if not usuario else [burbuja, icono],
            alignment=ft.MainAxisAlignment.START if not usuario else ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=10,
        )
        mensajes.controls.append(fila)
        if actualizar:
            mensajes.update()

    def poner_adjunto(archivo, mime):
        estado["adjunto"] = {"bytes": archivo.bytes, "mime": mime, "nombre": archivo.name}
        vista_adjunto.content = ft.Row(
            [
                ft.Icon(ft.Icons.IMAGE, color="#D8B4FE", size=18),
                ft.Text(archivo.name, color="#E9D5FF", size=13, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.IconButton(icon=ft.Icons.CLOSE, icon_color="#D8B4FE", tooltip="Quitar imagen", on_click=quitar_adjunto),
            ],
            spacing=6,
        )
        vista_adjunto.visible = True
        vista_adjunto.update()
        avisar("Imagen lista para enviar junto con tu mensaje.")

    def quitar_adjunto(evento=None):
        estado["adjunto"] = None
        vista_adjunto.visible = False
        vista_adjunto.update()

    def tipo_imagen(nombre):
        ext = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""
        return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext)

    async def elegir_imagen(evento=None):
        archivos = await selector.pick_files(file_type=ft.FilePickerFileType.IMAGE, allow_multiple=False, with_data=True)
        if not archivos:
            return
        archivo = archivos[0]
        mime = tipo_imagen(archivo.name)
        if not mime or not archivo.bytes:
            avisar("No pudimos leer esa imagen. Usa JPG, PNG o WEBP.", "#FFC6D2")
            return
        if len(archivo.bytes) > 15_000_000:
            avisar("La imagen supera 15 MB. Elige una más pequeña.", "#FDE68A")
            return
        poner_adjunto(archivo, mime)

    async def cargar_texto(evento=None):
        archivos = await selector.pick_files(
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["txt"],
            allow_multiple=False,
            with_data=True,
        )
        if not archivos:
            return
        archivo = archivos[0]
        if not archivo.bytes or len(archivo.bytes) > 50_000:
            avisar("El archivo está vacío o supera 50 KB.", "#FDE68A")
            return
        try:
            contenido = archivo.bytes.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            avisar("Guarda el archivo como texto UTF-8 e inténtalo otra vez.", "#FDE68A")
            return
        if not contenido or len(contenido) > MAX_TEXTO:
            avisar("El texto debe tener entre 1 y 4000 caracteres.", "#FDE68A")
            return
        entrada.value = contenido
        entrada.update()
        avisar("Texto cargado. Puedes enviarlo o pedir una imagen.", "#C4F1D0")

    async def leer_foto(evento=None):
        archivos = await selector.pick_files(file_type=ft.FilePickerFileType.IMAGE, allow_multiple=False, with_data=True)
        if not archivos:
            return
        archivo = archivos[0]
        mime = tipo_imagen(archivo.name)
        if not mime or not archivo.bytes:
            avisar("Elige una imagen JPG, PNG o WEBP que se pueda leer.", "#FDE68A")
            return
        avisar("Leyendo el texto de la imagen…")
        try:
            texto_leido = await asyncio.to_thread(ia_media, INSTRUCCION_OCR, archivo.bytes, mime, "", False)
            texto_leido = texto_leido.strip()
            if not texto_leido or texto_leido == "No se encontró texto legible.":
                raise RuntimeError("No encontramos texto legible. Prueba con una imagen más clara.")
            entrada.value = texto_leido[:MAX_TEXTO]
            entrada.update()
            avisar("Texto extraído. Ya puedes enviarlo.", "#C4F1D0")
        except Exception as exc:
            avisar(str(exc) if isinstance(exc, RuntimeError) else "No pudimos leer esa imagen.", "#FFC6D2")

    def frases_como_texto(datos):
        if not isinstance(datos, dict):
            raise RuntimeError("La IA respondió en un formato inesperado.")
        frases = [datos.get(f"broma{i}") for i in range(1, 4)]
        if not all(isinstance(frase, str) and frase.strip() for frase in frases):
            raise RuntimeError("La IA no devolvió las tres bromas. Inténtalo otra vez.")
        return "\n\n".join(f"{i}. {frase.strip()}" for i, frase in enumerate(frases, start=1))

    async def enviar(evento=None):
        texto_usuario = (entrada.value or "").strip()
        adjunto = estado["adjunto"]
        if not texto_usuario and not adjunto:
            avisar("Escribe o dicta un mensaje, o adjunta una imagen.", "#FDE68A")
            await entrada.focus()
            return
        if len(texto_usuario) > MAX_TEXTO:
            avisar("El mensaje supera 4000 caracteres.", "#FDE68A")
            return

        agregar_mensaje("user", texto_usuario, adjunto["bytes"] if adjunto else None, adjunto["nombre"] if adjunto else None)
        entrada.value = ""
        entrada.update()
        quitar_adjunto()
        enviar_btn.disabled = True
        crear_img_btn.disabled = True
        enviar_btn.update()
        crear_img_btn.update()
        avisar("Preparando tus tres bromas amistosas…")
        try:
            if adjunto:
                datos = await asyncio.to_thread(
                    ia_media, INSTRUCCION_FOTO, adjunto["bytes"], adjunto["mime"], texto_usuario, True
                )
            else:
                datos = await asyncio.to_thread(ia, INSTRUCCION, texto_usuario, True)
            agregar_mensaje("assistant", frases_como_texto(datos), reproducible=True)
            avisar("Listo. ¿Hacemos otra ronda? 💜", "#C4F1D0")
        except Exception as exc:
            mensaje = str(exc) if isinstance(exc, RuntimeError) else "No pudimos conectar con la IA. Revisa la llave y tu conexión."
            agregar_mensaje("assistant", mensaje)
            avisar("No se pudo completar el mensaje.", "#FFC6D2")
        finally:
            enviar_btn.disabled = False
            crear_img_btn.disabled = False
            enviar_btn.update()
            crear_img_btn.update()

    async def crear_imagen(evento=None):
        prompt = (entrada.value or "").strip()
        if not prompt:
            avisar("Escribe o dicta qué imagen quieres crear.", "#FDE68A")
            await entrada.focus()
            return
        adjunto = estado["adjunto"]
        agregar_mensaje("user", "Crear una imagen: " + prompt, adjunto["bytes"] if adjunto else None, adjunto["nombre"] if adjunto else None)
        entrada.value = ""
        entrada.update()
        quitar_adjunto()
        enviar_btn.disabled = True
        crear_img_btn.disabled = True
        enviar_btn.update()
        crear_img_btn.update()
        avisar("Creando tu imagen. Puede tardar un poco…")
        try:
            imagen, mime = await asyncio.to_thread(
                generar_imagen,
                prompt,
                adjunto["bytes"] if adjunto else None,
                adjunto["mime"] if adjunto else "image/jpeg",
            )
            agregar_mensaje("assistant", "Aquí está la imagen que pediste. 💜", imagen)
            avisar("Imagen creada.", "#C4F1D0")
        except Exception as exc:
            mensaje = str(exc) if isinstance(exc, RuntimeError) else "No pudimos crear la imagen. Revisa la llave y tu conexión."
            agregar_mensaje("assistant", mensaje)
            avisar("No se pudo crear la imagen.", "#FFC6D2")
        finally:
            enviar_btn.disabled = False
            crear_img_btn.disabled = False
            enviar_btn.update()
            crear_img_btn.update()

    async def leer_en_voz_alta(evento=None, texto=None):
        texto_actual = (texto if texto is not None else entrada.value or "").strip()
        if not texto_actual:
            avisar("Primero dicta o escribe un texto para escucharlo.", "#FDE68A")
            return
        boton = getattr(evento, "control", None) if evento else leer_btn
        boton.disabled = True
        boton.update()
        avisar("Preparando las bromas para escucharlas…" if texto is not None else "Preparando la lectura en voz alta…")
        try:
            audio = await asyncio.wait_for(
                asyncio.to_thread(lambda: asyncio.run(sintetizar_voz(texto_actual[:MAX_TEXTO]))),
                timeout=18,
            )
            avisar("Audio listo; reproduciendo las bromas…" if texto is not None else "Audio listo; reproduciendo tu texto…")
            reproductor = estado["audio"]
            if reproductor is None:
                reproductor = fta.Audio(src=audio, autoplay=False, volume=1.0)
                page.services.append(reproductor)
                estado["audio"] = reproductor
                page.update()
            else:
                await reproductor.release()
                reproductor.src = audio
                reproductor.update()
            page.run_task(reproductor.play)
            avisar("Leyendo las bromas en voz alta." if texto is not None else "Leyendo tu texto en voz alta.", "#C4F1D0")
        except asyncio.TimeoutError:
            avisar("La voz tardó demasiado en prepararse. Inténtalo de nuevo.", "#FFC6D2")
        except Exception as exc:
            mensaje = str(exc) if isinstance(exc, RuntimeError) else "No se pudo reproducir la voz. Revisa internet."
            avisar(mensaje, "#FFC6D2")
        finally:
            boton.disabled = False
            boton.update()

    async def finalizar_grabacion(automatico=False):
        if not estado["grabando"]:
            return
        estado["grabando"] = False
        tarea = estado["tarea_limite"]
        if tarea and tarea is not asyncio.current_task():
            tarea.cancel()
        await grabadora.stop_recording()
        microfono.icon = ft.Icons.MIC
        microfono.tooltip = "Hablar"
        microfono.update()
        if not fragmentos_audio:
            fragmentos_audio.clear()
            avisar("No llegó audio. Revisa el permiso del micrófono e inténtalo de nuevo.", "#FFC6D2")
            return
        if not estado["voz_detectada"]:
            fragmentos_audio.clear()
            avisar("No detecté voz. Acércate al micrófono y vuelve a intentarlo.", "#FFC6D2")
            return
        avisar("Te detuviste; transcribiendo tu voz…" if automatico else "Transcribiendo tu voz…")
        try:
            wav = pcm_a_wav(b"".join(fragmentos_audio), tasa=44100, canales=1)
            transcripcion = await asyncio.to_thread(transcribir_audio, wav, INSTRUCCION_VOZ)
            if not transcripcion.strip():
                raise RuntimeError("No se entendió la voz. Acércate al micrófono y habla con claridad.")
            entrada.value = transcripcion[:MAX_TEXTO]
            entrada.update()
            avisar("Voz transcrita. Usa el altavoz para escucharla o envía el mensaje.", "#C4F1D0")
        except Exception as exc:
            mensaje = str(exc) if isinstance(exc, RuntimeError) else "No pudimos transcribir el audio. Revisa la llave y la conexión."
            avisar(mensaje, "#FFC6D2")

    async def detener_automaticamente():
        await asyncio.sleep(12)
        if estado["grabando"] and not estado["voz_detectada"]:
            await finalizar_grabacion(automatico=True)
            return
        await asyncio.sleep(18)
        if estado["grabando"]:
            await finalizar_grabacion(automatico=True)

    async def alternar_microfono(evento=None):
        if estado["grabando"]:
            await finalizar_grabacion()
            return
        try:
            permiso = await grabadora.has_permission()
            if not permiso:
                avisar("Dale permiso al navegador para usar el micrófono.", "#FDE68A")
                return
            fragmentos_audio.clear()
            estado["voz_detectada"] = False
            estado["silencio_ms"] = 0.0
            estado["auto_cierre"] = False
            config = AudioRecorderConfiguration(
                encoder=AudioEncoder.PCM16BITS,
                sample_rate=44100,
                channels=1,
                suppress_noise=True,
                cancel_echo=True,
                auto_gain=True,
            )
            inicio = await grabadora.start_recording(configuration=config)
            if not inicio:
                avisar("No se pudo iniciar el micrófono. Revisa el permiso del navegador.", "#FFC6D2")
                return
            estado["grabando"] = True
            microfono.icon = ft.Icons.STOP
            microfono.tooltip = "Detener y transcribir"
            microfono.update()
            avisar("Te escucho… me detendré y transcribiré cuando termines de hablar.", "#FDE68A")
            estado["tarea_limite"] = asyncio.create_task(detener_automaticamente())
        except Exception:
            avisar("No pudimos abrir el micrófono. Acepta el permiso y vuelve a intentarlo.", "#FFC6D2")

    enviar_btn = ft.IconButton(
        icon=ft.Icons.SEND,
        icon_color="#FFFFFF",
        bgcolor="#7C3AED",
        tooltip="Enviar y crear bromas",
        on_click=enviar,
    )
    crear_img_btn = ft.TextButton(
        "Crear imagen",
        icon=ft.Icons.IMAGE,
        tooltip="Crear una imagen basada en tu texto o voz",
        on_click=crear_imagen,
        style=ft.ButtonStyle(color="#D8B4FE"),
    )
    microfono = ft.IconButton(
        icon=ft.Icons.MIC,
        icon_color="#E9D5FF",
        tooltip="Hablar",
        on_click=alternar_microfono,
    )
    leer_btn = ft.IconButton(
        icon=ft.Icons.VOLUME_UP,
        icon_color="#E9D5FF",
        tooltip="Escuchar lo que escribiste o dictaste",
        on_click=leer_en_voz_alta,
    )
    menu_mas = ft.PopupMenuButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        icon_color="#D8B4FE",
        tooltip="Adjuntar o leer contenido",
        items=[
            ft.PopupMenuItem(content="Adjuntar imagen", icon=ft.Icons.IMAGE, on_click=elegir_imagen),
            ft.PopupMenuItem(content="Leer texto de una foto", icon=ft.Icons.TEXT_FIELDS, on_click=leer_foto),
            ft.PopupMenuItem(content="Cargar archivo .txt", icon=ft.Icons.UPLOAD_FILE, on_click=cargar_texto),
        ],
    )
    entrada.on_submit = enviar

    composer = ft.Container(
        content=ft.Column(
            [
                vista_adjunto,
                ft.Row(
                    [menu_mas, entrada, leer_btn, microfono, enviar_btn],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                ft.Row(
                    [crear_img_btn, ft.Container(expand=True), ft.Text("Intro para enviar · Shift+Intro para salto", size=11, color="#8E829A")],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=4,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        bgcolor="#1B1622",
        border=ft.Border.all(1, "#49375E"),
        border_radius=24,
    )

    encabezado = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Image(
                                src=LOGO_BYTES,
                                width=48,
                                height=48,
                                fit=ft.BoxFit.CONTAIN,
                                semantics_label="Logo Labu",
                            ),
                            width=48,
                            height=48,
                            bgcolor="#30213F",
                            border_radius=24,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            [ft.Text("Roast amistoso", size=17, weight=ft.FontWeight.BOLD, color="#FFFFFF"), ft.Text("Chat con buena onda", size=12, color="#A99CB8")],
                            spacing=1,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(
                    content=ft.Row([ft.Icon(ft.Icons.SHIELD_MOON, color="#C4B5FD", size=15), ft.Text("Con cariño", color="#E9D5FF", size=12)], spacing=6),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    bgcolor="#2A2035",
                    border_radius=18,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        border=ft.Border.only(bottom=ft.BorderSide(1, "#30263A")),
    )

    interfaz = ft.Container(
        content=ft.Column(
            [
                encabezado,
                mensajes,
                ft.Container(
                    content=ft.Column(
                        [aviso, composer, ft.Text("Tu audio y tus imágenes se procesan en línea. Crear imágenes requiere facturación de Google (aprox. $0.034 por imagen 1K). Evita datos privados.", size=10, color="#857992", text_align=ft.TextAlign.CENTER)],
                        spacing=7,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                ),
            ],
            expand=True,
            spacing=0,
        ),
        expand=True,
        bgcolor="#141019",
        border=ft.Border.all(1, "#382A49"),
        border_radius=24,
    )
    agregar_mensaje(
        "assistant",
        "¡Qué onda! Escribe o dicta un hábito y te doy tres bromas suaves. También puedes adjuntar una imagen con + o crear una imagen desde tu idea.",
        actualizar=False,
    )
    aviso.value = "Listo para chatear. 💜"
    return ft.Container(content=interfaz, expand=True, padding=ft.Padding.symmetric(horizontal=12, vertical=12))
