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

## Funciones del chat

- Escribe o dicta un mensaje y recibe tres bromas amistosas.
- Adjunta una foto con el botón **+** para inspirar la respuesta.
- Usa **Crear imagen** para generar una ilustración a partir de lo escrito o dictado; también puede usar una foto adjunta como referencia.
- El micrófono graba hasta 30 segundos, con reducción de ruido, cancelación de eco y ajuste automático cuando el dispositivo lo admite.
- El altavoz lee en voz alta el texto del cuadro de mensaje.
- En el menú **+** también puedes cargar un archivo `.txt` o extraer el texto de una foto.

Los audios e imágenes se procesan en línea. La generación de imágenes puede generar un cargo en Google AI Studio. Evita información privada.
