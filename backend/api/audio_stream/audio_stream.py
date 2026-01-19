from flask import request
from flask_socketio import emit, join_room
from backend.app import socketio
import requests
from io import BytesIO

# In-memory storage for audio chunks per session
session_chunks = {}

ASR_SERVICE_URL = "http://127.0.0.1:5001/transcribe"

# frontend does a "socket.on("connect")", socketio server sees the "connect" and triggers this function
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
    
    # Clear any previous chunks for this session
    session_chunks[session_id] = []
    
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
        
        # Accumulate the chunk and check first to prevent crashes
        if session_id not in session_chunks:
            session_chunks[session_id] = []
        session_chunks[session_id].append(chunk)
        
        print(f"   ✅ Chunk accumulated (total chunks: {len(session_chunks[session_id])})")
        
    except Exception as e:
        print(f"❌ Chunk handling error in session {session_id[:8]}...: {e}")
        import traceback
        traceback.print_exc()


@socketio.on("end_speak")
def finalize_audio_session(data):
    """
    End recording and transcribe via ASR microservice
    """
    session_id = data.get("session_id", "default")
    auto_submit = data.get("auto_submit", False)
    
    print("\n" + "=" * 50)
    print("⏹️ END SPEAK EVENT RECEIVED")
    print(f"   Session ID: {session_id[:8]}...")
    print(f"   Auto-submit mode: {auto_submit}")
    print("=" * 50 + "\n")
    
    # Send initial processing message
    socketio.emit("partial_transcript", {
        "text": "...正在转写 (Transcribing...)"
    }, room=session_id)
    
    try:
        # Combine all chunks
        if session_id not in session_chunks or not session_chunks[session_id]:
            print(f"⚠️ No audio chunks for session {session_id[:8]}")
            socketio.emit("transcript_ready", {
                "text": "",
                "auto_submit": auto_submit,
                "session_id": session_id
            }, room=session_id)
            return
        
        # send chunks early while user speaking to avoid browser holding all the chunks in memory 
        combined_webm = b''.join(session_chunks[session_id])
        print(f"🔗 Combined {len(session_chunks[session_id])} chunks ({len(combined_webm)} bytes)")
        
        # Call ASR microservice
        print(f"🚀 Calling ASR service at {ASR_SERVICE_URL}...")
        
        files = {
            'file': ('audio.webm', BytesIO(combined_webm), 'audio/webm')
        }
        
        response = requests.post(ASR_SERVICE_URL, files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            final_text = result.get('text', '')
            print(f"✅ Transcription received: '{final_text}'")
        else:
            print(f"❌ ASR service error: {response.status_code} - {response.text}")
            final_text = ""
        
        # Send result to frontend
        socketio.emit("transcript_ready", {
            "text": final_text,
            "auto_submit": auto_submit,
            "session_id": session_id
        }, room=session_id)
        
        print(f"   ✅ Sent 'transcript_ready' to room: {session_id[:8]}...")
        print(f"   📝 Frontend will {'auto-submit' if auto_submit else 'wait for user confirmation'}")
        
        # Clean up
        session_chunks[session_id] = []
        
    except requests.exceptions.Timeout:
        print(f"❌ ASR service timeout")
        socketio.emit("transcript_ready", {
            "text": "",
            "auto_submit": auto_submit,
            "session_id": session_id,
            "error": "Transcription timeout"
        }, room=session_id)
        
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        import traceback
        traceback.print_exc()
        
        socketio.emit("transcript_ready", {
            "text": "",
            "auto_submit": auto_submit,
            "session_id": session_id,
            "error": str(e)
        }, room=session_id)
    finally:
        # Always clean up
        if session_id in session_chunks:
            session_chunks[session_id] = []
    
    print("=" * 50 + "\n")


@socketio.on("confirm_transcript")
def handle_confirm_transcript(data):
    """
    Frontend sends edited/confirmed transcript here.
    """
    print("\n" + "=" * 50)
    print("✅ CONFIRM TRANSCRIPT EVENT RECEIVED")
    print(f"   Data: {data}")
    
    #for debugging to see the edited text
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