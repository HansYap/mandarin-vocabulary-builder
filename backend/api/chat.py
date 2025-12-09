from flask import Blueprint, request, jsonify, send_file
from backend.models.asr_handler import ASRHandler
from backend.models.llm_handler import LLMHandler
from backend.models.feedback_gen import FeedbackGenerator
from backend.state.store import transcripts, conversation_histories
import requests
import io

# Create your handlers once (or you can lazily create per-request) (RMBR SINGLETON)
asr = ASRHandler()
llm = LLMHandler()
feedback = FeedbackGenerator(llm)

# MeloTTS API endpoint
MELOTTS_API_URL = "http://localhost:8000/tts"

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('', methods=['POST'])
@chat_bp.route('/', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    
    user_input = data.get('text') or data.get('message')
    session_id = data.get('session_id', 'default')

    # Init session storage
    conversation_histories.setdefault(session_id, [])
    transcripts.setdefault(session_id, [])

    transcripts[session_id].append({'role': 'user', 'text': user_input})

    # Get LLM response
    response = llm.get_response(user_input, conversation_histories[session_id])

    conversation_histories[session_id].append({'role': 'user', 'content': user_input})
    conversation_histories[session_id].append({'role': 'assistant', 'content': response})
    transcripts[session_id].append({'role': 'assistant', 'text': response})

    # Generate TTS audio - STREAM IT INSTEAD OF WAITING
    audio_url = None
    try:
        # Use streaming to reduce perceived latency
        tts_response = requests.post(
            MELOTTS_API_URL,
            json={
                "text": response,
                "language": "ZH",
                "speaker": "ZH",
                "speed": 0.8  # ← Slightly faster for responsiveness
            },
            timeout=15,  # ← Reduced timeout
            stream=True  # ← STREAM THE RESPONSE
        )
        
        if tts_response.status_code == 200:
            # Read audio in chunks to reduce waiting
            audio_chunks = []
            for chunk in tts_response.iter_content(chunk_size=4096):
                if chunk:
                    audio_chunks.append(chunk)
            
            audio_data = b''.join(audio_chunks)
            
            # Only base64 encode if needed - consider direct binary stream instead
            import base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            audio_url = f"data:audio/wav;base64,{audio_base64}"
        else:
            print(f"TTS Error: {tts_response.status_code}")
            
    except Exception as e:
        print(f"TTS generation failed: {e}")

    return jsonify({
        'status': 'success',
        'response': response,
        'transcript': user_input,
        'session_id': session_id,
        'audio': audio_url
    })