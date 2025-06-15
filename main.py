import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import requests
import json
import re
from collections import Counter
import time

# Dependencias específicas
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, ColorClip, concatenate_audioclips
import moviepy.video.fx.all as vfx
from moviepy.video.fx.all import fadein, fadeout
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth.exceptions

# Dependencias para AWS y manejo de imágenes
import boto3
import base64

# CONFIGURACIÓN GLOBAL (Valores por defecto)
DEFAULT_CONFIG = {
    # --- Claves de API ---
    "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", "sk_aef90d7653ec7020935fdf4a06ee695b927ba86db5e15334"),
    "PEXELS_API_KEY": os.getenv("PEXELS_API_KEY", "WYgqPYIfZnBRNTEQTBzxKxnil3nzyRTQ9KcQF1bupBaQEshp4sYymvEs"),
    "HUGGINGFACE_API_KEY": os.getenv("HUGGINGFACE_API_KEY", "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"),
    "AWS_ACCESS_KEY_ID": os.getenv("AKIAXV4NFPV3IYOIPUVF", "ozVGleE8HQzjHv48TLh1/nYM7dDkC2QTDnSq8xnv"),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AKIAXV4NFPV3IYOIPUVF", "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"),
    "AWS_REGION_NAME": os.getenv("eu-central-1", "us-east-1"),

    # --- Configuración de Servicios ---
    "VOICE_PROVIDER": "polly",
    "IMAGE_SOURCE": "flux",  # Cambiado a FLUX.1

    # --- Configuración de Voces ---
    "ELEVENLABS_VOICE_ID": "pMsXgVXv3BLzUgSXRplE",
    "POLLY_VOICE_ID": "Lucia",

    # --- Configuración de Modelos de Imagen ---
    "TITAN_MODEL_ID": "amazon.titan-image-generator-v1",

    # --- Configuración de Video y YouTube ---
    "NUM_IMAGES": 12,
    "VIDEO_SIZE": (1920, 1080),
    "FPS": 24,
    "ZOOM_FACTOR": 1.05,
    "ROOT_DIRECTORIES": ["projects", "output"],
    "VIDEO_BITRATE": "8000k",
    "CRF": "16",
    "YOUTUBE_CLIENT_SECRET_FILE": "client_secret.json",
    "YOUTUBE_SCOPES": ["https://www.googleapis.com/auth/youtube.upload"],
    "YOUTUBE_TITLE": "Video Automatizado",
    "YOUTUBE_DESCRIPTION": "Video generado con Python.",
    "YOUTUBE_TAGS": ["python", "automation"],
    "YOUTUBE_CATEGORY": "28",
    "YOUTUBE_PRIVACY": "private",
}

# Configuración del Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
logging.getLogger("moviepy").setLevel(logging.WARNING)

# --- Funciones de Generación de Audio ---

def generate_elevenlabs_audio(text: str, output_path: Path, config: Dict[str, Any]) -> None:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    if "YOUR_ELEVENLABS_API_KEY" in config["ELEVENLABS_API_KEY"]:
        raise ValueError("La clave de API de ElevenLabs no está configurada.")
    client = ElevenLabs(api_key=config["ELEVENLABS_API_KEY"])
    audio = client.text_to_speech.convert(
        voice_id=config["ELEVENLABS_VOICE_ID"],
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.5)
    )
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    logger.info(f"Audio de ElevenLabs generado en {output_path}")

