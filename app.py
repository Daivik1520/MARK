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

from core.ai_engine import get_ai_response, get_ai_response_streaming, reset_conversation, get_system_prompt, set_system_prompt, get_llm_backend, set_llm_backend
from core.tts_engine import text_to_speech_base64, get_available_voices, set_voice, get_current_voice, get_current_lang
from core.fast_router import try_fast_route
from core.system_controller import set_brightness, TOOL_MAP
from core.agentic import run_agentic_task, get_agentic_plan
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


@app.get("/api/voices")
async def api_voices():
    """Return the curated list of available TTS voices."""
    voices = get_available_voices()
    current = get_current_voice()
    return {"voices": voices, "current": current}


@app.post("/api/set_voice")
async def api_set_voice(request: Request):
    """Change the active TTS voice at runtime."""
    data = await request.json()
    voice_id = data.get("voice_id", "").strip()
    if not voice_id:
        return JSONResponse({"error": "voice_id required"}, status_code=400)
    ok = set_voice(voice_id)
    if ok:
        lang = get_current_lang()
        return {"success": True, "voice_id": voice_id, "lang": lang}
    return JSONResponse({"error": f"Unknown voice: {voice_id}"}, status_code=400)


@app.get("/api/llm_status")
async def api_llm_status():
    """Return current LLM backend and model status."""
    from core.local_llm import get_model_status
    return {
        "backend": get_llm_backend(),
        "local_model": get_model_status(),
    }


@app.post("/api/agentic")
async def api_agentic(request: Request):
    """Execute a complex multi-step task using the agentic loop."""
    data = await request.json()
    task = data.get("task", "").strip()
    max_steps = data.get("max_steps", 15)
    if not task:
        return JSONResponse({"error": "No task provided"}, status_code=400)

    result = await asyncio.to_thread(run_agentic_task, task, max_steps)
    return result


@app.post("/api/agentic_plan")
async def api_agentic_plan(request: Request):
    """Get a plan for a task without executing it."""
    data = await request.json()
    task = data.get("task", "").strip()
    if not task:
        return JSONResponse({"error": "No task provided"}, status_code=400)

    plan = await asyncio.to_thread(get_agentic_plan, task)
    return {"plan": plan}


@app.get("/api/mcp_status")
async def api_mcp_status():
    """Get MCP server connection status."""
    from core.mcp_client import mcp_get_status_sync
    return {"servers": mcp_get_status_sync()}


@app.post("/api/mcp_connect")
async def api_mcp_connect(request: Request):
    """Connect to MCP servers."""
    data = await request.json()
    server_name = data.get("server_name", "all")
    from core.mcp_client import mcp_connect
    result = await asyncio.to_thread(mcp_connect, server_name)
    return {"result": result}


