from flask import request
from flask_socketio import emit, join_room
from backend.app import socketio
from backend.models.asr_handler import ASRHandler

asr = ASRHandler()
partial_transcripts = {}

@socketio.on('connect')
def handle_connect():
    print("=" * 50)
    print("✅ NEW CLIENT CONNECTED")
    print(f"   Socket ID: {request.sid}")
    print("=" * 50)

@socketio.on('disconnect')
def handle_disconnect(data):
    print("=" * 50)
    print("🔌 CLIENT DISCONNECTED")
    print(f"   Data: {data}")
    print(f"   Socket ID: {request.sid}")
    print("=" * 50)

@socketio.on("start_speak")
def start_audio_session(data):
    print("\n" + "=" * 50)
    print("🎤 START SPEAK EVENT RECEIVED")
    print(f"   Data: {data}")
    print(f"   Socket ID: {request.sid}")
    
    session_id = data.get("session_id", "default")
    print(f"   Session ID: {session_id}")
    
    # Join the room so we can target this specific client
    join_room(session_id)
    print(f"   ✅ Joined room: {session_id}")
    
    partial_transcripts[session_id] = ""
    
    # Clear any previous chunks for this session
    asr.clear_session(session_id)
    
    emit("session_ready", {"status": "ok"}, room=session_id)
    print(f"   ✅ Sent 'session_ready' to room: {session_id}")
    print("=" * 50 + "\n")

@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    session_id = data.get("session_id", "default")
    
    if "chunk" not in data:
        print(f"⚠️ No chunk in data for session: {session_id}")
        return

    try:
        # Convert array back to bytes
        chunk = bytes(data["chunk"])
        chunk_size = len(chunk)
        
        print(f"📦 Audio chunk received - Session: {session_id[:8]}... | Size: {chunk_size} bytes")
        
        # Accumulate the chunk instead of transcribing immediately
        asr.add_chunk(session_id, chunk)
        print(f"   ✅ Chunk accumulated (total chunks: {len(asr.session_chunks.get(session_id, []))})")
        
    except Exception as e:
        print(f"❌ Chunk handling error in session {session_id[:8]}...: {e}")
        import traceback
        traceback.print_exc()

@socketio.on("end_speak")
def finalize_audio_session(data):
    """
    NEW BEHAVIOR: Only transcribe and send to frontend.
    Frontend will decide whether to auto-submit or let user edit.
    """
    print("\n" + "=" * 50)
    print("⏹️ END SPEAK EVENT RECEIVED")
    print(f"   Data: {data}")
    
    session_id = data.get("session_id", "default")
    auto_submit = data.get("auto_submit", False)  # NEW: Check if auto-submit is enabled
    
    print(f"   Session ID: {session_id[:8]}...")
    print(f"   Auto-submit mode: {auto_submit}")
    print(f"   Transcribing accumulated chunks...")
    
    # Transcribe all accumulated chunks
    final_text = asr.transcribe_accumulated(session_id)
    
    if not final_text:
        print(f"   ⚠️ No transcription result")
        final_text = ""
    else:
        print(f"   Final transcript: '{final_text}'")
    
    # Send transcript to frontend with auto_submit flag
    emit("transcript_ready", {
        "text": final_text,
        "auto_submit": auto_submit,
        "session_id": session_id
    }, room=session_id)
    print(f"   ✅ Sent 'transcript_ready' to room: {session_id[:8]}...")
    print(f"   📝 Frontend will {'auto-submit' if auto_submit else 'wait for user confirmation'}")
    
    # Clean up temporary data but keep session alive for potential edits
    partial_transcripts[session_id] = ""
    asr.clear_session(session_id)
    print(f"   ✅ Cleaned up session: {session_id[:8]}...")
    print("=" * 50 + "\n")

@socketio.on("confirm_transcript")
def handle_confirm_transcript(data):
    """
    NEW EVENT: Frontend sends edited/confirmed transcript here.
    This replaces the old auto-call to /chat.
    """
    print("\n" + "=" * 50)
    print("✅ CONFIRM TRANSCRIPT EVENT RECEIVED")
    print(f"   Data: {data}")
    
    session_id = data.get("session_id", "default")
    edited_text = data.get("text", "")
    
    print(f"   Session ID: {session_id[:8]}...")
    print(f"   Confirmed text: '{edited_text}'")
    
    # Acknowledge receipt
    emit("transcript_confirmed", {
        "status": "ok",
        "text": edited_text,
        "session_id": session_id
    }, room=session_id)
    
    print(f"   ✅ Frontend should now call /chat with: '{edited_text}'")
    print("=" * 50 + "\n")

@socketio.on_error_default
def default_error_handler(e):
    print(f"❌ SocketIO Error: {e}")
    import traceback
    traceback.print_exc()

# Debug: catch all events
@socketio.on('*')
def catch_all(event, data):
    if event not in ['connect', 'disconnect', 'start_speak', 'audio_chunk', 'end_speak', 'confirm_transcript']:
        print(f"🔍 DEBUG - Caught unhandled event: '{event}'")
        print(f"   Data: {data}")