def generate_polly_audio(text: str, output_path: Path, config: Dict[str, Any]) -> None:
    logger.info("Generando audio con Amazon Polly...")
    if "YOUR_AWS_ACCESS_KEY_ID" in config["AWS_ACCESS_KEY_ID"]:
        raise ValueError("Las credenciales de AWS no están configuradas.")
    
    polly_client = boto3.client(
        'polly',
        region_name=config["AWS_REGION_NAME"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"]
    )
    
    # Split text into chunks of less than 2500 characters (before SSML)
    max_length = 2500
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        estimated_ssml_length = len(current_chunk) + len(sentence) + (current_chunk.count('.') + sentence.count('.') + current_chunk.count(',') + sentence.count(',') + current_chunk.count(';') + sentence.count(';')) * 30
        if estimated_ssml_length < max_length:
            current_chunk += sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Generate audio for each chunk with SSML
    temp_audio_files = []
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        try:
            ssml_chunk = chunk.replace('.', '.<break time="500ms"/>')
            ssml_chunk = ssml_chunk.replace(',', ',<break time="250ms"/>')
            ssml_chunk = ssml_chunk.replace(';', ';<break time="300ms"/>')
            ssml_text = f'<speak><prosody rate="80%" pitch="medium">{ssml_chunk}</prosody></speak>'
            logger.info(f"Chunk {i+1}/{len(chunks)} length: {len(chunk)} chars (plain), {len(ssml_text)} chars (SSML)")
            if len(ssml_text) > 3000:
                raise ValueError(f"Chunk {i+1} SSML length ({len(ssml_text)}) exceeds 3000 characters")
            response = polly_client.synthesize_speech(
                Text=ssml_text,
                TextType='ssml',
                OutputFormat='mp3',
                VoiceId=config["POLLY_VOICE_ID"],
                Engine='standard'
            )
            temp_path = output_path.parent / f"temp_polly_{i}.mp3"
            with open(temp_path, 'wb') as f:
                f.write(response['AudioStream'].read())
            temp_audio_files.append(temp_path)
            logger.info(f"Audio de Polly generado para chunk {i+1}/{len(chunks)}")
        except Exception as e:
            logger.error(f"Fallo al generar audio para chunk {i+1}: {e}")
            raise
    
    # Concatenate audio files
    if not temp_audio_files:
        raise ValueError("No se generaron archivos de audio válidos.")
    
    try:
        audio_clips = [AudioFileClip(str(f)) for f in temp_audio_files]
        final_audio = concatenate_audioclips(audio_clips)
        final_audio.write_audiofile(str(output_path), codec="mp3", logger=None)
        final_audio.close()
        for clip in audio_clips:
            clip.close()
        logger.info(f"Audio final de Polly concatenado y guardado en {output_path}")
    except Exception as e:
        logger.error(f"Fallo al concatenar audios: {e}")
        raise
    finally:
        time.sleep(1)
        for temp_file in temp_audio_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.info(f"Archivo temporal {temp_file} eliminado")
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_file}: {e}")

def generate_audio(text: str, output_path: Path, config: Dict[str, Any]) -> None:
    provider = config.get("VOICE_PROVIDER", "elevenlabs")
    logger.info(f"Proveedor de voz seleccionado: {provider}")
    if not text.strip():
        raise ValueError("El texto del guion está vacío.")
    
    try:
        if provider == "polly":
            generate_polly_audio(text, output_path, config)
        elif provider == "elevenlabs":
            generate_elevenlabs_audio(text, output_path, config)
        else:
            raise ValueError(f"Proveedor de voz no soportado: {provider}")
        
        if not output_path.exists() or output_path.stat().st_size < 1000:
            raise ValueError("La generación del archivo de audio falló (archivo vacío o muy pequeño).")
    except Exception as e:
        logger.error(f"Fallo al generar audio con {provider}: {e}")
        raise

# --- Funciones de Generación de Imágenes ---

def generate_pexels_images(query: str, num: int, output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    logger.info(f"Buscando {num} imágenes en Pexels con la consulta: {query}")
    if "YOUR_PEXELS_API_KEY" in config["PEXELS_API_KEY"]:
        raise ValueError("La clave de API de Pexels no está configurada.")
    headers = {"Authorization": config["PEXELS_API_KEY"]}
    params = {"query": query, "per_page": num, "orientation": "landscape", "size": "large"}
    response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=10)
    response.raise_for_status()
    photos = response.json().get("photos", [])
    image_paths = []
    for i, photo in enumerate(photos[:num]):
        img_url = photo["src"]["large2x"]
        img_data = requests.get(img_url, timeout=15).content
        img_path = output_dir / f"imagen_{i:02d}.jpg"
        img_path.write_bytes(img_data)
        logger.info(f"Imagen {i+1} de Pexels guardada en {img_path}")
        image_paths.append(img_path)
    return image_paths

def generate_flux_images(query: str, num: int, output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    logger.info(f"Generando {num} imágenes con FLUX.1 para la consulta: {query}")
    if "YOUR_HUGGINGFACE_API_KEY" in config["HUGGINGFACE_API_KEY"]:
        raise ValueError("La clave de API de Hugging Face no está configurada.")
    api_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev"
    headers = {"Authorization": f"Bearer {config['HUGGINGFACE_API_KEY']}"}
    prompt = f"Ultra-realistic {query}, 4K resolution, cinematic lighting, intricate details, photorealistic textures, 16:9 aspect ratio, dramatic composition"
    image_paths = []
    for i in range(num):
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 100,
                "guidance_scale": 8.5,
                "width": 1920,
                "height": 1080
            }
        }
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        img_data = response.content
        img_path = output_dir / f"imagen_{i:02d}.jpg"
        img_path.write_bytes(img_data)
        logger.info(f"Imagen {i+1} de FLUX guardada en {img_path}")
        image_paths.append(img_path)
    return image_paths

