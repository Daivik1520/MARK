"""
MARK — Main Application Server
Flask-SocketIO server powering the MARK AI System Controller.
"""

import os
import time
import threading
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

from ai_engine import get_ai_response, reset_conversation
from tts_engine import text_to_speech_base64

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="static")
app.config["SECRET_KEY"] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─────────────────────────────────────────────
# WEBSOCKET EVENTS
# ─────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    print("🔌 Client connected")
    emit("status", {"message": "Connected to MARK", "type": "success"})


@socketio.on("disconnect")
def handle_disconnect():
    print("🔌 Client disconnected")


@socketio.on("user_message")
def handle_message(data):
    """Handle user text/voice message."""
    user_text = data.get("message", "").strip()
    if not user_text:
        return

    print(f"👤 User: {user_text}")

    # Send thinking indicator
    emit("thinking", {"status": True})

    try:
        # Get AI response (may include tool calls)
        start = time.time()
        result = get_ai_response(user_text)
        elapsed = round(time.time() - start, 2)

        ai_text = result["text"]
        tool_calls = result.get("tool_calls")

        print(f"🤖 MARK: {ai_text} ({elapsed}s)")

        # Send the text response
        emit("ai_response", {
            "text": ai_text,
            "tool_calls": tool_calls,
            "response_time": elapsed
        })

        # Generate TTS audio in background and send it
        def generate_and_send_audio():
            audio_b64 = text_to_speech_base64(ai_text)
            if audio_b64:
                socketio.emit("tts_audio", {"audio": audio_b64})

        threading.Thread(target=generate_and_send_audio, daemon=True).start()

    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(f"❌ {error_msg}")
        emit("ai_response", {"text": error_msg, "tool_calls": None})

    finally:
        emit("thinking", {"status": False})


@socketio.on("reset_chat")
def handle_reset():
    """Reset conversation history."""
    reset_conversation()
    emit("status", {"message": "Conversation reset", "type": "info"})


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

if __name__ == "__main__":
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("\n⚠️  WARNING: Set your OPENROUTER_API_KEY in .env file!")
        print("   Get one at: https://openrouter.ai/keys\n")

    print("""
    ╔══════════════════════════════════════╗
    ║         M.A.R.K. SYSTEM              ║
    ║   AI System Controller v1.0          ║
    ║   http://localhost:5001              ║
    ╚══════════════════════════════════════╝
    """)

    socketio.run(app, host="0.0.0.0", port=5001, debug=False, allow_unsafe_werkzeug=True)
