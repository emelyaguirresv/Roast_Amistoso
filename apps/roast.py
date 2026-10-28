import asyncio

import flet as ft
from flet_audio_recorder import AudioEncoder, AudioRecorder, AudioRecorderConfiguration

from ia import ia
from multimedia import ia_media, pcm_a_wav

INSTRUCCION = (
    'Responde SOLO con JSON válido y exactamente estos campos: '
    '{"broma1":"...","broma2":"...","broma3":"..."}. '
    'Escribe tres bromas amistosas, breves y originales sobre el hábito u objeto indicado. '
    'Que suenen naturales, cariñosas y fáciles de compartir entre amigos. '
    'Nunca insultes, humilles ni hagas bromas sobre apariencia, salud, origen, religión, '
    'discapacidad, identidad o situación económica. No bromees sobre personas que aparezcan '
    'en una imagen; si aparece una persona, haz bromas suaves sobre un objeto cotidiano.'
)
INSTRUCCION_FOTO = (
    INSTRUCCION + ' Observa la imagen y basa las bromas en el objeto cotidiano principal. '
    'No identifiques a nadie ni describas personas.'
)
INSTRUCCION_VOZ = (
    'Transcribe en español únicamente las palabras que se escuchan con claridad. '
    'No agregues explicaciones, nombres ni información que no se haya dicho.'
)
INSTRUCCION_OCR = (
    'Lee el texto visible en la imagen. Devuelve únicamente el texto que se pueda leer, '
    'conservando el orden y los saltos de línea. Si no hay texto legible, responde: '
    'No se encontró texto legible.'
)
MORADO = "#8B5CF6"
BLANCO = "#FFFFFF"
MAX_TEXTO = 4000


