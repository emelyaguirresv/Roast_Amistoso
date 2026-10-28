import os
import json
from pathlib import Path
import httpx

# Empieza por modelos que comprobamos disponibles con la llave de este proyecto.
# Gemini 2.5 queda fuera: Google limita su acceso y puede responder 404 aunque
# aparezca en el listado general de modelos.
MODELOS = []
for candidato in ("gemini-3.6-flash", "gemini-3.5-flash", os.getenv("GEMINI_MODEL", "").strip()):
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
        ultimo_error_transitorio = None
        hubo_timeout = False
        reintentables = {404, 429, 500, 502, 503, 504}
        for modelo in MODELOS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
            try:
                intento = httpx.post(url, timeout=20, headers={"x-goog-api-key": clave}, json=payload)
            except httpx.TimeoutException:
                hubo_timeout = True
                continue
            if intento.status_code == 200 or intento.status_code not in reintentables:
                respuesta = intento
                break
            if intento.status_code != 404:
                ultimo_error_transitorio = intento
        if respuesta is None:
            respuesta = ultimo_error_transitorio
        if respuesta is None:
            if hubo_timeout:
                raise RuntimeError("Gemini tardó demasiado en responder. Inténtalo de nuevo en unos segundos.")
            raise RuntimeError("No encontramos un modelo Gemini disponible para esta llave.")
    except httpx.TimeoutException as exc:
        raise RuntimeError("La conexión tardó demasiado. Inténtalo de nuevo.") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("No pudimos conectar con la IA. Revisa tu conexión.") from exc

    if respuesta.status_code != 200:
        if respuesta.status_code == 404:
            detalle = "Los modelos configurados no están disponibles para esta llave. Actualiza GEMINI_MODEL o crea una llave con acceso a Gemini."
        elif respuesta.status_code == 401:
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
