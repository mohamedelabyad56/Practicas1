import os
import logging
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter
from retrying import retry
import requests
import boto3
import base64
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, ColorClip, concatenate_audioclips
import moviepy.video.fx.all as vfx
from moviepy.video.fx.all import fadein, fadeout
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth.exceptions

# CONFIGURACIÓN GLOBAL
DEFAULT_CONFIG = {
    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "AWS_REGION_NAME": "us-east-1",
    "VOICE_PROVIDER": "polly",
    "POLLY_VOICE_ID": "Lucia",
    "IMAGE_SOURCE": "pexels",
    "HUGGINGFACE_API_KEY": os.getenv("HUGGINGFACE_API_KEY", ""),
    "PEXELS_API_KEY": os.getenv("PEXELS_API_KEY", "WYgqPYIfZnBRNTEQTBzxKxnil3nzyRTQ9KcQF1bupBaQEshp4sYymvEs"),
    "TITAN_MODEL_ID": "amazon.titan-image-generator-v1",
    "NUM_IMAGES": 12,
    "VIDEO_SIZE": (1920, 1080),
    "FPS": 24,
    "ZOOM_FACTOR": 1.05,
    "VIDEO_BITRATE": "8000k",
    "CRF": "16",
    "ROOT_DIRECTORIES": ["projects", "output"],
    "YOUTUBE_CLIENT_SECRET_FILE": "client_secret.json",
    "YOUTUBE_SCOPES": ["https://www.googleapis.com/auth/youtube.upload"],
    "YOUTUBE_TITLE": "Video Automatizado",
    "YOUTUBE_DESCRIPTION": "Video generado con Python.",
    "YOUTUBE_TAGS": ["python", "automation"],
    "YOUTUBE_CATEGORY": "28",
    "YOUTUBE_PRIVACY": "private",
}

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)
logging.getLogger("moviepy").setLevel(logging.WARNING)

