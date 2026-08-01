"""
MARK — Main Application Server (FastAPI + async Socket.IO)

Fully asynchronous. Model inference and other blocking work runs in a thread
pool so the event loop stays responsive while Gemma is decoding.
"""

import os
import time
import asyncio
import contextlib
import socketio
import uvicorn
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from core.ai_engine import (
    get_ai_response, get_ai_response_streaming, reset_conversation,
    get_system_prompt, set_system_prompt, get_llm_backend, set_llm_backend,
)
from core.fast_router import try_fast_route
from core.tts_engine import (
    text_to_speech_base64, get_available_voices, set_voice,
    get_current_voice, get_current_lang,
)
from core.system_controller import set_brightness, TOOL_MAP
from core.agentic import run_agentic_task, get_agentic_plan, should_use_agent
from core import permissions
from core.tool_executor import get_pending
from tools.reminder_manager import start_scheduler as start_reminder_scheduler
from tools.clipboard_manager import start_clipboard_monitor
from services.gesture_controller import execute_gesture
from services.proactive_monitor import start_proactive_monitor
from services.focus_bubble import set_socketio as focus_set_socketio
from tools.iot_controller import get_iot_state_dict, control_iot_device, list_iot_devices
from tools.virtual_mouse import (
    move_virtual_mouse, virtual_mouse_click, virtual_mouse_dpad,
    virtual_mouse_scroll, get_virtual_mouse_state,
)

load_dotenv()

PORT = int(os.getenv("PORT", "3000"))

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


# ─────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────

class SioBridge:
    """Lets synchronous background services emit on the async Socket.IO server."""

    def __init__(self, server, loop):
        self._sio = server
        self._loop = loop

    def emit(self, event, data=None):
        try:
            asyncio.run_coroutine_threadsafe(self._sio.emit(event, data), self._loop)
        except Exception as e:
            print(f"  ⚠️  Emit failed for {event}: {e}")


def _start_service(name, fn, *args):
    """Run a startup hook, reporting failure without taking the server down."""
    try:
        fn(*args)
        return True
    except Exception as e:
        print(f"  ⚠️  {name}: {e}")
        return False


@contextlib.asynccontextmanager
async def lifespan(app):
    print(f"""
    ╔════════════════════════════════════════════╗
    ║              M.A.R.K.  v3.0                ║
    ║        AI System Controller                ║
    ║        http://localhost:{PORT}               ║
    ║        Local Gemma 3 4B — Metal GPU        ║
    ╚════════════════════════════════════════════╝
    """)

    loop = asyncio.get_running_loop()
    bridge = SioBridge(sio, loop)

    # HUD card needs the socket server, so it is bound here rather than at import.
    def show_hud_card(title="MARK HUD", content="", icon="🔮", duration=8):
        try:
            duration = int(duration)
        except (ValueError, TypeError):
            duration = 8
        bridge.emit("hud_card", {"title": title, "content": content,
                                 "icon": icon, "duration": duration})
        return f"HUD card displayed: {title}"

    TOOL_MAP["show_hud_card"] = show_hud_card

    await asyncio.to_thread(_start_service, "Reminder scheduler", start_reminder_scheduler, bridge)
    await asyncio.to_thread(_start_service, "Clipboard monitor", start_clipboard_monitor)
    await asyncio.to_thread(_start_service, "Proactive monitor", start_proactive_monitor, bridge)
    _start_service("Focus bubble", focus_set_socketio, bridge)

    # Ambient triggers — calendar-free, purely local signals.
    try:
        from services.proactive_triggers import start_triggers
        await asyncio.to_thread(start_triggers, bridge)
    except Exception as e:
        print(f"  ⚠️  Proactive triggers: {e}")

    # Dictation hotkey.
    try:
        from services.dictation import start_dictation
        await asyncio.to_thread(start_dictation, bridge)
    except Exception as e:
        print(f"  ⚠️  Dictation: {e}")

    # MCP servers.
    try:
        from core.mcp_client import (
            mcp_connect_all_sync, list_server_configs, enabled_server_configs,
        )
        all_servers = list_server_configs()
        enabled = enabled_server_configs()
        if enabled:
            result = await asyncio.to_thread(mcp_connect_all_sync)
            if result.get("connected"):
                print(f"  🔌 MCP: connected — {', '.join(result['connected'])}")
            if result.get("failed"):
                print(f"  🔌 MCP: could not reach {', '.join(result['failed'])} "
                      f"(they stay off; nothing else is affected)")
        elif all_servers:
            print(f"  🔌 MCP: {len(all_servers)} servers available, all off. "
                  f"Say \"enable the filesystem MCP server\" to switch one on.")
        else:
            print("  🔌 MCP: no servers configured")
    except Exception as e:
        print(f"  ⚠️  MCP: {e}")

    # Menu-bar command palette. rumps needs the main thread, which uvicorn owns,
    # so it runs as its own process and talks to us over the REST API.
    try:
        from services.command_palette import launch_detached
        launch_detached(PORT)
    except Exception as e:
        print(f"  ⚠️  Command palette: {e}")

    # Warm the model last, in the background, so the first request does not pay
    # for loading it. It runs after the other services have finished printing:
    # silencing ggml's startup chatter means redirecting file descriptor 2,
    # which is process-wide, so overlapping it with other output loses lines.
    import threading
    from core.local_llm import load_model
    threading.Thread(target=load_model, daemon=True, name="model-warmup").start()

    print(f"\n  ✅ MARK is live at http://localhost:{PORT}\n")

    yield

    # ── Shutdown ──
    try:
        from services.command_palette import stop_detached
        stop_detached()
    except Exception:
        pass
    try:
        from core.mcp_client import mcp_disconnect_all_sync
        await asyncio.to_thread(mcp_disconnect_all_sync)
    except Exception:
        pass
    print("  👋 MARK stopped.")