def generate_titan_images(query: str, num: int, output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    logger.info(f"Generando {num} imágenes con Amazon Titan...")
    if "YOUR_AWS_ACCESS_KEY_ID" in config["AWS_ACCESS_KEY_ID"]:
        raise ValueError("Las credenciales de AWS no están configuradas.")
    
    bedrock_runtime = boto3.client(
        'bedrock-runtime',
        region_name=config["AWS_REGION_NAME"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"]
    )
    
    prompt = f"Ultra-realistic photograph of {query}, 4K resolution, cinematic lighting, highly detailed, photorealistic textures, dramatic composition, 16:9 aspect ratio"
    image_paths = []
    for i in range(num):
        body = json.dumps({
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": prompt,
            },
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "height": 1080,
                "width": 1920,
                "cfgScale": 10.0,
                "seed": i
            }
        })
        
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=config["TITAN_MODEL_ID"],
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        base64_image = response_body.get('images')[0]
        image_data = base64.b64decode(base64_image)
        
        img_path = output_dir / f"imagen_{i:02d}.jpg"
        img_path.write_bytes(img_data)
        logger.info(f"Imagen {i+1} de Titan guardada en {img_path}")
        image_paths.append(img_path)
        
    return image_paths

def generate_images(query: str, num: int, output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    source = config.get("IMAGE_SOURCE", "flux")
    logger.info(f"Fuente de imágenes seleccionada: {source}")
    try:
        if source == "titan":
            return generate_titan_images(query, num, output_dir, config)
        elif source == "flux":
            return generate_flux_images(query, num, output_dir, config)
        elif source == "pexels":
            return generate_pexels_images(query, num, output_dir, config)
        else:
            raise ValueError(f"Fuente de imágenes no soportada: {source}")
    except Exception as e:
        logger.error(f"Fallo al generar imágenes con {source}: {e}. Intentando con Pexels como alternativa.")
        if source != "pexels":
            return generate_pexels_images(query, num, output_dir, config)
        else:
            raise

def setup_directories(project_name: str) -> tuple[Path, Path, Path]:
    base_dir = Path("output") / project_name
    audio_dir, images_dir, video_dir = base_dir / "audio", base_dir / "imagenes", base_dir / "video"
    for d in [audio_dir, images_dir, video_dir]: d.mkdir(parents=True, exist_ok=True)
    return audio_dir, images_dir, video_dir

def extract_keywords(text: str) -> str:
    stop_words = {"el","la","los","las","de","en","a","con","por","para","que","y","o","un","una","es","se","al","del","su"}
    words = re.findall(r'\w+', text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 3]
    return " ".join(w for w, c in Counter(keywords).most_common(3)) or "tecnologia"

def load_project_config(project_path: Path) -> Dict[str, Any]:
    config_path = project_path / "config.json"
    final_config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            project_specific_config = json.load(f)
        final_config.update(project_specific_config)
    else:
        logger.warning(f"No se encontró config.json en {project_path}. Usando configuración por defecto.")
    return final_config

def select_projects() -> List[Path]:
    project_dir = Path("projects")
    if not any(project_dir.iterdir()): raise FileNotFoundError("No hay proyectos en la carpeta 'projects'.")
    projects = sorted([d for d in project_dir.iterdir() if d.is_dir()])
    print("Proyectos disponibles:")
    for i, p in enumerate(projects, 1): print(f"{i}. {p.name}")
    selections = input("Selecciona los números de los proyectos (ej: 1 o 1,2): ").strip()
    return [projects[int(i)-1] for i in selections.split(',')]

def create_video(audio_path: Path, image_paths: List[Path], output_path: Path, config: Dict[str, Any]) -> None:
    if not image_paths: raise ValueError("No hay imágenes para crear el video.")
    if not audio_path.exists(): raise FileNotFoundError(f"Audio no encontrado en {audio_path}")
    audio_clip = AudioFileClip(str(audio_path))
    duration_per_image = audio_clip.duration / len(image_paths)
    transition_duration = 1.0  # Duración de solapamiento para fundidos
    clips = []
    
    for i, img_path in enumerate(image_paths):
        # Ajustar duración para incluir solapamiento
        clip_duration = duration_per_image + transition_duration if i < len(image_paths) - 1 else duration_per_image
        img_clip = ImageClip(str(img_path)).set_duration(clip_duration)
        img_resized = img_clip.resize(height=config["VIDEO_SIZE"][1] * 1.1)
        bg = ColorClip(size=config["VIDEO_SIZE"], color=(0,0,0), duration=clip_duration)
        composite = CompositeVideoClip([bg, img_resized.set_position("center")], size=config["VIDEO_SIZE"])
        zoomed = composite.fx(vfx.resize, lambda t: 1 + (t/duration_per_image) * (config["ZOOM_FACTOR"]-1))
        styled = zoomed.fx(vfx.colorx, factor=0.8)  # Look cinematográfico
        # Aplicar fundido de entrada y salida
        final_clip = styled.fx(fadein, transition_duration).fx(fadeout, transition_duration)
        # Ajustar posición temporal para solapamiento
        start_time = i * duration_per_image - (transition_duration if i > 0 else 0)
        final_clip = final_clip.set_start(start_time)
        clips.append(final_clip)
    
    # Combinar clips con solapamiento
    video = CompositeVideoClip(clips, size=config["VIDEO_SIZE"]).set_duration(audio_clip.duration).set_audio(audio_clip)
    video.write_videofile(
        str(output_path),
        fps=config["FPS"],
        codec="libx264",
        audio_codec="aac",
        bitrate=config["VIDEO_BITRATE"],
        preset="veryslow",
        threads=4,
        ffmpeg_params=["-crf", config["CRF"]],
        logger="bar"
    )
    audio_clip.close()
    video.close()
    logger.info("Video generado con éxito.")

def upload_to_youtube(video_path: Path, config: Dict[str, Any]) -> None:
    if not video_path.exists(): raise FileNotFoundError(f"Video no encontrado: {video_path}")
    flow = InstalledAppFlow.from_client_secrets_file(config["YOUTUBE_CLIENT_SECRET_FILE"], config["YOUTUBE_SCOPES"])
    credentials = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=credentials)
    request_body = {
        "snippet": {
            "title": config["YOUTUBE_TITLE"],
            "description": config["YOUTUBE_DESCRIPTION"],
            "tags": config["YOUTUBE_TAGS"],
            "categoryId": config["YOUTUBE_CATEGORY"]
        },
        "status": {"privacyStatus": config["YOUTUBE_PRIVACY"]}
    }
    media_file = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    insert_request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media_file)
    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            logger.info(f"Subido {int(status.progress() * 100)}%")
    logger.info(f"Video subido: http://youtu.be/{response['id']}")

