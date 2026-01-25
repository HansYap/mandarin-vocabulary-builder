import eventlet
eventlet.monkey_patch()

from backend.app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # Use eventlet instead of threading - much more stable for WebSocket
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)