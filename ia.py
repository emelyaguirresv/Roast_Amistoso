import os
import json
from pathlib import Path
import httpx

# Prueba primero el modelo indicado y luego alternativas actuales.
MODELOS = []
for candidato in (os.getenv("GEMINI_MODEL", "").strip(), "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"):
    if candidato and candidato not in MODELOS:
        MODELOS.append(candidato)


def _leer_clave():
    """Lee la clave del entorno o del archivo local de secretos."""
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if clave:
        return clave
    archivo = Path(__file__).parent / ".streamlit" / "secrets"
    if archivo.is_file():
        return archivo.read_text(encoding="utf-8").strip()
    return ""


def ia(instruccion, texto, como_json=False):
    """Envía instrucción y texto a Gemini; devuelve dict/lista si se solicita JSON."""
    clave = _leer_clave()
    if not clave:
        raise RuntimeError("Falta GEMINI_API_KEY. Agrégala al secreto local del proyecto.")
    cfg = {"responseMimeType": "application/json"} if como_json else {}
    payload = {
        "contents": [{"parts": [{"text": instruccion + "\n\nTexto: " + texto}]}],
        "generationConfig": cfg,
    }
    try:
        respuesta = None
        reintentables = {404, 429, 500, 502, 503, 504}
        for modelo in MODELOS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
            respuesta = httpx.post(url, timeout=35, headers={"x-goog-api-key": clave}, json=payload)
            if respuesta.status_code not in reintentables:
                break
        if respuesta is None or respuesta.status_code == 404:
            raise RuntimeError("No encontramos un modelo Gemini disponible para esta llave.")
    except httpx.TimeoutException as exc:
        raise RuntimeError("La conexión tardó demasiado. Inténtalo de nuevo.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("No pudimos conectar con la IA. Revisa tu conexión.") from exc

    if respuesta.status_code != 200:
        if respuesta.status_code == 401:
            detalle = "Gemini rechazó la llave (401). Crea una llave nueva en AI Studio y reemplaza el contenido de .streamlit/secrets."
        elif respuesta.status_code in (400, 403):
            detalle = "La llave o el acceso a Gemini no son válidos. Revisa el secreto de AI Studio."
        elif respuesta.status_code == 429:
            detalle = "La IA alcanzó su cuota en todos los modelos disponibles. Espera un momento e inténtalo de nuevo."
        elif respuesta.status_code in (500, 502, 503, 504):
            detalle = "Los modelos de Gemini están temporalmente ocupados. Espera un momento e inténtalo de nuevo."
        else:
            detalle = f"La IA respondió con un error ({respuesta.status_code}). Inténtalo de nuevo."
        raise RuntimeError(detalle)

    try:
        texto_respuesta = respuesta.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("La IA devolvió una respuesta incompleta. Inténtalo otra vez.") from exc
    if como_json:
        texto_respuesta = texto_respuesta.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(texto_respuesta)
        except json.JSONDecodeError as exc:
            raise RuntimeError("La IA devolvió un formato inesperado. Inténtalo otra vez.") from exc
    return texto_respuesta
