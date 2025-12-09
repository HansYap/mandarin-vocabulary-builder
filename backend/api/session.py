from flask import Blueprint, request, jsonify

from backend.models.feedback_gen import FeedbackGenerator
from backend.models.llm_handler import LLMHandler
from backend.state.store import transcripts

session_bp = Blueprint('session', __name__)

# If you want to regenerate per session_id
_feedback_generator = FeedbackGenerator(LLMHandler())

# Use same in-memory store (or better: persistent)
_transcripts = {}  # ideally same as chat

# For simplicity, assuming global transcripts is okay:
# (in real app: use a dict mapping session_id -> transcript)

@session_bp.route('', methods=['POST'])
@session_bp.route('/', methods=['POST'])
def end_session():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')

    # Get the stored transcript (you need to share it with chat)
    transcript = transcripts.get(session_id, [])
    
    print("\n=== TRANSCRIPT FOR SESSION:", session_id, "===")
    for msg in transcript:
        print(f"{msg['role'].upper()}: {msg['text']}")
    print("=== END TRANSCRIPT ===\n")
    
    feedback = _feedback_generator.analyze_session(transcript)

    # clear for next session
    transcripts[session_id] = []
    # optionally clear conversation history if stored elsewhere

    return jsonify({
        'status': 'success',
        'feedback': feedback
    })