@app.post("/api/set_llm_backend")
async def api_set_llm_backend(request: Request):
    """Switch LLM backend (currently only 'local' supported)."""
    data = await request.json()
    backend = data.get("backend", "").strip()
    if backend == "local":
        # Pre-load model in background thread
        import threading
        from core.local_llm import load_model
        threading.Thread(target=load_model, daemon=True).start()
    ok = set_llm_backend(backend)
    if ok:
        return {"success": True, "backend": backend}
    return JSONResponse({"error": f"Invalid backend: {backend}. Use: local"}, status_code=400)



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

            # TTS in background — starts playing immediately (non-blocking)
            asyncio.create_task(_send_tts(ai_text, sid))
            await sio.emit("thinking", {"status": False}, to=sid)
            return

        # Check if this is a complex multi-step task that needs agentic mode
        agentic_triggers = [
            "and then", "step by step", "after that", "first ", "next ",
            "create a project", "set up", "build me", "install and configure",
            "find and replace", "search and", "download and",
            "write a script that", "make a program that",
            "automate", "do all", "complete the following",
        ]
        user_lower = user_text.lower()
        is_agentic = any(trigger in user_lower for trigger in agentic_triggers)

        if is_agentic:
            # AGENTIC PATH: Multi-step autonomous execution
            print(f"🧠 AGENTIC MODE: \"{user_text[:60]}...\"")

            async def on_agentic_step(step_num, step_info):
                tool_names = [tc["name"] for tc in step_info.get("tool_calls", [])]
                msg = step_info.get("ai_text") or f"Step {step_num}: {', '.join(tool_names)}" if tool_names else f"Step {step_num}: thinking..."
                await sio.emit("agentic_step", {
                    "step": step_num,
                    "message": msg[:200],
                    "tools": tool_names,
                }, to=sid)

            # Run agentic loop (sync callback won't work directly, so we skip on_step for now)
            result = await asyncio.to_thread(run_agentic_task, user_text, 15)
            elapsed = round(time.time() - start, 2)

            ai_text = result["text"]
            tool_calls = result.get("tool_calls")
            step_count = result.get("step_count", 0)
            print(f"🧠 AGENTIC DONE: {step_count} steps, {elapsed}s")

            await sio.emit("ai_response", {
                "text": ai_text,
                "tool_calls": tool_calls,
                "response_time": elapsed,
                "agentic": True,
                "steps": step_count,
            }, to=sid)
        else:
            # STREAMING PATH: LLM streams text → TTS starts on first sentence
            from core.tts_engine import get_current_voice, _current_rate, _current_pitch

            voice = get_current_voice()
            rate = _current_rate
            pitch = _current_pitch

            sentences_yielded = 0
            full_text = ""
            tool_calls = None
            tts_tasks = []
            queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _run_streaming():
                """Run sync generator in thread, push events to async queue."""
                for event in get_ai_response_streaming(user_text):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            # Start LLM streaming in background thread
            stream_task = asyncio.create_task(asyncio.to_thread(_run_streaming))

            # Process events as they arrive
            while True:
                event = await queue.get()
                if event is None:
                    break

                if event["type"] == "sentence":
                    sentences_yielded += 1
                    sentence_text = event["text"]
                    # Fire off TTS generation for this sentence immediately
                    tts_task = asyncio.create_task(
                        _emit_tts_chunk(sentence_text, sentences_yielded - 1, voice, rate, pitch, sid)
                    )
                    tts_tasks.append(tts_task)

                elif event["type"] == "done":
                    full_text = event["text"]
                    tool_calls = event.get("tool_calls")

            await stream_task  # Ensure thread is done

            elapsed = round(time.time() - start, 2)
            ai_text = full_text
            print(f"🤖 MARK: {ai_text[:80]} ({elapsed}s)")

            await sio.emit("ai_response", {
                "text": ai_text,
                "tool_calls": tool_calls,
                "response_time": elapsed,
            }, to=sid)

            # If we streamed sentences, wait for all TTS tasks and emit final marker
            if tts_tasks:
                await asyncio.gather(*tts_tasks, return_exceptions=True)
                # Emit a final marker so client knows streaming is done
                await sio.emit("tts_chunk", {
                    "audio": "",
                    "index": sentences_yielded,
                    "total": sentences_yielded,
                    "text": "",
                    "final": True,
                    "streaming": True,
                }, to=sid)
            elif tool_calls:
                # Tool call path — TTS the result normally
                asyncio.create_task(_send_tts(ai_text, sid))
            else:
                # No sentences were streamed (very short response) — TTS normally
                asyncio.create_task(_send_tts(ai_text, sid))

    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(f"❌ {error_msg}")
        await sio.emit("ai_response", {"text": error_msg, "tool_calls": None}, to=sid)

    finally:
        await sio.emit("thinking", {"status": False}, to=sid)


async def _send_tts(text, sid=None):
    """Generate TTS audio in streaming chunks and emit each sentence independently.
    First sentence starts playing within ~300ms — near-zero perceived latency."""
    from core.streaming_tts import stream_tts_chunks, split_into_chunks
    from core.tts_engine import get_current_voice, _current_rate, _current_pitch

    try:
        voice = get_current_voice()
        rate = _current_rate
        pitch = _current_pitch

        chunks = split_into_chunks(text)
        if not chunks:
            return

        # If it's a short response (1-2 sentences), use the fast single-chunk path
        if len(chunks) <= 2:
            audio_b64 = await asyncio.to_thread(text_to_speech_base64, text)
            if audio_b64:
                if sid:
                    await sio.emit("tts_audio", {"audio": audio_b64}, to=sid)
                else:
                    await sio.emit("tts_audio", {"audio": audio_b64})
            return

        # Streaming path: emit each sentence's audio as soon as it's ready
        chunk_count = 0
        async for chunk_data in stream_tts_chunks(text, voice, rate, pitch):
            emit_data = {
                "audio": chunk_data["audio"],
                "index": chunk_data["index"],
                "total": chunk_data["total"],
                "text": chunk_data["text"],
                "final": chunk_data["final"],
                "streaming": True,
            }
            if sid:
                await sio.emit("tts_chunk", emit_data, to=sid)
            else:
                await sio.emit("tts_chunk", emit_data)
            chunk_count += 1

        print(f"  🔊 Streamed {chunk_count} TTS chunks")

    except Exception as e:
        print(f"  TTS streaming error: {e}")
        # Fallback to non-streaming
        try:
            audio_b64 = await asyncio.to_thread(text_to_speech_base64, text)
            if audio_b64:
                if sid:
                    await sio.emit("tts_audio", {"audio": audio_b64}, to=sid)
                else:
                    await sio.emit("tts_audio", {"audio": audio_b64})
        except Exception:
            pass


