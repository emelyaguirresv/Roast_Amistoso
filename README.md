---
title: Roast amistoso
emoji: 💜
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
---

# Roast amistoso

Mini app en Python y Flet que genera tres bromas ligeras para compartir entre amigos usando Gemini.

## Ejecutar en Windows

1. Instala Python 3.13.
2. En PowerShell, abre esta carpeta y ejecuta:

   ```powershell
   py -m pip install -r requirements.txt
   py main.py
   ```

3. Abre la dirección local que muestra Flet. La llave local se lee de `.streamlit/secrets` o de la variable `GEMINI_API_KEY`.

## Publicar para usar desde el celular

Crea un Space de tipo **Docker** en Hugging Face, sube estos archivos y agrega `GEMINI_API_KEY` en **Settings → Variables and secrets → Secrets**. El secreto no se agrega al código ni a GitHub. Cuando el Space esté en estado **Running**, abre su enlace `https://...hf.space` desde el celular.

La app escucha el puerto `PORT` que define el alojamiento y no requiere permisos especiales del celular.

## Entradas disponibles

- Voz en español: graba hasta 30 segundos, transcribe y deja el texto listo para revisar.
- Foto de un objeto: Gemini la usa como inspiración para las bromas.
- Archivo `.txt`: carga el texto para revisarlo antes de generar.
- Lectura de texto en foto: extrae el texto visible y lo coloca en el campo para que puedas revisarlo.

No subas fotos de personas ni información privada. En un celular, el micrófono requiere un enlace HTTPS; la dirección local `127.0.0.1` solo funciona en la computadora donde corre la app.