# --- Funciones de Generación de Audio ---

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def generate_elevenlabs_audio(text: str, output_path: Path, config: Dict[str, Any]) -> None:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    if not config["ELEVENLABS_API_KEY"]:
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
    if output_path.stat().st_size < 1000:
        raise ValueError("Archivo MP3 de ElevenLabs demasiado pequeño.")
    logger.info(f"Audio de ElevenLabs generado en {output_path}")

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def generate_polly_audio(text: str, output_path: Path, config: Dict[str, Any]) -> None:
    logger.info("Generando audio con Amazon Polly...")
    if not config["AWS_ACCESS_KEY_ID"] or not config["AWS_SECRET_ACCESS_KEY"]:
        raise ValueError("Las credenciales de AWS no están configuradas.")
    
    polly_client = boto3.client(
        'polly',
        region_name=config["AWS_REGION_NAME"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"]
    )
    
    chunk_marker = "--- CHUNK SPLIT FOR POLLY ---"
    if chunk_marker in text:
        chunks = [chunk.strip() for chunk in text.split(chunk_marker) if chunk.strip()]
    else:
        max_length = 2500
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            estimated_ssml_length = len(current_chunk) + len(sentence) + (
                current_chunk.count('.') + sentence.count('.') + 
                current_chunk.count(',') + sentence.count(',') + 
                current_chunk.count(';') + sentence.count(';')
            ) * 30
            if estimated_ssml_length < max_length:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        if current_chunk:
            chunks.append(current_chunk.strip())
    
    temp_audio_files = []
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        try:
            ssml_chunk = chunk.replace('.', '.<break time="500ms"/>')
            ssml_chunk = ssml_chunk.replace(',', ',<break time="250ms"/>')
            ssml_chunk = ssml_chunk.replace(';', ';<break time="300ms"/>')
            ssml_text = f'<speak><prosody rate="80%" pitch="medium">{ssml_chunk}</prosody></speak>'
            logger.info(f"Chunk {i+1}/{len(chunks)}: {len(chunk)} chars (plain), {len(ssml_text)} chars (SSML)")
            if len(ssml_text) > 3000:
                raise ValueError(f"Chunk {i+1} SSML exceeds 3000 chars")
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
            if temp_path.stat().st_size < 1000:
                raise ValueError(f"Archivo MP3 temporal {temp_path} demasiado pequeño.")
            temp_audio_files.append(temp_path)
            logger.info(f"Audio chunk {i+1}/{len(chunks)} generado")
        except Exception as e:
            logger.error(f"Fallo en chunk {i+1}: {e}")
            raise
    
    if not temp_audio_files:
        raise ValueError("No se generaron audios válidos.")
    
    try:
        audio_clips = [AudioFileClip(str(f)) for f in temp_audio_files]
        final_audio = concatenate_audioclips(audio_clips)
        final_audio.write_audiofile(str(output_path), codec="mp3", bitrate="192k", logger=None)
        if output_path.stat().st_size < 1000:
            raise ValueError("Archivo MP3 final demasiado pequeño.")
        logger.info(f"Audio final guardado en {output_path}")
    except Exception as e:
        logger.error(f"Fallo al concatenar audios: {e}")
        raise
    finally:
        for clip in audio_clips:
            clip.close()
        final_audio.close()
        for temp_file in temp_audio_files:
            if temp_file.exists():
                temp_file.unlink()
                logger.info(f"Eliminado {temp_file}")

def generate_audio(text: str, output_path: Path, config: Dict[str, Any]) -> None:
    provider = config.get("VOICE_PROVIDER", "polly")
    logger.info(f"Usando proveedor de voz: {provider}")
    if not text.strip():
        raise ValueError("El texto del guion está vacío.")
    if provider == "polly":
        generate_polly_audio(text, output_path, config)
    elif provider == "elevenlabs":
        generate_elevenlabs_audio(text, output_path, config)
    else:
        raise ValueError(f"Proveedor de voz no soportado: {provider}")

# --- Funciones de Generación de Imágenes ---

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def generate_pexels_images(prompts: List[str], output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    logger.info(f"Buscando {len(prompts)} imágenes en Pexels")
    if not config["PEXELS_API_KEY"]:
        raise ValueError("La clave de API de Pexels no está configurada.")
    headers = {"Authorization": config["PEXELS_API_KEY"]}
    image_paths = []
    for i, prompt in enumerate(prompts):
        params = {"query": prompt, "per_page": 1, "orientation": "landscape", "size": "large"}
        try:
            response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=10)
            response.raise_for_status()
            photos = response.json().get("photos", [])
            if photos:
                img_url = photos[0]["src"]["large2x"]
                img_data = requests.get(img_url, timeout=15).content
                img_path = output_dir / f"image_{i+1:02d}.jpg"
                img_path.write_bytes(img_data)
                image_paths.append(img_path)
                logger.info(f"Imagen {i+1} de Pexels guardada: {img_path}")
            else:
                logger.warning(f"No se encontraron imágenes en Pexels para: {prompt}")
        except Exception as e:
            logger.error(f"Fallo en Pexels para prompt {prompt}: {e}")
    return image_paths

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def generate_flux_images(prompts: List[str], output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    logger.info(f"Generando {len(prompts)} imágenes con FLUX.1")
    if not config["HUGGINGFACE_API_KEY"]:
        raise ValueError("Hugging Face API key no configurada.")
    api_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev"
    headers = {"Authorization": f"Bearer {config['HUGGINGFACE_API_KEY']}"}
    image_paths = []
    for i, prompt in enumerate(prompts):
        enhanced_prompt = f"Ultra-realistic {prompt}, 4K resolution, cinematic lighting, intricate details, photorealistic textures, 16:9 aspect ratio"
        payload = {
            "inputs": enhanced_prompt,
            "parameters": {
                "num_inference_steps": 50,
                "guidance_scale": 7.5,
                "width": 1920,
                "height": 1080
            }
        }
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            img_data = response.content
            img_path = output_dir / f"image_{i+1:02d}.jpg"
            img_path.write_bytes(img_data)
            image_paths.append(img_path)
            logger.info(f"Imagen {i+1} de FLUX.1 guardada: {img_path}")
        except requests.RequestException as e:
            logger.error(f"Fallo en FLUX.1 para prompt {prompt}: {e}")
            raise
    return image_paths

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def generate_titan_images(prompts: List[str], output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    logger.info(f"Generando {len(prompts)} imágenes con Amazon Titan")
    if not config["AWS_ACCESS_KEY_ID"] or not config["AWS_SECRET_ACCESS_KEY"]:
        raise ValueError("Las credenciales de AWS no están configuradas.")
    bedrock_runtime = boto3.client(
        'bedrock-runtime',
        region_name=config["AWS_REGION_NAME"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"]
    )
    image_paths = []
    for i, prompt in enumerate(prompts):
        enhanced_prompt = f"Ultra-realistic photograph of {prompt}, 4K resolution, cinematic lighting, highly detailed, photorealistic textures, 16:9 aspect ratio"
        body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": enhanced_prompt, "negativeText": "blurry, low quality"},
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "quality": "premium",
                "height": 1080,
                "width": 1920,
                "cfgScale": 8.0,
                "seed": i
            }
        }
        try:
            response = bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=config["TITAN_MODEL_ID"]
            )
            response_body = json.loads(response.get('body').read())
            if not response_body.get('images'):
                raise ValueError("No se generaron imágenes")
            image_base64 = response_body['images'][0]
            image_data = base64.b64decode(image_base64)
            img_path = output_dir / f"image_{i+1:02d}.jpg"
            img_path.write_bytes(image_data)
            image_paths.append(img_path)
            logger.info(f"Imagen {i+1} de Titan guardada: {img_path}")
        except boto3.exceptions.Boto3Error as e:
            logger.error(f"Fallo en Titan para prompt {prompt}: {e}")
            raise
    return image_paths

def generate_images(prompts: List[str], output_dir: Path, config: Dict[str, Any]) -> List[Path]:
    source = config.get("IMAGE_SOURCE", "pexels")
    logger.info(f"Fuente de imágenes: {source}")
    try:
        if source == "titan":
            return generate_titan_images(prompts, output_dir, config)
        elif source == "flux":
            return generate_flux_images(prompts, output_dir, config)
        elif source == "pexels":
            return generate_pexels_images(prompts, output_dir, config)
        else:
            raise ValueError(f"Fuente de imágenes no soportada: {source}")
    except Exception as e:
        logger.error(f"Fallo con {source}: {e}")
        if source != "pexels":
            logger.info("Usando Pexels como fallback")
            return generate_pexels_images(prompts, output_dir, config)
        raise

# --- Funciones Auxiliares ---

def setup_directories(project_name: str) -> tuple[Path, Path, Path]:
    base_dir = Path("output") / project_name
    audio_dir, images_dir, video_dir = base_dir / "audio", base_dir / "imagenes", base_dir / "video"
    for d in [audio_dir, images_dir, video_dir]:
        d.mkdir(parents=True, exist_ok=True)
    return audio_dir, images_dir, video_dir

def extract_prompts(text: str) -> List[str]:
    chunk_marker = "--- CHUNK SPLIT FOR POLLY ---"
    chunks = text.split(chunk_marker) if chunk_marker in text else [text]
    stop_words = {"el", "la", "los", "las", "de", "en", "a", "con", "por", "para", "que", "y", "o", "un", "una", "es", "se", "al", "del", "su"}
    prompts = []
    for chunk in chunks:
        words = re.findall(r'\w+', chunk.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        top_keywords = [w for w, _ in Counter(keywords).most_common(3)]
        if top_keywords:
            prompt = " ".join(top_keywords)
            prompts.append(prompt)
    default_prompts = [
        "FIFA World Cup 2006 Germany",
        "Zidane headbutt Materazzi 2006",
        "Italy winning penalty shootout 2006",
        "Storming of Olympiastadion Berlin",
        "Philipp Lahm goal opening match",
        "Battle of Nuremberg 2006",
        "Fabio Grosso goal vs Germany",
        "France vs Brazil 2006",
        "Shakira performance World Cup",
        "Miroslav Klose Golden Boot",
        "Italian fans celebrating 2006",
        "Zinedine Zidane red card"
    ]
    while len(prompts) < 12:
        prompts.extend(default_prompts[:12 - len(prompts)])
    return prompts[:12]

def load_project_config(project_path: Path) -> Dict[str, Any]:
    config_path = project_path / "config.json"
    final_config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            project_specific_config = json.load(f)
        final_config.update(project_specific_config)
    else:
        logger.warning(f"No config.json en {project_path}. Usando configuración por defecto.")
    return final_config

def select_projects() -> List[Path]:
    project_dir = Path("projects")
    if not any(project_dir.iterdir()):
        raise FileNotFoundError("No hay proyectos en 'projects'.")
    projects = sorted([d for d in project_dir.iterdir() if d.is_dir()])
    print("Proyectos disponibles:")
    for i, p in enumerate(projects, 1):
        print(f"{i}. {p.name}")
    selections = input("Selecciona los números de los proyectos (ej: 1 o 1,2): ").strip()
    return [projects[int(i)-1] for i in selections.split(',')]

def create_video(audio_path: Path, image_paths: List[Path], output_path: Path, config: Dict[str, Any]) -> None:
    if not image_paths:
        raise ValueError("No hay imágenes para el video.")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio no encontrado: {audio_path}")
    audio_clip = AudioFileClip(str(audio_path))
    duration_per_image = audio_clip.duration / len(image_paths)
    transition_duration = 1.0
    clips = []
    
    for i, img_path in enumerate(image_paths):
        clip_duration = duration_per_image + transition_duration if i < len(image_paths) - 1 else duration_per_image
        img_clip = ImageClip(str(img_path)).set_duration(clip_duration)
        img_resized = img_clip.resize(height=config["VIDEO_SIZE"][1] * 1.1)
        bg = ColorClip(size=config["VIDEO_SIZE"], color=(0,0,0), duration=clip_duration)
        composite = CompositeVideoClip([bg, img_resized.set_position("center")], size=config["VIDEO_SIZE"])
        zoomed = composite.fx(vfx.resize, lambda t: 1 + (t/clip_duration) * (config["ZOOM_FACTOR"]-1))
        styled = zoomed.fx(vfx.colorx, factor=0.9)
        final_clip = styled.fx(fadein, transition_duration).fx(fadeout, transition_duration)
        start_time = i * duration_per_image - (transition_duration if i > 0 else 0)
        final_clip = final_clip.set_start(start_time)
        clips.append(final_clip)
    
    video = CompositeVideoClip(clips, size=config["VIDEO_SIZE"]).set_duration(audio_clip.duration).set_audio(audio_clip)
    video.write_videofile(
        str(output_path),
        fps=config["FPS"],
        codec="libx264",
        audio_codec="aac",
        bitrate=config["VIDEO_BITRATE"],
        preset="medium",
        threads=4,
        ffmpeg_params=["-crf", config["CRF"]],
        logger="bar"
    )
    audio_clip.close()
    video.close()
    logger.info(f"Video generado: {output_path}")

@retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
def upload_to_youtube(video_path: Path, config: Dict[str, Any]) -> None:
    try:
        if not video_path.exists():
            raise FileNotFoundError(f"Video no encontrado: {video_path}")
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
        logger.info(f"Video subido a: http://youtu.be/{response['id']}")
    except Exception as e:
        logger.error(f"Fallo al subir a YouTube: {e}")
        raise

def process_project(project_path: Path) -> None:
    project_name = project_path.stem
    logger.info(f"Procesando proyecto: {project_name}")
    try:
        config = load_project_config(project_path)
        script_file = project_path / "script.txt"
        if not script_file.exists():
            raise FileNotFoundError(f"No script.txt en {project_name}")
        audio_dir, images_dir, video_dir = setup_directories(project_name)
        with open(script_file, "r", encoding="utf-8") as f:
            text = f.read().strip()
        audio_path = audio_dir / f"{project_name}.mp3"
        video_path = video_dir / f"{project_name}_video.mp4"
        
        generate_audio(text, audio_path, config)
        prompts = extract_prompts(text)
        image_paths = generate_images(prompts, images_dir, config)
        create_video(audio_path, image_paths, video_path, config)
        
        if input(f"¿Subir '{project_name}' a YouTube? (s/n): ").lower() == "s":
            upload_to_youtube(video_path, config)
    except Exception as e:
        logger.error(f"Fallo en {project_name}: {e}")
        raise

def main():
    try:
        for d in DEFAULT_CONFIG["ROOT_DIRECTORIES"]:
            Path(d).mkdir(exist_ok=True)
        projects = select_projects()
        for p in projects:
            process_project(p)
        logger.info("Procesamiento completado.")
    except Exception as e:
        logger.error(f"Fallo general: {e}")

if __name__ == "__main__":
    main()