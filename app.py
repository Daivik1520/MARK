"""
MARK — Main Application Server (FastAPI + Async SocketIO)
Fully asynchronous server powering the MARK AI System Controller.
Uses uvicorn + python-socketio for zero-blocking concurrency.
"""

import os
import time
import asyncio
import socketio
import uvicorn
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from core.ai_engine import get_ai_response, reset_conversation, get_system_prompt, set_system_prompt
from core.tts_engine import text_to_speech_base64
from core.fast_router import try_fast_route
from core.system_controller import set_brightness, TOOL_MAP
from tools.reminder_manager import start_scheduler as start_reminder_scheduler
from tools.clipboard_manager import start_clipboard_monitor
from services.gesture_controller import execute_gesture
from services.proactive_monitor import start_proactive_monitor
from services.focus_bubble import set_socketio as focus_set_socketio

load_dotenv()

# ─────────────────────────────────────────────
# FASTAPI + ASYNC SOCKETIO SETUP
# ─────────────────────────────────────────────

app = FastAPI(title="MARK AI System Controller")
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, app)


# ─────────────────────────────────────────────
# REST ROUTES
# ─────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/upload_3d")
async def upload_3d(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "No file selected"}, status_code=400)
    os.makedirs("static/uploads", exist_ok=True)
    safe = file.filename.replace("/", "_").replace("\\", "_")
    path = os.path.join("static/uploads", safe)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"url": f"/static/uploads/{safe}", "name": safe}


@app.post("/api/command")
async def api_command(request: Request):
    """REST endpoint for the Floating Command Palette and external integrations."""
    data = await request.json()
    command = data.get("command", "").strip()
    if not command:
        return JSONResponse({"error": "No command"}, status_code=400)

    # Fast path first
    fast = try_fast_route(command)
    if fast:
        return {"response": fast["text"], "fast": True}

    # Slow path: AI
    result = await asyncio.to_thread(get_ai_response, command)
    return {"response": result["text"], "tool_calls": result.get("tool_calls"), "fast": False}


# ─────────────────────────────────────────────
# SOCKETIO EVENTS
# ─────────────────────────────────────────────

@sio.on("connect")
async def handle_connect(sid, environ):
    print("🔌 Client connected")
    await sio.emit("status", {"message": "Connected to MARK", "type": "success"}, to=sid)


@sio.on("disconnect")
async def handle_disconnect(sid):
    print("🔌 Client disconnected")


@sio.on("user_message")
async def handle_message(sid, data):
    """Handle user text/voice message — fully async."""
    user_text = data.get("message", "").strip()
    if not user_text:
        return

    print(f"👤 User: {user_text}")
    await sio.emit("thinking", {"status": True}, to=sid)

    try:
        start = time.time()

        # ⚡ FAST PATH: instant local regex match (no AI, no network)
        fast_result = try_fast_route(user_text)
        if fast_result:
            elapsed = round(time.time() - start, 4)
            ai_text = fast_result["text"]
            tool_calls = fast_result.get("tool_calls")
            print(f"⚡ FAST: {ai_text[:80]} ({elapsed}s)")

            await sio.emit("ai_response", {
                "text": ai_text,
                "tool_calls": tool_calls,
                "response_time": elapsed,
            }, to=sid)

            # TTS in background (non-blocking)
            asyncio.create_task(_send_tts(ai_text))
            await sio.emit("thinking", {"status": False}, to=sid)
            return

        # SLOW PATH: Full AI processing in thread pool (non-blocking)
        result = await asyncio.to_thread(get_ai_response, user_text)
        elapsed = round(time.time() - start, 2)

        ai_text = result["text"]
        tool_calls = result.get("tool_calls")
        print(f"🤖 MARK: {ai_text} ({elapsed}s)")

        await sio.emit("ai_response", {
            "text": ai_text,
            "tool_calls": tool_calls,
            "response_time": elapsed,
        }, to=sid)

        # TTS in background
        asyncio.create_task(_send_tts(ai_text))

    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(f"❌ {error_msg}")
        await sio.emit("ai_response", {"text": error_msg, "tool_calls": None}, to=sid)

    finally:
        await sio.emit("thinking", {"status": False}, to=sid)


async def _send_tts(text):
    """Generate TTS audio in background and broadcast."""
    try:
        audio_b64 = await asyncio.to_thread(text_to_speech_base64, text)
        if audio_b64:
            await sio.emit("tts_audio", {"audio": audio_b64})
    except Exception as e:
        print(f"  TTS error: {e}")


