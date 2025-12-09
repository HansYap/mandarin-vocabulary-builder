from backend.app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # Use eventlet instead of threading - much more stable for WebSocket
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, use_reloader=False)