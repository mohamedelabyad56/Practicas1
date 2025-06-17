Pipeline de Automatización de Vídeos 🎥

Un pipeline en Python para crear vídeos documentales históricos de forma automática. Genera narraciones en español con Amazon Polly, imágenes fotorrealistas con Hugging Face FLUX.1, monta vídeos con MoviePy y los sube a YouTube. Ideal para creadores de contenido educativo sobre temas como la Unión Soviética o la Antigua Roma.
Índice

Descripción del Proyecto
Por Qué Destaca
Características
Tecnologías
Requisitos Previos
Instalación
Configuración
Uso
Estructura del Proyecto
Ejemplos de Proyectos
Solución de Problemas
Contribuir
Licencia
Agradecimientos

Descripción del Proyecto
El Pipeline de Automatización de Vídeos permite crear documentales educativos de alta calidad con mínima intervención manual. Convierte guiones de texto en vídeos narrados en español, con imágenes generadas por IA y montaje profesional, listos para subir a YouTube. Incluye proyectos como un documental de 15 minutos sobre la Unión Soviética y un resumen de 3 minutos sobre la Antigua Roma.
Por Qué Destaca
Este pipeline es una herramienta innovadora para creadores de contenido:

Eficiencia: Genera vídeos en horas, no días, automatizando narración, imágenes y montaje.
Calidad: Usa FLUX.1 para imágenes en 4K y la voz Lucia de Polly para narraciones naturales en español.
Flexibilidad: Permite personalizar guiones y configuraciones para cualquier tema histórico.
Escalabilidad: Su diseño modular facilita añadir nuevos proyectos.Como Grok, creo que este proyecto demuestra el poder de la IA para democratizar la creación de contenido, aunque requiere inversión en APIs de pago (Hugging Face, AWS).

Características

Narración en español con Amazon Polly (voz Lucia).
Imágenes fotorrealistas generadas con Hugging Face FLUX.1.
Montaje de vídeos con MoviePy, con efectos de zoom y transiciones.
Subida automática a YouTube con metadatos personalizables.
Gestión robusta de errores con reintentos y validación de MP3 (>1KB).
Estructura modular con guiones y configuraciones por proyecto.
Soporte para guiones largos (~15 minutos) con segmentación para Polly.

Tecnologías

Python: 3.8+ para la lógica principal.
Amazon Polly: Texto a voz para narraciones en español.
Hugging Face FLUX.1: Generación de imágenes con IA.
MoviePy: Edición y montaje de vídeos.
Google YouTube API: Subida de vídeos.
Librerías: boto3, requests, elevenlabs, google-auth-oauthlib, retrying, python-dotenv.

Requisitos Previos

Python 3.8+: Descargar aquí.
Git: Para clonar el repositorio.
Claves de API:
AWS (Polly): Consola AWS.
Hugging Face (FLUX.1): Hugging Face (plan Pro/Enterprise recomendado).
Google (YouTube API): Consola Google Cloud.


Sistema: Windows (probado), Linux o macOS.
Hardware: 8GB+ de RAM, conexión estable a internet para APIs.

Instalación
Clona el repositorio y configura un entorno virtual desde la terminal.
# Clonar el repositorio
git clone https://github.com/tu-usuario/video-automation-pipeline.git
cd video-automation-pipeline

# Crear y activar entorno virtual (Windows)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install --upgrade boto3 requests moviepy elevenlabs google-auth-oauthlib google-api-python-client retrying python-dotenv

Para Linux/macOS:
source venv/bin/activate

Configuración

Crear .env:Copia .env.example a .env y añade tus claves de API:
copy .env.example .env  # Windows
cp .env.example .env    # Linux/macOS

Edita .env:
AWS_ACCESS_KEY_ID=tu_clave_aws
AWS_SECRET_ACCESS_KEY=tu_secreto_aws
HUGGINGFACE_API_KEY=hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
ELEVENLABS_API_KEY=tu_clave_elevenlabs
GOOGLE_CLIENT_SECRET=tu_secreto_google


Obtener Claves de API:

AWS: Crea un usuario IAM con permisos para Polly en Consola AWS.
Hugging Face: Genera un token en Ajustes de Hugging Face. Necesitas un plan de pago (Pro/Enterprise) para FLUX.1.
Google: Configura un proyecto de YouTube API en Consola Google Cloud y descarga client_secret.json.


Proteger .env:Asegúrate de que .gitignore incluya .env:
echo ".env" >> .gitignore

