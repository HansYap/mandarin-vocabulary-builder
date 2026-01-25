from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import subprocess
import tempfile
import os
import torch
from pydantic import BaseModel
import time
from contextlib import asynccontextmanager


def get_model():
    """Lazy load the Whisper model with retry logic"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute = "float16" if device == "cuda" else "int8"
    
    
    # Set longer timeout for downloads
    os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '600'
    
    model_name = "dropbox-dash/faster-whisper-large-v3-turbo"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"Loading model {model_name} (attempt {attempt + 1}/{max_retries})...")
            
            whisper_model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute,
                num_workers=1,
                download_root="/root/.cache/huggingface"
            )
            
            print(f"Model loaded successfully on {device}!")
            break
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("All retry attempts failed!")
                raise
    
    return whisper_model


def convert_webm_to_wav(webm_bytes: bytes) -> bytes | None:
    """Convert WebM audio to WAV format"""
    try:
        process = subprocess.Popen(
            [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', 'pipe:0', '-f', 'wav',
                '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
                'pipe:1'
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        wav_bytes, stderr = process.communicate(input=webm_bytes, timeout=10)
        
        if process.returncode != 0:
            print(f"FFmpeg error: {stderr.decode()}")
            return None
            
        return wav_bytes
        
    except subprocess.TimeoutExpired:
        print("FFmpeg conversion timeout")
        process.kill()
        return None
    except Exception as e:
        print(f"FFmpeg conversion error: {e}")
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events"""
    print("=" * 60)
    print("ASR Service Starting...")
    try:
        
        app.state.whisper_model = get_model()
        print("Whisper model loaded and ready!")
        print("=" * 60)
    except Exception as e:
        print(f"FAILED to load model: {e}")
        raise e 

    yield 

    print("Shutting down ASR Service...")
    if hasattr(app.state, 'whisper_model'):
        del app.state.whisper_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        
app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None
    
    
@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio file (WebM, WAV, etc.)
    """
    try:
        
        # Read file content
        audio_data = await file.read()
        
        # Convert WebM to WAV if needed
        if file.content_type == "audio/webm" or file.filename.endswith('.webm'):
            
            wav_data = convert_webm_to_wav(audio_data)
            if not wav_data:
                raise HTTPException(status_code=400, detail="Failed to convert audio")
            audio_data = wav_data
        
        # Save to temporary file for Whisper
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            
            # Get model and transcribe
            segments, info = app.state.whisper_model.transcribe(
                temp_path,
                language="zh",
                beam_size=5,
                initial_prompt="这是一段中文和English的混合语音。",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Collect segments
            all_text = []
            for segment in segments:
                all_text.append(segment.text)
            
            transcription = "".join(all_text).strip()
            
            return TranscriptionResponse(
                text=transcription,
                language=info.language if hasattr(info, 'language') else None,
                duration=info.duration if hasattr(info, 'duration') else None
            )
            
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    print(f"Failed to delete temp file: {e}")
                    
    except Exception as e:
        print(f"Transcription error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# TO BE IMPLEMENTED
@app.post("/unload")
async def unload_model():
    if hasattr(app.state, 'whisper_model'):
        app.state.whisper_model = None
        torch.cuda.empty_cache()
        return {"status": "unloaded"}
    return {"status": "already_unloaded"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": app.state.whisper_model is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)