app = FastAPI(title="MARK AI System Controller", lifespan=lifespan)
socket_app = socketio.ASGIApp(sio, app)


# ─────────────────────────────────────────────
# REST ROUTES
# ─────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def api_health():
    """Readiness probe — used by the command palette and by tests."""
    from core.local_llm import get_model_status
    return {
        "ok": True,
        "model": get_model_status(),
        "backend": get_llm_backend(),
        "pending_confirmation": get_pending(),
    }


@app.post("/upload_3d")
async def upload_3d(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "No file selected"}, status_code=400)
    os.makedirs("static/uploads", exist_ok=True)
    safe = os.path.basename(file.filename).replace("/", "_").replace("\\", "_")
    path = os.path.join("static/uploads", safe)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"url": f"/static/uploads/{safe}", "name": safe}


@app.post("/api/command")
async def api_command(request: Request):
    """Single-shot command endpoint used by the palette and external callers."""
    data = await request.json()
    command = (data.get("command") or "").strip()
    if not command:
        return JSONResponse({"error": "No command"}, status_code=400)

    fast = await asyncio.to_thread(try_fast_route, command)
    if fast:
        return {"response": fast["text"], "tool_calls": fast["tool_calls"], "fast": True}

    result = await asyncio.to_thread(get_ai_response, command)
    return {"response": result["text"], "tool_calls": result.get("tool_calls"), "fast": False}


@app.get("/api/voices")
async def api_voices():
    return {"voices": get_available_voices(), "current": get_current_voice()}


@app.post("/api/set_voice")
async def api_set_voice(request: Request):
    data = await request.json()
    voice_id = (data.get("voice_id") or "").strip()
    if not voice_id:
        return JSONResponse({"error": "voice_id required"}, status_code=400)
    if set_voice(voice_id):
        return {"success": True, "voice_id": voice_id, "lang": get_current_lang()}
    return JSONResponse({"error": f"Unknown voice: {voice_id}"}, status_code=400)


@app.get("/api/llm_status")
async def api_llm_status():
    from core.local_llm import get_model_status, has_vision_projector, vision_model_enabled
    return {
        "backend": get_llm_backend(),
        "local_model": get_model_status(),
        "vision_projector_present": has_vision_projector(),
        "vision_model_enabled": vision_model_enabled(),
    }


@app.post("/api/set_llm_backend")
async def api_set_llm_backend(request: Request):
    data = await request.json()
    backend = (data.get("backend") or "").strip()
    if backend == "local":
        import threading
        from core.local_llm import load_model
        threading.Thread(target=load_model, daemon=True).start()
    if set_llm_backend(backend):
        return {"success": True, "backend": backend}
    return JSONResponse(
        {"error": f"Invalid backend: {backend}. Use 'local' or 'ollama'."},
        status_code=400,
    )


