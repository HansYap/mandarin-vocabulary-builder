from flask import Blueprint, request, jsonify
from backend.state.store import transcripts, conversation_histories, llm
import requests

# MeloTTS API endpoint
MELOTTS_API_URL = "http://127.0.0.1:8000/tts"

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('', methods=['POST'])
@chat_bp.route('/', methods=['POST'])
def chat():
   
   # silent=true to return none if request body not valid json, prevent crashes
    data = request.get_json(silent=True) or {}
    
    user_input = data.get('text') or data.get('message')
    session_id = data.get('session_id', 'default')
    is_edited = data.get('is_edited', False)  # Track if user edited the text via the "Manual" ASR feature
    original_text = data.get('original_text', None)  # keep original for logging/analysis 'just in case'

    if not user_input:
        return jsonify({
            'status': 'error',
            'message': 'No text provided'
        }), 400

    # Init session storage
    conversation_histories.setdefault(session_id, [])
    transcripts.setdefault(session_id, [])

    # Log if edited
    if is_edited and original_text:
        print(f"📝 User edited transcript:")
        print(f"   Original: '{original_text}'")
        print(f"   Edited:   '{user_input}'")

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
                    #Suggestion: Replace audio_chunks.append(chunk), With socketio.emit("audio_chunk", chunk) for true real time streaming
                    audio_chunks.append(chunk)
            
            audio_data = b''.join(audio_chunks)
            
            # convert to base64 to store raw bytes in json and url for frontend to play audio
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
        'audio': audio_url,
        'was_edited': is_edited  
    })