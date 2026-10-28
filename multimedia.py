import base64
import io
import json
import wave

import httpx

from ia import MODELOS, _leer_clave

MAX_ARCHIVO = 15_000_000


def pcm_a_wav(pcm: bytes, tasa: int = 16000, canales: int = 1) -> bytes:
    """Empaqueta los fragmentos PCM16 del micrófono en un WAV válido."""
    if not pcm:
        raise RuntimeError("No se recibió audio. Graba una frase e inténtalo otra vez.")
    salida = io.BytesIO()
    with wave.open(salida, "wb") as archivo:
        archivo.setnchannels(canales)
        archivo.setsampwidth(2)
        archivo.setframerate(tasa)
        archivo.writeframes(pcm)
    return salida.getvalue()


def ia_media(instruccion, datos: bytes, mime: str, texto: str = "", como_json: bool = False):
    """Envía una imagen o un audio a Gemini usando la misma llave segura de ia.py."""
    clave = _leer_clave()
    if not clave:
        raise RuntimeError("Falta la llave de Gemini. Agrégala como secreto GEMINI_API_KEY.")
    if not datos:
        raise RuntimeError("El archivo está vacío. Elige otro e inténtalo de nuevo.")
    if len(datos) > MAX_ARCHIVO:
        raise RuntimeError("El archivo supera 15 MB. Elige una imagen más pequeña o un audio más corto.")
    if mime not in {"image/jpeg", "image/png", "image/webp", "audio/wav"}:
        raise RuntimeError("Formato no compatible. Usa JPG, PNG, WEBP o WAV.")

    pedido = instruccion + ("\n\nTexto adicional: " + texto if texto.strip() else "")
    partes = [
        {"text": pedido},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(datos).decode("ascii")}},
    ]
    configuracion = {"responseMimeType": "application/json"} if como_json else {}
    cuerpo = {"contents": [{"parts": partes}], "generationConfig": configuracion}
    respuesta = None
    try:
        for modelo in MODELOS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
            respuesta = httpx.post(url, timeout=60, headers={"x-goog-api-key": clave}, json=cuerpo)
            if respuesta.status_code != 404:
                break
    except httpx.TimeoutException as exc:
        raise RuntimeError("La conexión tardó demasiado. Inténtalo de nuevo.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("No pudimos conectar con Gemini. Revisa la conexión a internet.") from exc

    if respuesta is None or respuesta.status_code == 404:
        raise RuntimeError("No encontramos un modelo Gemini disponible para esta llave.")
    if respuesta.status_code != 200:
        if respuesta.status_code == 401:
            detalle = "Gemini rechazó la llave (401). Reemplázala por una llave válida en el secreto GEMINI_API_KEY."
        elif respuesta.status_code in (400, 403):
            detalle = "Gemini rechazó la llave, el formato del archivo o el acceso al modelo."
        elif respuesta.status_code == 429:
            detalle = "Gemini alcanzó su cuota por ahora. Espera un momento e inténtalo de nuevo."
        else:
            detalle = f"Gemini respondió con un error ({respuesta.status_code}). Inténtalo de nuevo."
        raise RuntimeError(detalle)

    try:
        texto_respuesta = respuesta.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("Gemini devolvió una respuesta incompleta.") from exc
    if como_json:
        texto_respuesta = texto_respuesta.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(texto_respuesta)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini devolvió un formato inesperado. Inténtalo otra vez.") from exc
    return texto_respuesta