@app.post("/api/agentic")
async def api_agentic(request: Request):
    data = await request.json()
    task = (data.get("task") or "").strip()
    if not task:
        return JSONResponse({"error": "No task provided"}, status_code=400)
    max_steps = int(data.get("max_steps", 10))
    return await asyncio.to_thread(run_agentic_task, task, max_steps)


@app.post("/api/agentic_plan")
async def api_agentic_plan(request: Request):
    data = await request.json()
    task = (data.get("task") or "").strip()
    if not task:
        return JSONResponse({"error": "No task provided"}, status_code=400)
    return {"plan": await asyncio.to_thread(get_agentic_plan, task)}


# ── Safety layer ──

@app.get("/api/permissions")
async def api_permissions():
    return {
        "pending": get_pending(),
        "auto_approve": permissions.is_auto_approve(),
        "undoable": permissions.list_undo(5),
    }


@app.post("/api/permissions/resolve")
async def api_resolve_permission(request: Request):
    from core.tool_executor import resolve_pending
    data = await request.json()
    decision = "yes" if data.get("approve") else "no"
    text, calls = await asyncio.to_thread(resolve_pending, decision)
    return {"response": text, "tool_calls": calls}


@app.post("/api/undo")
async def api_undo():
    return {"response": await asyncio.to_thread(permissions.undo_last)}


@app.get("/api/audit")
async def api_audit(count: int = 25):
    return {"log": permissions.recent_audit(count)}


# ── MCP ──

@app.get("/api/mcp_status")
async def api_mcp_status():
    from core.mcp_client import mcp_get_status_sync
    return {"servers": mcp_get_status_sync()}


@app.post("/api/mcp_connect")
async def api_mcp_connect(request: Request):
    data = await request.json()
    from core.mcp_client import mcp_connect
    return {"result": await asyncio.to_thread(mcp_connect, data.get("server_name", "all"))}


# ── IoT & virtual mouse ──

@app.get("/api/iot/devices")
async def api_get_iot_devices():
    return get_iot_state_dict()


@app.post("/api/iot/control")
async def api_control_iot_device(request: Request):
    data = await request.json()
    msg = control_iot_device(data.get("device", ""), data.get("action", ""), data.get("value"))
    return {"message": msg, "devices": get_iot_state_dict()}


@app.get("/api/virtual_mouse/state")
async def api_virtual_mouse_state():
    return get_virtual_mouse_state()


# ─────────────────────────────────────────────
# SOCKET.IO
# ─────────────────────────────────────────────

@sio.on("connect")
async def handle_connect(sid, environ):
    print("🔌 Client connected")
    await sio.emit("status", {"message": "Connected to MARK", "type": "success"}, to=sid)
    await sio.emit("iot_state_update", get_iot_state_dict(), to=sid)
    await sio.emit("virtual_mouse_update", get_virtual_mouse_state(), to=sid)
    pending = get_pending()
    if pending:
        await sio.emit("confirmation_required", pending, to=sid)


@sio.on("disconnect")
async def handle_disconnect(sid):
    print("🔌 Client disconnected")


@sio.on("iot_control")
async def handle_iot_control(sid, data):
    msg = control_iot_device(data.get("device_id"), data.get("action", "toggle"), data.get("value"))
    await sio.emit("iot_state_update", get_iot_state_dict())
    await sio.emit("status", {"message": msg, "type": "info"}, to=sid)


@sio.on("virtual_mouse_move")
async def handle_vmouse_move(sid, data):
    move_virtual_mouse(data.get("x", 0), data.get("y", 0),
                       relative=data.get("relative", False), mode=data.get("mode"))
    await sio.emit("virtual_mouse_update", get_virtual_mouse_state())


@sio.on("virtual_mouse_click")
async def handle_vmouse_click(sid, data):
    msg = virtual_mouse_click(button=data.get("button", "left"))
    await sio.emit("virtual_mouse_update", get_virtual_mouse_state())
    await sio.emit("iot_state_update", get_iot_state_dict())
    await sio.emit("status", {"message": msg, "type": "info"}, to=sid)