async def _emit_tts_chunk(text, index, voice, rate, pitch, sid=None):
    """Generate TTS for a single sentence and emit it as a streaming chunk."""
    from core.streaming_tts import generate_tts_chunk
    try:
        audio_b64 = await generate_tts_chunk(text, voice, rate, pitch)
        if audio_b64:
            emit_data = {
                "audio": audio_b64,
                "index": index,
                "total": -1,  # Unknown total during streaming
                "text": text,
                "final": False,
                "streaming": True,
            }
            if sid:
                await sio.emit("tts_chunk", emit_data, to=sid)
            else:
                await sio.emit("tts_chunk", emit_data)
    except Exception as e:
        print(f"  TTS chunk error for sentence {index}: {e}")


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
    print("""
    ╔══════════════════════════════════════╗
    ║         M.A.R.K. SYSTEM              ║
    ║    AI System Controller v2.0         ║
    ║     http://localhost:5001            ║
    ║     ⚡ Local Gemma 2 2B (GPU)        ║
    ╚══════════════════════════════════════╝
    """)

    # Pre-load the local model in background
    import threading
    from core.local_llm import load_model
    threading.Thread(target=load_model, daemon=True).start()

    # Start background services in thread pool (each guarded against crash)
    loop = asyncio.get_event_loop()

    # Reminder scheduler needs the sio instance wrapped for compatibility
    class SioCompat:
        """Thin wrapper so legacy services can call .emit() synchronously."""
        def emit(self, event, data=None):
            asyncio.run_coroutine_threadsafe(sio.emit(event, data), loop)

    sio_compat = SioCompat()

    try:
        await asyncio.to_thread(start_reminder_scheduler, sio_compat)
    except Exception as e:
        print(f"⚠️  Reminder scheduler error: {e}")

    try:
        await asyncio.to_thread(start_clipboard_monitor)
    except Exception as e:
        print(f"⚠️  Clipboard monitor error: {e}")

    try:
        await asyncio.to_thread(start_proactive_monitor, sio_compat)
    except Exception as e:
        print(f"⚠️  Proactive monitor error: {e}")

    try:
        focus_set_socketio(sio_compat)
    except Exception as e:
        print(f"⚠️  Focus bubble error: {e}")

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

    # Auto-connect MCP servers (if configured)
    try:
        from core.mcp_client import mcp_connect_all_sync, list_server_configs
        config = list_server_configs()
        if config:
            print(f"🔌 MCP: Connecting to {len(config)} configured server(s)...")
            result = await asyncio.to_thread(mcp_connect_all_sync)
            connected = result.get("connected", [])
            failed = result.get("failed", [])
            if connected:
                print(f"  ✓ MCP connected: {', '.join(connected)}")
            if failed:
                print(f"  ✗ MCP failed: {', '.join(failed)}")
        else:
            print("🔌 MCP: No servers configured (add to mcp_servers.json)")
    except Exception as e:
        print(f"⚠️  MCP startup error: {e}")

    # Start dictation service (if available)
    try:
        from services.dictation import start_dictation
        await asyncio.to_thread(start_dictation, sio_compat)
        print("🎙️  Dictation service started (Ctrl+Shift+Space)")
    except ImportError:
        print("⚠️  Dictation service not available (install openai-whisper)")
    except Exception as e:
        print(f"⚠️  Dictation service error: {e}")

    # Command palette (rumps) requires macOS main thread — cannot run under uvicorn.
    # Skipping to prevent SIGABRT. Use standalone launcher for menubar integration.
    print("⚠️  Command Palette skipped (rumps needs main thread)")


# Mount static files AFTER routes so / route takes priority
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=5001, log_level="info")
