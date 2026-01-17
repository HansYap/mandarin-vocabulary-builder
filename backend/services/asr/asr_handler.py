"""
ASR Microservice using FastAPI
Run with: uvicorn asr_service:app --host 127.0.0.1 --port 5001
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import subprocess
import tempfile
import os
import torch
from pydantic import BaseModel

app = FastAPI(title="ASR Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instance (lazy loaded)
whisper_model = None

class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None


def get_model():
    """Lazy load the Whisper model"""
    global whisper_model
    if whisper_model is None:
        print("🔄 Loading Whisper model into VRAM...")
        whisper_model = WhisperModel(
            "large-v3-turbo",
            device="cuda",
            compute_type="float16",
            num_workers=1
        )
        print("✅ Whisper model loaded")
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
            print(f"❌ FFmpeg error: {stderr.decode()}")
            return None
            
        return wav_bytes
        
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg conversion timeout")
        process.kill()
        return None
    except Exception as e:
        print(f"❌ FFmpeg conversion error: {e}")
        return None


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio file (WebM, WAV, etc.)
    """
    try:
        print(f"📥 Received file: {file.filename} ({file.content_type})")
        
        # Read file content
        audio_data = await file.read()
        print(f"📊 File size: {len(audio_data)} bytes")
        
        # Convert WebM to WAV if needed
        if file.content_type == "audio/webm" or file.filename.endswith('.webm'):
            print("🔄 Converting WebM to WAV...")
            wav_data = convert_webm_to_wav(audio_data)
            if not wav_data:
                raise HTTPException(status_code=400, detail="Failed to convert audio")
            audio_data = wav_data
            print(f"✅ Conversion complete: {len(audio_data)} bytes")
        
        # Save to temporary file for Whisper
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            print(f"💾 Temp file: {temp_path}")
            print("🎯 Starting transcription...")
            
            # Get model and transcribe
            model = get_model()
            segments, info = model.transcribe(
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
                print(f"  📄 Segment: {segment.text}")
            
            transcription = "".join(all_text).strip()
            print(f"✅ Transcription: '{transcription}'")
            
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
                    print(f"🗑️ Temp file deleted")
                except Exception as e:
                    print(f"⚠️ Failed to delete temp file: {e}")
                    
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/unload")
async def unload_model():
    """Unload model from VRAM to free memory"""
    global whisper_model
    if whisper_model is not None:
        del whisper_model
        whisper_model = None
        torch.cuda.empty_cache()
        print("✅ Model unloaded from VRAM")
        return {"status": "unloaded"}
    return {"status": "already_unloaded"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": whisper_model is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5001)