@sio.on("virtual_mouse_dpad")
async def handle_vmouse_dpad(sid, data):
    virtual_mouse_dpad(data.get("direction", "right"), data.get("step", 50))
    await sio.emit("virtual_mouse_update", get_virtual_mouse_state())


@sio.on("virtual_mouse_scroll")
async def handle_vmouse_scroll(sid, data):
    virtual_mouse_scroll(data.get("direction", "down"), data.get("amount", 3))
    await sio.emit("virtual_mouse_update", get_virtual_mouse_state())


# ─────────────────────────────────────────────
# CONVERSATION
# ─────────────────────────────────────────────

@sio.on("user_message")
async def handle_message(sid, data):
    """
    Handle one turn.

    Three paths:
      fast    — deterministic shortcut, no model involved
      agent   — genuine multi-step task, streamed step by step
      chat    — model turn, streamed sentence by sentence into TTS
    """
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return

    print(f"\n👤 {user_text}")
    await sio.emit("thinking", {"status": True}, to=sid)
    start = time.time()

    try:
        # ── Fast path ──
        fast = await asyncio.to_thread(try_fast_route, user_text)
        if fast:
            elapsed = round(time.time() - start, 2)
            print(f"⚡ FAST: {fast['tool_calls'][0]['name']} ({elapsed}s)")
            await sio.emit("ai_response", {
                "text": fast["text"], "tool_calls": fast["tool_calls"],
                "response_time": elapsed, "fast": True,
            }, to=sid)
            await _speak(fast["text"], sid)
            return

        # ── Agent path ──
        if should_use_agent(user_text):
            print("🧠 AGENT MODE")
            await _run_agent(user_text, sid, start)
            return

        # ── Chat path (streamed) ──
        await _run_chat(user_text, sid, start)

    except Exception as e:
        import traceback
        traceback.print_exc()
        message = "Something went wrong on my end, sir. Try that again?"
        await sio.emit("ai_response", {"text": message, "tool_calls": None}, to=sid)
        await _speak(message, sid)

    finally:
        await sio.emit("thinking", {"status": False}, to=sid)


async def _run_chat(user_text, sid, start):
    """Stream a model turn, synthesising each sentence as it lands."""
    from core.tts_engine import get_current_voice, _current_rate, _current_pitch

    voice, rate, pitch = get_current_voice(), _current_rate, _current_pitch

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def produce():
        try:
            for event in get_ai_response_streaming(user_text):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait,
                                      {"type": "done", "text": f"Error: {e}", "tool_calls": None})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    producer = asyncio.create_task(asyncio.to_thread(produce))

    tts_tasks = []
    index = 0
    final_text = ""
    tool_calls = None
    first_audio_at = None

    while True:
        event = await queue.get()
        if event is None:
            break

        kind = event.get("type")

        if kind == "tool":
            await sio.emit("tool_used", {"name": event["name"],
                                         "result": str(event["result"])[:400]}, to=sid)
            if "needs your go-ahead" in str(event.get("result", "")):
                await sio.emit("confirmation_required", get_pending() or {}, to=sid)

        elif kind == "sentence":
            if first_audio_at is None:
                first_audio_at = round(time.time() - start, 2)
            tts_tasks.append(asyncio.create_task(
                _emit_tts_chunk(event["text"], index, voice, rate, pitch, sid)
            ))
            index += 1

        elif kind == "done":
            final_text = event["text"]
            tool_calls = event.get("tool_calls")

    await producer

    elapsed = round(time.time() - start, 2)
    if first_audio_at:
        print(f"  ⏱  first audio {first_audio_at}s · total {elapsed}s")

    await sio.emit("ai_response", {
        "text": final_text, "tool_calls": tool_calls, "response_time": elapsed,
    }, to=sid)

    if tts_tasks:
        await asyncio.gather(*tts_tasks, return_exceptions=True)
        await sio.emit("tts_chunk", {
            "audio": "", "index": index, "total": index,
            "text": "", "final": True, "streaming": True,
        }, to=sid)
    elif final_text:
        await _speak(final_text, sid)