@sio.on("reset_chat")
async def handle_reset(sid):
    reset_conversation()
    await sio.emit("status", {"message": "Conversation reset", "type": "info"}, to=sid)


@sio.on("clap_activate")
async def handle_clap_activate(sid):
    print("👏👏 Clap activation triggered!")
    asyncio.create_task(_send_tts("Activating all services. M.A.R.K. activated."))


@sio.on("get_system_prompt")
async def handle_get_prompt(sid):
    await sio.emit("system_prompt", {"prompt": get_system_prompt()}, to=sid)


@sio.on("set_system_prompt")
async def handle_set_prompt(sid, data):
    new_prompt = data.get("prompt", "").strip()
    if new_prompt:
        set_system_prompt(new_prompt)
        print("✏️  System prompt updated")
        await sio.emit("status", {"message": "System prompt saved", "type": "success"}, to=sid)
    else:
        await sio.emit("status", {"message": "Prompt cannot be empty", "type": "error"}, to=sid)


@sio.on("gesture")
async def handle_gesture(sid, data):
    gesture_type = data.get("type", "")
    if gesture_type:
        result = await asyncio.to_thread(execute_gesture, gesture_type)
        print(f"🖐️ Gesture: {gesture_type} → {result}")


@sio.on("presence")
async def handle_presence(sid, data):
    present = data.get("present", True)
    if not present:
        print("👤 Presence: user away — dimming screen")
        try:
            await asyncio.to_thread(set_brightness, "20")
        except Exception:
            pass
        await sio.emit("proactive_alert", {
            "message": "Screen dimmed — welcome back when you return, sir.",
            "severity": "info",
        }, to=sid)
    else:
        print("👤 Presence: user returned — restoring screen")
        try:
            await asyncio.to_thread(set_brightness, "80")
        except Exception:
            pass
        asyncio.create_task(_send_tts("Welcome back, sir."))


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("\n⚠️  WARNING: Set your OPENROUTER_API_KEY in .env file!")
        print("   Get one at: https://openrouter.ai/keys\n")

    print("""
    ╔══════════════════════════════════════╗
    ║         M.A.R.K. SYSTEM              ║
    ║    AI System Controller v2.0         ║
    ║     http://localhost:5001            ║
    ║     ⚡ FastAPI + Async SocketIO      ║
    ╚══════════════════════════════════════╝
    """)

    # Start background services in thread pool
    loop = asyncio.get_event_loop()

    # Reminder scheduler needs the sio instance wrapped for compatibility
    class SioCompat:
        """Thin wrapper so legacy services can call .emit() synchronously."""
        def emit(self, event, data=None):
            asyncio.run_coroutine_threadsafe(sio.emit(event, data), loop)

    sio_compat = SioCompat()

    await asyncio.to_thread(start_reminder_scheduler, sio_compat)
    await asyncio.to_thread(start_clipboard_monitor)
    await asyncio.to_thread(start_proactive_monitor, sio_compat)
    focus_set_socketio(sio_compat)

    # Register HUD card tool (needs sio instance)
    def show_hud_card(title="MARK HUD", content="", icon="🔮", duration=8):
        try:
            duration = int(duration)
        except (ValueError, TypeError):
            duration = 8
        asyncio.run_coroutine_threadsafe(
            sio.emit("hud_card", {"title": title, "content": content, "icon": icon, "duration": duration}),
            loop,
        )
        return f"HUD card displayed: {title}"

    TOOL_MAP["show_hud_card"] = show_hud_card

    # Start dictation service (if available)
    try:
        from services.dictation import start_dictation
        await asyncio.to_thread(start_dictation, sio_compat)
        print("🎙️  Dictation service started (Ctrl+Shift+Space)")
    except ImportError:
        print("⚠️  Dictation service not available (install openai-whisper)")
    except Exception as e:
        print(f"⚠️  Dictation service error: {e}")

    # Start command palette (if available)
    try:
        from services.command_palette import start_palette
        await asyncio.to_thread(start_palette)
        print("🎯 Command Palette active (Option+Space or menubar icon)")
    except ImportError:
        print("⚠️  Command palette not available (install rumps)")
    except Exception as e:
        print(f"⚠️  Command palette error: {e}")


# Mount static files AFTER routes so / route takes priority
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=5001, log_level="info")