def vista(page: ft.Page):
    # Los servicios de Flet permiten seleccionar archivos y grabar desde el navegador.
    selector = ft.FilePicker()
    fragmentos_audio = []
    grabando = False
    tarea_limite = None
    imagen_actual = {"bytes": None, "mime": None, "nombre": ""}

    def recibir_audio(evento):
        if evento.chunk:
            fragmentos_audio.append(evento.chunk)

    grabadora = AudioRecorder(on_stream=recibir_audio)
    page.services.append(selector)
    page.services.append(grabadora)

    entrada = ft.TextField(
        label="¿Qué hábito vamos a roast-ear?",
        hint_text="Ejemplo: siempre llega cinco minutos tarde",
        multiline=True,
        min_lines=2,
        max_lines=4,
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
    archivo_estado = ft.Text(color="#C4B5FD", size=12)
    boton = ft.Button("Crear mi roast", icon=ft.Icons.AUTO_AWESOME)
    otra = ft.Button("Otra ronda", icon=ft.Icons.REFRESH)
    microfono = ft.Button("Hablar (máx. 30 s)", icon=ft.Icons.MIC)
    foto = ft.Button("Usar foto de objeto", icon=ft.Icons.IMAGE)
    texto = ft.Button("Cargar archivo .txt", icon=ft.Icons.UPLOAD_FILE)
    leer_foto = ft.Button("Leer texto de una foto", icon=ft.Icons.TEXT_FIELDS)

    boton.style = ft.ButtonStyle(
        bgcolor=MORADO, color=BLANCO, padding=18,
        shape=ft.RoundedRectangleBorder(radius=14),
    )
    for control in (otra, microfono, foto, texto, leer_foto):
        control.style = ft.ButtonStyle(
            bgcolor="#332C3F", color=BLANCO, padding=14,
            shape=ft.RoundedRectangleBorder(radius=14),
        )

    def avisar(mensaje, color="#D8CBEA"):
        estado.value = mensaje
        estado.color = color
        estado.update()

    def poner_ejemplo(evento):
        entrada.value = evento.control.data
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

    def mime_de_imagen(nombre):
        extension = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""
        return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(extension)

    async def elegir_imagen(evento):
        archivos = await selector.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            allow_multiple=False,
            with_data=True,
        )
        if not archivos:
            return
        archivo = archivos[0]
        tipo = mime_de_imagen(archivo.name)
        if not tipo:
            avisar("Usa una imagen JPG, PNG o WEBP.", "#FDE68A")
            return
        if not archivo.bytes:
            avisar("No pudimos leer la foto. Vuelve a elegirla.", "#FFC6D2")
            return
        imagen_actual.update({"bytes": archivo.bytes, "mime": tipo, "nombre": archivo.name})
        archivo_estado.value = f"Foto lista: {archivo.name}. Pulsa Crear mi roast para usarla."
        archivo_estado.update()
        avisar("Foto cargada. Se enviará a Gemini cuando generes las bromas.")

    async def cargar_txt(evento):
        archivos = await selector.pick_files(
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["txt"],
            allow_multiple=False,
            with_data=True,
        )
        if not archivos:
            return
        archivo = archivos[0]
        if not archivo.bytes:
            avisar("El archivo está vacío o no pudimos leerlo.", "#FFC6D2")
            return
        if len(archivo.bytes) > 50_000:
            avisar("El archivo supera 50 KB. Guarda una versión más corta.", "#FDE68A")
            return
        try:
            contenido = archivo.bytes.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            avisar("El archivo debe estar guardado como texto UTF-8.", "#FDE68A")
            return
        if not contenido:
            avisar("El archivo no contiene texto. Elige otro archivo .txt.", "#FDE68A")
            return
        if len(contenido) > MAX_TEXTO:
            avisar("El texto supera 4000 caracteres. Acórtalo antes de usarlo.", "#FDE68A")
            return
        imagen_actual.update({"bytes": None, "mime": None, "nombre": ""})
        entrada.value = contenido
        entrada.update()
        archivo_estado.value = f"Texto cargado: {archivo.name}"
        archivo_estado.update()
        avisar("Revisa el texto y pulsa Crear mi roast para usarlo.")

    async def leer_texto_foto(evento):
        archivos = await selector.pick_files(
            file_type=ft.FilePickerFileType.IMAGE,
            allow_multiple=False,
            with_data=True,
        )
        if not archivos:
            return
        archivo = archivos[0]
        tipo = mime_de_imagen(archivo.name)
        if not tipo or not archivo.bytes:
            avisar("Elige una imagen JPG, PNG o WEBP que se pueda leer.", "#FDE68A")
            return
        if len(archivo.bytes) > 15_000_000:
            avisar("La foto supera 15 MB. Elige una imagen más pequeña.", "#FDE68A")
            return
        leer_foto.disabled = True
        leer_foto.update()
        avisar("Leyendo el texto de la foto…")
        try:
            transcripcion = await asyncio.to_thread(
                ia_media, INSTRUCCION_OCR, archivo.bytes, tipo, "", False
            )
            transcripcion = transcripcion.strip()
            if not transcripcion or transcripcion == "No se encontró texto legible.":
                raise RuntimeError("No encontramos texto legible. Prueba con una foto más clara.")
            if len(transcripcion) > MAX_TEXTO:
                raise RuntimeError("El texto leído supera 4000 caracteres. Usa una foto con menos texto.")
            imagen_actual.update({"bytes": None, "mime": None, "nombre": ""})
            entrada.value = transcripcion
            entrada.update()
            archivo_estado.value = f"Texto leído de: {archivo.name}"
            archivo_estado.update()
            avisar("Texto extraído. Revísalo y pulsa Crear mi roast para usarlo.", "#C4F1D0")
        except Exception as exc:
            avisar(str(exc) if isinstance(exc, RuntimeError) else "No pudimos leer la foto. Inténtalo con otra imagen.", "#FFC6D2")
        finally:
            leer_foto.disabled = False
            leer_foto.update()

    async def generar(evento):
        rasgo = (entrada.value or "").strip()
        datos_foto = imagen_actual["bytes"]
        if not rasgo and not datos_foto:
            avisar("Escribe, habla, carga un .txt o elige una foto primero.", "#FDE68A")
            entrada.focus()
            return
        if len(rasgo) > MAX_TEXTO:
            avisar("El texto supera 4000 caracteres. Acórtalo antes de continuar.", "#FDE68A")
            return

        boton.disabled = True
        otra.disabled = True
        resultados.controls.clear()
        boton.update()
        otra.update()
        resultados.update()
        avisar("La IA está preparando tres bromas…")
        try:
            if datos_foto:
                datos = await asyncio.to_thread(
                    ia_media, INSTRUCCION_FOTO, datos_foto, imagen_actual["mime"], rasgo, True
                )
            else:
                datos = await asyncio.to_thread(ia, INSTRUCCION, rasgo, True)
            if not isinstance(datos, dict):
                raise ValueError("Formato inesperado")
            poner_tarjetas(datos)
            avisar("¡Listo! Que la risa sea entre amigos 💜", "#C4F1D0")
        except Exception as exc:
            mensaje = str(exc) if isinstance(exc, RuntimeError) else "No pudimos crear las bromas. Inténtalo de nuevo."
            avisar(mensaje, "#FFC6D2")
            resultados.controls.clear()
        finally:
            boton.disabled = False
            otra.disabled = False
            boton.update()
            otra.update()
            resultados.update()

    async def terminar_grabacion():
        nonlocal grabando, tarea_limite
        if not grabando:
            return
        grabando = False
        if tarea_limite and tarea_limite is not asyncio.current_task():
            tarea_limite.cancel()
        await grabadora.stop_recording()
        microfono.text = "Hablar (máx. 30 s)"
        microfono.icon = ft.Icons.MIC
        microfono.update()
        if not fragmentos_audio:
            avisar("No se recibió audio. Revisa el permiso del micrófono e inténtalo otra vez.", "#FFC6D2")
            return
        avisar("Transcribiendo tu voz…")
        try:
            audio_wav = pcm_a_wav(b"".join(fragmentos_audio), tasa=16000, canales=1)
            transcripcion = await asyncio.to_thread(
                ia_media, INSTRUCCION_VOZ, audio_wav, "audio/wav", "", False
            )
            transcripcion = transcripcion.strip()
            if not transcripcion:
                raise RuntimeError("No se entendió la voz. Prueba hablando más cerca del micrófono.")
            imagen_actual.update({"bytes": None, "mime": None, "nombre": ""})
            entrada.value = transcripcion[:MAX_TEXTO]
            entrada.update()
            archivo_estado.value = "Voz transcrita. Revisa el texto antes de enviarlo para generar bromas."
            archivo_estado.update()
            avisar("Voz transcrita. Pulsa Crear mi roast cuando estés listo.", "#C4F1D0")
        except Exception as exc:
            avisar(str(exc) if isinstance(exc, RuntimeError) else "No pudimos transcribir el audio. Inténtalo otra vez.", "#FFC6D2")

    async def parar_automaticamente():
        await asyncio.sleep(30)
        if grabando:
            avisar("Llegaste al límite de 30 segundos. Procesando tu voz…")
            await terminar_grabacion()

    async def alternar_microfono(evento):
        nonlocal grabando, tarea_limite
        if grabando:
            avisar("Procesando tu grabación…")
            await terminar_grabacion()
            return
        try:
            permiso = await grabadora.has_permission()
            if not permiso:
                avisar("Permite el acceso al micrófono para usar la voz.", "#FDE68A")
                return
            fragmentos_audio.clear()
            configuracion = AudioRecorderConfiguration(
                encoder=AudioEncoder.PCM16BITS,
                sample_rate=16000,
                channels=1,
            )
            inicio = await grabadora.start_recording(configuration=configuracion)
            if not inicio:
                avisar("No se pudo iniciar el micrófono. Revisa el permiso del navegador.", "#FFC6D2")
                return
            grabando = True
            microfono.text = "Detener y transcribir"
            microfono.icon = ft.Icons.STOP
            microfono.update()
            avisar("Grabando… habla ahora. Se detendrá en un máximo de 30 segundos.", "#FDE68A")
            tarea_limite = asyncio.create_task(parar_automaticamente())
        except Exception:
            avisar("No pudimos abrir el micrófono. Acepta el permiso y vuelve a intentarlo.", "#FFC6D2")

    boton.on_click = generar
    otra.on_click = generar
    microfono.on_click = alternar_microfono
    foto.on_click = elegir_imagen
    texto.on_click = cargar_txt
    leer_foto.on_click = leer_texto_foto

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
                ft.Text("También puedes entrar por voz, foto o archivo", color="#E9D5FF", size=14, weight=ft.FontWeight.BOLD),
                ft.Row([microfono, foto, texto, leer_foto], wrap=True, spacing=8, run_spacing=8),
                ft.Text(
                    "Voz: hasta 30 segundos. Foto: solo objetos o texto. No subas personas, compañeros, DUI, teléfonos ni contraseñas.",
                    color="#BDAED0", size=12,
                ),
                archivo_estado,
                ft.Row([boton, otra], wrap=True, spacing=10),
                estado,
                resultados,
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINE, color="#C4B5FD", size=18),
                            ft.Text("La IA puede equivocarse. Revisa el texto leído antes de generar y comparte solo bromas amables.", color="#CFC4DC", size=12, expand=True),
                        ], spacing=10,
                    ),
                    padding=14, bgcolor="#191321", border_radius=14,
                ),
            ], spacing=14,
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
                ft.Text("Escribe, habla, usa la foto de un objeto o carga un texto para crear bromas con cariño.", size=17, color="#CFC4DC"),
                ft.Container(height=8),
                ft.Row([ft.Icon(ft.Icons.MIC, color="#C4B5FD", size=18), ft.Text("La voz se transcribe antes de enviarla", color=BLANCO, size=14)], spacing=10),
                ft.Row([ft.Icon(ft.Icons.IMAGE, color="#C4B5FD", size=18), ft.Text("La foto puede inspirar las bromas", color=BLANCO, size=14)], spacing=10),
                ft.Row([ft.Icon(ft.Icons.TEXT_FIELDS, color="#C4B5FD", size=18), ft.Text("Lee archivos .txt y texto en fotos", color=BLANCO, size=14)], spacing=10),
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
