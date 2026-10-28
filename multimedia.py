import base64
import io
import json
import os
import tempfile
import wave

import edge_tts
import httpx
from google import genai

from ia import MODELOS, _leer_clave

MAX_ARCHIVO = 15_000_000


def pcm_a_wav(pcm: bytes, tasa: int = 44100, canales: int = 1) -> bytes:
    """Empaqueta los fragmentos PCM16 del micrófono en un WAV válido."""
    if not pcm:
        raise RuntimeError("No se recibió audio. Habla un momento e inténtalo de nuevo.")
    salida = io.BytesIO()
    with wave.open(salida, "wb") as archivo:
        archivo.setnchannels(canales)
        archivo.setsampwidth(2)
        archivo.setframerate(tasa)
        archivo.writeframes(pcm)
    return salida.getvalue()


def _error_api(exc):
    for valor in (
        getattr(exc, "code", None),
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        try:
            if valor is not None:
                return int(valor)
        except (TypeError, ValueError):
            pass
    return None


def _validar_archivo(datos: bytes, mime: str):
    if not datos:
        raise RuntimeError("El archivo está vacío. Elige otro e inténtalo de nuevo.")
    if len(datos) > MAX_ARCHIVO:
        raise RuntimeError("El archivo supera 15 MB. Elige uno más pequeño.")
    if mime not in {"image/jpeg", "image/png", "image/webp", "audio/wav"}:
        raise RuntimeError("Formato no compatible. Usa JPG, PNG, WEBP o WAV.")


def ia_media(instruccion, datos: bytes, mime: str, texto: str = "", como_json: bool = False):
    """Envía una imagen a Gemini usando la llave guardada localmente."""
    clave = _leer_clave()
    if not clave:
        raise RuntimeError("Falta una llave de Google AI Studio en GEMINI_API_KEY.")
    _validar_archivo(datos, mime)
    pedido = instruccion + ("\n\nMensaje del usuario: " + texto if texto.strip() else "")
    cuerpo = {
        "contents": [{"parts": [
            {"text": pedido},
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(datos).decode("ascii")}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json"} if como_json else {},
    }
    respuesta = None
    try:
        reintentables = {404, 429, 500, 502, 503, 504}
        for modelo in MODELOS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
            respuesta = httpx.post(url, timeout=60, headers={"x-goog-api-key": clave}, json=cuerpo)
            if respuesta.status_code not in reintentables:
                break
    except httpx.TimeoutException as exc:
        raise RuntimeError("Gemini tardó demasiado. Inténtalo de nuevo.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("No pudimos conectar con Gemini. Revisa internet.") from exc

    if respuesta is None or respuesta.status_code == 404:
        raise RuntimeError("No hay un modelo de Gemini disponible para esta llave.")
    if respuesta.status_code != 200:
        if respuesta.status_code == 401:
            detalle = "La llave de Google AI Studio fue rechazada (401). Revisa GEMINI_API_KEY."
        elif respuesta.status_code == 403:
            detalle = "Google no autorizó esta llave o este modelo. Revisa el acceso en AI Studio."
        elif respuesta.status_code == 429:
            detalle = "Gemini alcanzó su límite en todos los modelos disponibles. Espera un poco e inténtalo de nuevo."
        elif respuesta.status_code in (500, 502, 503, 504):
            detalle = "Los modelos de Gemini están temporalmente ocupados. Inténtalo otra vez en un momento."
        else:
            detalle = f"Gemini respondió con un error ({respuesta.status_code}). Inténtalo de nuevo."
        raise RuntimeError(detalle)

    try:
        partes = respuesta.json()["candidates"][0]["content"]["parts"]
        texto_respuesta = "\n".join(p["text"] for p in partes if isinstance(p, dict) and p.get("text"))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("Gemini devolvió una respuesta incompleta.") from exc
    if not texto_respuesta.strip():
        raise RuntimeError("Gemini no devolvió texto. Inténtalo con otra imagen.")
    if como_json:
        texto_respuesta = texto_respuesta.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(texto_respuesta)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini devolvió un formato inesperado. Inténtalo otra vez.") from exc
    return texto_respuesta.strip()


def transcribir_audio(datos: bytes, instruccion: str = "", mime: str = "audio/wav") -> str:
    """Transcribe con Gemini 3.5 Transcribe y detección automática del idioma."""
    clave = _leer_clave()
    if not clave:
        raise RuntimeError("Falta una llave de Google AI Studio en GEMINI_API_KEY.")
    if not datos:
        raise RuntimeError("No se recibió audio. Habla un momento e inténtalo de nuevo.")
    if len(datos) > MAX_ARCHIVO:
        raise RuntimeError("El audio es demasiado grande. Graba una frase más corta.")
    extensiones = {"audio/wav": ".wav", "audio/mp3": ".mp3", "audio/mpeg": ".mp3"}
    if mime not in extensiones:
        raise RuntimeError("Formato de audio no compatible.")

    cliente = genai.Client(api_key=clave)
    ruta_local = None
    archivo_remoto = None
    try:
        with tempfile.NamedTemporaryFile(suffix=extensiones[mime], delete=False) as temporal:
            temporal.write(datos)
            ruta_local = temporal.name
        archivo_remoto = cliente.files.upload(file=ruta_local)
        interaccion = cliente.interactions.create(
            model="gemini-3.5-transcribe",
            input=[{
                "type": "audio",
                "uri": archivo_remoto.uri,
                "mime_type": archivo_remoto.mime_type or mime,
            }],
            generation_config={
                "transcription_config": {
                    "mode": "smart",
                    "language_codes": [],
                }
            },
        )
        resultado = (interaccion.output_text or "").strip()
        if not resultado:
            raise RuntimeError("No se entendió la voz. Habla cerca del micrófono y con menos ruido.")
        return resultado
    except RuntimeError:
        raise
    except Exception as exc:
        codigo = _error_api(exc)
        if codigo == 401:
            raise RuntimeError("Google rechazó la llave (401). Revisa la llave GEMINI_API_KEY de AI Studio.") from exc
        if codigo == 403:
            raise RuntimeError("Google no autorizó la transcripción. Revisa el acceso de la llave en AI Studio.") from exc
        if codigo in (404, 501) and mime == "audio/wav":
            return ia_media(instruccion or "Transcribe literalmente el audio.", datos, "audio/wav")
        raise RuntimeError("No pudimos transcribir el audio. Revisa la conexión y vuelve a intentarlo.") from exc
    finally:
        if archivo_remoto is not None:
            try:
                cliente.files.delete(name=archivo_remoto.name)
            except Exception:
                pass
        if ruta_local and os.path.exists(ruta_local):
            os.remove(ruta_local)
        cliente.close()

def generar_imagen(prompt: str, imagen_referencia: bytes | None = None, mime: str = "image/jpeg") -> tuple[bytes, str]:
    """Genera una ilustración con Gemini y, opcionalmente, una foto de referencia."""
    clave = _leer_clave()
    if not clave:
        raise RuntimeError("Falta una llave de Google AI Studio en GEMINI_API_KEY.")
    prompt = prompt.strip()
    if not prompt:
        raise RuntimeError("Escribe o dicta una idea antes de crear la imagen.")
    if len(prompt) > 4000:
        raise RuntimeError("La idea supera 4000 caracteres. Acórtala e inténtalo de nuevo.")
    if imagen_referencia:
        _validar_archivo(imagen_referencia, mime)
        entrada = [
            {"type": "text", "text": "Crea una ilustración original basada en esta idea. Usa la foto adjunta solo como referencia visual y conserva un tono amistoso. No agregues texto a la imagen salvo que el usuario lo solicite. Idea: " + prompt},
            {"type": "image", "data": base64.b64encode(imagen_referencia).decode("ascii"), "mime_type": mime},
        ]
    else:
        entrada = "Crea una ilustración original, amistosa y visualmente atractiva basada en esta idea. No agregues texto salvo que el usuario lo solicite. Idea: " + prompt

    cliente = genai.Client(api_key=clave)
    try:
        ultimo_error = None
        interaccion = None
        for modelo in ("gemini-nano-banana-2.1", "gemini-3.1-flash-lite-image", "gemini-2.5-flash-image"):
            try:
                interaccion = cliente.interactions.create(
                    model=modelo,
                    input=entrada,
                    response_format={
                        "type": "image",
                        "mime_type": "image/png",
                        "aspect_ratio": "1:1",
                        "image_size": "1K",
                    },
                )
                break
            except Exception as exc:
                ultimo_error = exc
                if _error_api(exc) not in (404, 500, 502, 503, 504):
                    raise
        if interaccion is None:
            raise ultimo_error or RuntimeError("No hay un modelo de imágenes disponible.")
        salida = getattr(interaccion, "output_image", None)
        data = getattr(salida, "data", None) if salida else None
        mime_salida = getattr(salida, "mime_type", None) or "image/png"
        if not data:
            raise RuntimeError("El modelo terminó, pero no devolvió una imagen. Prueba con otra descripción.")
        try:
            return base64.b64decode(data), mime_salida
        except (ValueError, TypeError) as exc:
            raise RuntimeError("No pudimos abrir la imagen que generó Gemini.") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        codigo = _error_api(exc)
        if codigo == 401:
            raise RuntimeError("Google rechazó la llave (401). Revisa la llave GEMINI_API_KEY de AI Studio.") from exc
        if codigo == 403:
            raise RuntimeError("Google no autorizó la generación de imágenes para esta llave.") from exc
        if codigo == 429:
            raise RuntimeError("Gemini alcanzó su límite de generación. Espera un poco e inténtalo de nuevo.") from exc
        raise RuntimeError("No pudimos crear la imagen. Revisa tu conexión y vuelve a intentarlo.") from exc
    finally:
        cliente.close()


async def sintetizar_voz(texto: str) -> bytes:
    """Crea una lectura natural en español latino y devuelve audio MP3."""
    texto = texto.strip()
    if not texto:
        raise RuntimeError("No hay texto para leer en voz alta.")
    if len(texto) > 4000:
        raise RuntimeError("El texto supera 4000 caracteres. Acórtalo antes de escucharlo.")
    comunicador = edge_tts.Communicate(text=texto, voice="es-MX-DaliaNeural", rate="+0%", volume="+0%")
    partes = []
    try:
        async for fragmento in comunicador.stream():
            if fragmento["type"] == "audio":
                partes.append(fragmento["data"])
    except Exception as exc:
        raise RuntimeError("No se pudo generar la voz. Revisa internet e inténtalo de nuevo.") from exc
    audio = b"".join(partes)
    if not audio:
        raise RuntimeError("El servicio de voz no generó audio. Inténtalo de nuevo.")
    return audio
