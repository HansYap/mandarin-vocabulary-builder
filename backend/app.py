from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

# Use eventlet async_mode for better WebSocket stability
socketio = SocketIO(
    cors_allowed_origins="*", 
    async_mode="eventlet",  # Changed from threading
    ping_timeout=60, 
    ping_interval=25
)

def create_app():
    app = Flask(__name__)
    CORS(app, origins=["*"])
    
    from backend.api.chat import chat_bp
    from backend.api.session import session_bp
    from backend.api.dictionary import dictionary_bp

    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(session_bp, url_prefix='/api/end-session')
    app.register_blueprint(dictionary_bp, url_prefix='/api/dictionary')

    # Initialize socketio with app FIRST
    socketio.init_app(app)
    
    # Import audio_stream AFTER socketio is initialized
    from backend.api.audio_stream import audio_stream

    return app