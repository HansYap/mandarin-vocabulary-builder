from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from melo.api import TTS
import io
import torch

app = FastAPI(title="MeloTTS API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Device configuration
device = 'auto'
if device == 'auto':
    device = 'cpu'
    if torch.cuda.is_available(): 
        device = 'cuda'
    if torch.backends.mps.is_available(): 
        device = 'mps'

# Pre-load all models
print("Loading models...")
models = {
    # 'EN': TTS(language='EN', device=device),
    # 'ES': TTS(language='ES', device=device),
    # 'FR': TTS(language='FR', device=device),
    'ZH': TTS(language='ZH', device=device),
    # 'JP': TTS(language='JP', device=device),
    # 'KR': TTS(language='KR', device=device),
}
print("Models loaded successfully!")

class TTSRequest(BaseModel):
    text: str
    language: str = "EN"
    speaker: str = "EN-US"
    speed: float = 1.0
    sdp_ratio: float = 0.2
    noise_scale: float = 0.6
    noise_scale_w: float = 0.8

@app.get("/")
async def root():
    return {
        "message": "MeloTTS API Server",
        "version": "1.0.0",
        "endpoints": {
            "POST /tts": "Generate speech from text",
            "GET /speakers": "Get all available speakers",
            "GET /speakers/{language}": "Get speakers for specific language",
            "GET /languages": "Get supported languages",
            "GET /health": "Health check"
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "device": device}

@app.get("/languages")
async def get_languages():
    """Get list of supported languages"""
    return {
        "languages": list(models.keys())
    }

@app.get("/speakers")
async def get_all_speakers():
    """Get all available speakers across all languages"""
    all_speakers = {}
    for lang, model in models.items():
        all_speakers[lang] = list(model.hps.data.spk2id.keys())
    return all_speakers

@app.get("/speakers/{language}")
async def get_speakers(language: str):
    """Get available speakers for a specific language"""
    language = language.upper()
    if language not in models:
        raise HTTPException(
            status_code=400, 
            detail=f"Language '{language}' not supported. Available: {list(models.keys())}"
        )
    
    speakers = list(models[language].hps.data.spk2id.keys())
    return {
        "language": language,
        "speakers": speakers
    }

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech
    
    Parameters:
    - text: The text to convert to speech
    - language: Language code (EN, ES, FR, ZH, JP, KR)
    - speaker: Speaker ID (e.g., EN-US, EN-BR, EN-AU, EN_INDIA, EN-Default)
    - speed: Speech speed (default: 1.0, range: 0.1-10.0)
    - sdp_ratio: SDP ratio (default: 0.2)
    - noise_scale: Noise scale (default: 0.6)
    - noise_scale_w: Noise scale W (default: 0.8)
    
    Returns: WAV audio file
    """
    try:
        # Validate language
        language = request.language.upper()
        if language not in models:
            raise HTTPException(
                status_code=400,
                detail=f"Language '{language}' not supported. Available: {list(models.keys())}"
            )
        
        model = models[language]
        speaker_ids = model.hps.data.spk2id
        
        # Validate speaker
        if request.speaker not in speaker_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Speaker '{request.speaker}' not found for language '{language}'. Available speakers: {list(speaker_ids.keys())}"
            )
        
        # Validate speed
        if not 0.1 <= request.speed <= 10.0:
            raise HTTPException(
                status_code=400,
                detail="Speed must be between 0.1 and 10.0"
            )
        
        # Generate speech to BytesIO buffer
        bio = io.BytesIO()
        model.tts_to_file(
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
        
        # Reset buffer position to beginning
        bio.seek(0)
        
        # Return audio as streaming response
        return StreamingResponse(
            bio,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating speech: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    print(f"Starting MeloTTS API Server on device: {device}")
    print("API will be available at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)