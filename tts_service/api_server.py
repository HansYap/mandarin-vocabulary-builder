from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool # Essential for non-blocking
from pydantic import BaseModel
from melo.api import TTS
import io
import torch
from contextlib import asynccontextmanager

device = 'cuda' if torch.cuda.is_available() else 'cpu'
if torch.backends.mps.is_available():
    device = 'mps'

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events cleanly"""
    print(f"Starting TTS Service on {device}...")
    try:
        # Store in app.state so routes can access them
        app.state.tts_models = {
            'ZH': TTS(language='ZH', device=device)
        }
        app.state.model_loaded = True
        print("Models loaded successfully!")
    except Exception as e:
        app.state.model_loaded = False
        print(f"CRITICAL: Error loading models: {e}")
    
    yield
    
    # Clean up on shutdown
    if hasattr(app.state, 'tts_models'):
        app.state.tts_models.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

app = FastAPI(title="MeloTTS API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    text: str
    language: str = "ZH" # Default to ZH since that's what we loaded
    speaker: str = "ZH"    
    speed: float = 1.0
    sdp_ratio: float = 0.2
    noise_scale: float = 0.6
    noise_scale_w: float = 0.8

# --- Helper to get models safely ---
def get_tts_model(lang: str):
    models = getattr(app.state, 'tts_models', {})
    if lang not in models:
        raise HTTPException(
            status_code=400, 
            detail=f"Language '{lang}' not supported. Available: {list(models.keys())}"
        )
    return models[lang]

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "model_loaded": getattr(app.state, "model_loaded", False),
        "device": device
    }

@app.get("/languages")
async def get_languages():
    return {"languages": list(getattr(app.state, 'tts_models', {}).keys())}

@app.get("/speakers")
async def get_all_speakers():
    all_speakers = {}
    for lang, model in getattr(app.state, 'tts_models', {}).items():
        all_speakers[lang] = list(model.hps.data.spk2id.keys())
    return all_speakers

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    if not getattr(app.state, "model_loaded", False):
        raise HTTPException(status_code=503, detail="Models are still loading")

    try:
        lang = request.language.upper()
        model = get_tts_model(lang)
        speaker_ids = model.hps.data.spk2id
        
        if request.speaker not in speaker_ids:
            raise HTTPException(status_code=400, detail=f"Speaker '{request.speaker}' not found")
        
        bio = io.BytesIO()

        # Run the heavy /GPU task in a threadpool so the API stays responsive
        await run_in_threadpool(
            model.tts_to_file,
            request.text,
            speaker_ids[request.speaker],
            bio,
            speed=request.speed,
            sdp_ratio=request.sdp_ratio,
            noise_scale=request.noise_scale,
            noise_scale_w=request.noise_scale_w,
            format='wav',
            quiet=True
        )
        
        bio.seek(0)
        return StreamingResponse(bio, media_type="audio/wav")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)