def process_project(project_path: Path) -> None:
    project_name = project_path.stem
    logger.info(f"--- Iniciando procesamiento de {project_name} ---")
    try:
        config = load_project_config(project_path)
        script_file = project_path / "script.txt"
        if not script_file.exists():
            raise FileNotFoundError(f"No se encontró 'script.txt' en {project_name}")
        audio_dir, images_dir, video_dir = setup_directories(project_name)
        with open(script_file, "r", encoding="utf-8") as f:
            text = f.read().strip()
        audio_path = audio_dir / f"{project_name}.mp3"
        video_path = video_dir / f"{project_name}_video.mp4"
        
        generate_audio(text, audio_path, config)
        query = extract_keywords(text)
        image_paths = generate_images(query, config["NUM_IMAGES"], images_dir, config)
        create_video(audio_path, image_paths, video_path, config)
        
        if input(f"¿Subir '{project_name}' a YouTube? (s/n): ").lower() == "s":
            upload_to_youtube(video_path, config)
    except Exception as e:
        logger.error(f"Fallo al procesar {project_name}: {e}")
    finally:
        logger.info(f"--- Procesamiento de {project_name} finalizado ---")

def main():
    try:
        for d in DEFAULT_CONFIG["ROOT_DIRECTORIES"]:
            Path(d).mkdir(exist_ok=True)
        projects = select_projects()
        for p in projects:
            process_project(p)
        logger.info("Todos los proyectos seleccionados han sido procesados.")
    except Exception as e:
        logger.error(f"El programa falló: {e}")

if __name__ == "__main__":
    main()