Restringe permisos (Windows):
icacls .env /inheritance:r /grant:r "%username%:F"



Uso

Crear un Proyecto:Añade un directorio en projects/ con script.txt y config.json. Ejemplo para SovietUnion15Min:
mkdir projects\SovietUnion15Min


script.txt: Guion de ~15 minutos con marcadores --- CHUNK SPLIT FOR POLLY ---.
config.json: Configuraciones como NUM_IMAGES y metadatos de YouTube.


Ejecutar el Pipeline:Corre main.py desde la terminal:
python main.py


Selecciona el proyecto (por ejemplo, SovietUnion15Min con su número, como 8).
El script:
Genera audio (output/SovietUnion15Min/audio/SovietUnion15Min.mp3).
Crea 30 imágenes con FLUX.1 (output/SovietUnion15Min/images/).
Monta el vídeo (output/SovietUnion15Min/video/SovietUnion15Min_video.mp4).
Pregunta si quieres subir a YouTube (responde s para subir).




Verificar Salida:Comprueba los archivos generados:
dir output\SovietUnion15Min\audio\SovietUnion15Min.mp3
dir output\SovietUnion15Min\video\SovietUnion15Min_video.mp4
dir output\SovietUnion15Min\images\*.jpg



Estructura del Proyecto
video-automation-pipeline/
├── main.py                # Script principal del pipeline
├── .env                   # Claves de API (no rastreado)
├── .gitignore             # Excluye archivos sensibles
├── projects/              # Directorios de proyectos
│   ├── SovietUnion15Min/
│   │   ├── script.txt     # Guion de 15 minutos
│   │   ├── config.json    # Configuraciones del proyecto
│   ├── Roma2/
│   │   ├── script.txt     # Guion de 3 minutos
│   │   ├── config.json    # Configuraciones del proyecto
├── output/                # Archivos generados
│   ├── SovietUnion15Min/
│   │   ├── audio/         # Archivos MP3
│   │   ├── images/        # Imágenes JPG
│   │   ├── video/         # Vídeos MP4

Ejemplos de Proyectos

SovietUnion15Min: Documental de 15 minutos sobre el ascenso y caída de la Unión Soviética, con 30 imágenes de FLUX.1.
Guion: Cubre la Revolución de 1917, Stalin, Guerra Fría y colapso de 1991.
Config: NUM_IMAGES: 30, título de YouTube: "La Unión Soviética: Ascenso y Caída en 15 Minutos".


Roma2: Resumen de 3 minutos sobre la Antigua Roma, con 30 imágenes.
Guion: Trata sobre Rómulo, la República, el Imperio y su caída.
Config: Título de YouTube: "La Antigua Roma: El Ascenso y Caída de un Imperio - v2".



Solución de Problemas

Error: 402 Client Error: Payment Required:
Causa: FLUX.1 requiere un plan de pago en Hugging Face.
Solución: Actualiza a Pro/Enterprise en Precios de Hugging Face o verifica tu HUGGINGFACE_API_KEY.
Prueba la API:python -c "import requests; headers={'Authorization': 'Bearer %HUGGINGFACE_API_KEY%'}; print(requests.post('https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev', headers=headers, json={'inputs': 'Ciudad de la Unión Soviética'}, timeout=60).status_code)"




Error: Hugging Face API key no configurada:
Causa: HUGGINGFACE_API_KEY vacío en .env.
Solución: Añade una clave válida desde Ajustes de Hugging Face.


Error: MP3 demasiado pequeño:
Causa: Audio corrupto (<1KB).
Solución: Verifica credenciales de AWS y permisos de Polly.


Generación de Imágenes Lenta: 30 imágenes pueden tardar ~30–60 minutos. Reduce NUM_IMAGES en config.json (por ejemplo, a 12).

Contribuir
¡Las contribuciones son bienvenidas! Para colaborar:

Haz un fork del repositorio.
Crea una rama para tu funcionalidad (git checkout -b funcionalidad/tu-funcionalidad).
Confirma los cambios (git commit -m "Añadir tu funcionalidad").
Sube la rama (git push origin funcionalidad/tu-funcionalidad).
Abre un Pull Request.

Sigue el Código de Conducta y reporta problemas en Issues de GitHub.
Licencia
Este proyecto está bajo la Licencia MIT. Consulta LICENSE para más detalles.
Agradecimientos

Amazon Polly por la narración natural.
Hugging Face FLUX.1 por imágenes fotorrealistas.
MoviePy por la edición de vídeos.