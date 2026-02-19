"""
MARK — Main Application Server
Flask-SocketIO server powering the MARK AI System Controller.
"""

import os
import time
import threading
from flask import Flask, render_template, send_from_directory, request, jsonify
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

from ai_engine import get_ai_response, reset_conversation, get_system_prompt, set_system_prompt
from tts_engine import text_to_speech_base64
from reminder_manager import start_scheduler as start_reminder_scheduler
from clipboard_manager import start_clipboard_monitor
from gesture_controller import execute_gesture
from proactive_monitor import start_proactive_monitor
from system_controller import set_brightness

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


@app.route("/upload_3d", methods=["POST"])
def upload_3d():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400
    os.makedirs("static/uploads", exist_ok=True)
    safe = secure_filename(f.filename)
    f.save(os.path.join("static/uploads", safe))
    return jsonify({"url": f"/static/uploads/{safe}", "name": safe})


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


@socketio.on("clap_activate")
def handle_clap_activate():
    """Handle clap activation — generate TTS for the activation phrase."""
    print("👏👏 Clap activation triggered!")
    activation_text = "Activating all services. M.A.R.K. activated."

    def generate_activation_audio():
        audio_b64 = text_to_speech_base64(activation_text)
        if audio_b64:
            socketio.emit("clap_activation_tts", {"audio": audio_b64})

    threading.Thread(target=generate_activation_audio, daemon=True).start()


@socketio.on("get_system_prompt")
def handle_get_prompt():
    """Send the current system prompt to the client."""
    emit("system_prompt", {"prompt": get_system_prompt()})


@socketio.on("set_system_prompt")
def handle_set_prompt(data):
    """Update the system prompt."""
    new_prompt = data.get("prompt", "").strip()
    if new_prompt:
        set_system_prompt(new_prompt)
        print("✏️  System prompt updated")
        emit("status", {"message": "System prompt saved", "type": "success"})
    else:
        emit("status", {"message": "Prompt cannot be empty", "type": "error"})


@socketio.on("gesture")
def handle_gesture(data):
    """Handle gesture events from the frontend."""
    gesture_type = data.get("type", "")
    if gesture_type:
        result = execute_gesture(gesture_type)
        print(f"🖐️ Gesture: {gesture_type} → {result}")


@socketio.on("presence")
def handle_presence(data):
    """Handle presence detection events from the frontend webcam."""
    present = data.get("present", True)
    if not present:
        # User walked away — dim screen
        print("👤 Presence: user away — dimming screen")
        try:
            set_brightness("20")
        except Exception:
            pass
        emit("proactive_alert", {
            "message": "Screen dimmed — welcome back when you return, sir.",
            "severity": "info"
        })
    else:
        # User returned — restore brightness & greet
        print("👤 Presence: user returned — restoring screen")
        try:
            set_brightness("80")
        except Exception:
            pass
        # Send welcome-back TTS
        def _greet():
            audio_b64 = text_to_speech_base64("Welcome back, sir.")
            if audio_b64:
                socketio.emit("tts_audio", {"audio": audio_b64})
        threading.Thread(target=_greet, daemon=True).start()


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
    ║    AI System Controller v1.0         ║
    ║     http://localhost:5001            ║
    ╚══════════════════════════════════════╝
    """)

    # Start background services
    start_reminder_scheduler(socketio)
    start_clipboard_monitor()
    start_proactive_monitor(socketio)

    socketio.run(app, host="0.0.0.0", port=5001, debug=False, allow_unsafe_werkzeug=True)
