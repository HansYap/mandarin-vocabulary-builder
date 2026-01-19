from flask import Blueprint, request, jsonify
from backend.state.store import transcripts, feedback

session_bp = Blueprint('session', __name__)

@session_bp.route('', methods=['POST'])
@session_bp.route('/', methods=['POST'])
def end_session():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')

    # Get the stored transcript (you need to share it with chat)
    transcript = transcripts.get(session_id, [])
    
    feedback_response = feedback.analyze_session(transcript)

    # clear for next session
    transcripts[session_id] = []

    return jsonify({
        'status': 'success',
        'feedback': feedback_response
    })