async def _run_agent(user_text, sid, start):
    """Run a multi-step task, reporting each step to the UI as it happens."""
    loop = asyncio.get_running_loop()

    def on_step(step_num, record):
        tools = [c["name"] for c in record.get("tool_calls", [])]
        asyncio.run_coroutine_threadsafe(sio.emit("agentic_step", {
            "step": step_num,
            "message": record.get("ai_text", "")[:200],
            "tools": tools,
        }, to=sid), loop)

    result = await asyncio.to_thread(run_agentic_task, user_text, 10, on_step)
    elapsed = round(time.time() - start, 2)
    print(f"🧠 AGENT DONE: {result['step_count']} steps in {elapsed}s")

    await sio.emit("ai_response", {
        "text": result["text"],
        "tool_calls": result.get("tool_calls"),
        "response_time": elapsed,
        "agentic": True,
        "steps": result["step_count"],
    }, to=sid)

    if get_pending():
        await sio.emit("confirmation_required", get_pending(), to=sid)

    await _speak(result["text"], sid)


# ─────────────────────────────────────────────
# SPEECH
# ─────────────────────────────────────────────

async def _emit_tts_chunk(text, index, voice, rate, pitch, sid=None):
    """Synthesise one sentence and push it to the client."""
    from core.streaming_tts import generate_tts_chunk
    try:
        audio = await generate_tts_chunk(text, voice, rate, pitch)
        if not audio:
            return
        payload = {"audio": audio, "index": index, "total": -1,
                   "text": text, "final": False, "streaming": True}
        await (sio.emit("tts_chunk", payload, to=sid) if sid else sio.emit("tts_chunk", payload))
    except Exception as e:
        print(f"  TTS chunk {index} failed: {e}")


async def _speak(text, sid=None):
    """Synthesise a complete utterance (used off the streaming path)."""
    from core.streaming_tts import stream_tts_chunks, split_into_chunks
    from core.tts_engine import get_current_voice, _current_rate, _current_pitch

    if not text:
        return
    try:
        chunks = split_into_chunks(text)
        if not chunks:
            return

        if len(chunks) <= 2:
            audio = await asyncio.to_thread(text_to_speech_base64, text)
            if audio:
                payload = {"audio": audio}
                await (sio.emit("tts_audio", payload, to=sid) if sid else sio.emit("tts_audio", payload))
            return

        voice, rate, pitch = get_current_voice(), _current_rate, _current_pitch
        async for chunk in stream_tts_chunks(text, voice, rate, pitch):
            payload = {**chunk, "streaming": True}
            await (sio.emit("tts_chunk", payload, to=sid) if sid else sio.emit("tts_chunk", payload))

    except Exception as e:
        print(f"  TTS error: {e}")


# ─────────────────────────────────────────────
# MISC EVENTS
# ─────────────────────────────────────────────

@sio.on("reset_chat")
async def handle_reset(sid):
    reset_conversation()
    await sio.emit("status", {"message": "Conversation reset", "type": "info"}, to=sid)


@sio.on("clap_activate")
async def handle_clap_activate(sid):
    print("👏 Clap detected")
    await _speak("I'm here, sir.", sid)


@sio.on("get_system_prompt")
async def handle_get_prompt(sid):
    await sio.emit("system_prompt", {"prompt": get_system_prompt()}, to=sid)


@sio.on("set_system_prompt")
async def handle_set_prompt(sid, data):
    prompt = (data.get("prompt") or "").strip()
    if prompt:
        set_system_prompt(prompt)
        await sio.emit("status", {"message": "System prompt saved", "type": "success"}, to=sid)
    else:
        await sio.emit("status", {"message": "Prompt cannot be empty", "type": "error"}, to=sid)


@sio.on("gesture")
async def handle_gesture(sid, data):
    gesture = data.get("type", "")
    if gesture:
        result = await asyncio.to_thread(execute_gesture, gesture)
        print(f"🖐️  Gesture: {gesture} → {result}")


@sio.on("presence")
async def handle_presence(sid, data):
    if not data.get("present", True):
        print("👤 User away — dimming")
        with contextlib.suppress(Exception):
            await asyncio.to_thread(set_brightness, "20")
        await sio.emit("proactive_alert", {
            "message": "Screen dimmed — welcome back when you return, sir.",
            "severity": "info",
        }, to=sid)
    else:
        print("👤 User back — restoring")
        with contextlib.suppress(Exception):
            await asyncio.to_thread(set_brightness, "80")
        await _speak("Welcome back, sir.", sid)


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=PORT, log_level="warning")
