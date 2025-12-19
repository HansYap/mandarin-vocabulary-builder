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
    CORS(app, origins=["http://127.0.0.1:5173", "http://localhost:5173", "https://frontend-tutor-mvp.vercel.app"])
    
    from .api.chat import chat_bp
    from .api.session import session_bp

    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(session_bp, url_prefix='/api/end-session')

    # Initialize socketio with app FIRST
    socketio.init_app(app)
    
    # Import audio_stream AFTER socketio is initialized
    from .api.audio_stream import audio_stream

    return app