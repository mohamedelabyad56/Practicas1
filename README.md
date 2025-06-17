# 🎬 Video Automation Pipeline con Python, AWS y Hugging Face

Este proyecto automatiza la creación de vídeos narrados en español utilizando datos de actualidad. Usa IA para generar imágenes, narraciones, montaje de vídeo y subida a YouTube. Ideal para canales automatizados o contenido informativo.

---

## 🚀 Descripción del Proyecto

Este pipeline realiza todo el proceso desde un **prompt** hasta la **subida automática del vídeo** a YouTube:

1. 🧠 Se crea un texto basado en un tema.
2. 🖼️ Se generan imágenes con **Hugging Face**.
3. 🔊 Se narra el texto con **Amazon Polly**.
4. 🎞️ Se montan vídeo + audio con **MoviePy**.
5. 📤 Se sube el vídeo a **YouTube automáticamente**.

---

## 🌟 Por Qué Destaca

- Automatización total de contenido
- Soporte multilingüe (configurable)
- Código limpio y modular
- Soporte para YouTube API

---

## 🛠️ Características

- ✅ Generación de texto desde prompt
- ✅ Narración natural en español (voz femenina o masculina)
- ✅ Imágenes fotorrealistas por bloque de texto
- ✅ Sincronización automática voz + imagen
- ✅ Renderizado final con título dinámico
- ✅ Subida a YouTube con título, descripción y miniatura

---

## 🧪 Tecnologías

| Herramienta        | Uso                            |
|--------------------|---------------------------------|
| Python 3.8+        | Lógica del pipeline             |
| Amazon Polly       | Narración por voz               |
| Hugging Face       | Generación de imágenes (diffusion) |
| MoviePy            | Edición de vídeo                |
| YouTube Data API   | Subida de vídeos                |
| dotenv             | Gestión de variables de entorno |

---

## ⚙️ Requisitos Previos

- Cuenta de AWS con acceso a **Amazon Polly**
- Cuenta de Hugging Face con una API key válida
- Cuenta de Google con acceso a la **YouTube Data API**
- Python 3.8 o superior

---

## 📦 Instalación

```bash
git clone https://github.com/tu-usuario/video-automation-pipeline.git
cd video-automation-pipeline
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
