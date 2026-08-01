"""
MARK — Dictation

Press Option+D, speak, and the transcript is typed into whatever app is
focused.

Recognition uses Apple's on-device SFSpeechRecognizer when an audio recorder is
available, and falls back to triggering macOS's own dictation otherwise. The
previous implementation only simulated a double-Fn keypress: it never captured
audio and never inserted a transcript anywhere.
"""

import os
import re
import time
import threading
import subprocess
from shutil import which

_sio = None
_listener = None
_busy = threading.Lock()

HOTKEY_HINT = "Option+D"


def _notify(message, kind="info"):
    if _sio:
        try:
            _sio.emit("status", {"message": message, "type": kind})
        except Exception:
            pass


# ─────────────────────────────────────────────
# CAPTURE & TRANSCRIBE
# ─────────────────────────────────────────────

def _record(seconds=8, path="/tmp/mark_dictation.wav"):
    """Record from the default input device using ffmpeg or sox, if present."""
    candidates = [
        ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0", "-t", str(seconds),
         "-ar", "16000", "-ac", "1", path],
        ["rec", "-r", "16000", "-c", "1", path, "trim", "0", str(seconds)],
    ]
    for cmd in candidates:
        if not which(cmd[0]):
            continue
        try:
            subprocess.run(cmd, capture_output=True, timeout=seconds + 10)
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                return path
        except Exception:
            continue
    return None


def _transcribe(path):
    """Transcribe a wav file with Apple's on-device recogniser."""
    try:
        from Foundation import NSURL, NSRunLoop, NSDate
        import Speech
    except ImportError:
        return None

    try:
        recognizer = Speech.SFSpeechRecognizer.alloc().init()
        if recognizer is None or not recognizer.isAvailable():
            return None

        request = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(
            NSURL.fileURLWithPath_(path)
        )
        request.setRequiresOnDeviceRecognition_(True)

        state = {"text": None, "done": False}

        def handler(result, error):
            if error is not None:
                state["done"] = True
                return
            if result is not None:
                state["text"] = result.bestTranscription().formattedString()
                if result.isFinal():
                    state["done"] = True

        recognizer.recognitionTaskWithRequest_resultHandler_(request, handler)

        deadline = time.time() + 20
        loop = NSRunLoop.currentRunLoop()
        while not state["done"] and time.time() < deadline:
            loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

        return state["text"]
    except Exception:
        return None


def _type_text(text):
    """Insert text into the focused app via the clipboard."""
    if not text:
        return
    try:
        import pyperclip
        import pyautogui
        previous = ""
        try:
            previous = pyperclip.paste()
        except Exception:
            pass
        pyperclip.copy(text)
        time.sleep(0.08)
        pyautogui.hotkey("command", "v")
        time.sleep(0.15)
        if previous:
            try:
                pyperclip.copy(previous)
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  Could not insert dictated text: {e}")


def _fallback_system_dictation():
    """Trigger macOS's built-in dictation as a last resort."""
    script = ('tell application "System Events" to key code 63\n'
              'delay 0.1\n'
              'tell application "System Events" to key code 63')
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
        _notify("macOS dictation activated — speak now.", "info")
    except Exception:
        pass


def dictate_once(seconds=8):
    """Record, transcribe, then type. Safe to call from a hotkey thread."""
    if not _busy.acquire(blocking=False):
        return
    try:
        path = _record(seconds)
        if not path:
            _fallback_system_dictation()
            return

        _notify(f"Listening for {seconds} seconds...", "info")
        text = _transcribe(path)
        try:
            os.remove(path)
        except OSError:
            pass

        if not text or not text.strip():
            _notify("I didn't catch that, sir.", "warning")
            return

        text = re.sub(r"\s+", " ", text).strip()
        _type_text(text)
        _notify(f"Typed: {text[:60]}", "success")
        print(f"  🎙️  Dictated: {text[:80]}")
    finally:
        _busy.release()


# ─────────────────────────────────────────────
# HOTKEY
# ─────────────────────────────────────────────

_pressed = set()


def _on_press(key):
    _pressed.add(key)
    try:
        from pynput.keyboard import Key, KeyCode
        option = Key.alt in _pressed or Key.alt_l in _pressed or Key.alt_r in _pressed
        # Option+D on macOS produces "∂" rather than "d".
        is_d = isinstance(key, KeyCode) and key.char in ("d", "D", "∂")
        if option and is_d:
            _pressed.clear()
            threading.Thread(target=dictate_once, daemon=True).start()
    except Exception:
        pass


def _on_release(key):
    _pressed.discard(key)


def start_dictation(sio_instance=None):
    """Install the dictation hotkey listener."""
    global _sio, _listener
    _sio = sio_instance

    try:
        from pynput import keyboard
    except ImportError:
        print("  ⚠️  pynput not installed — dictation hotkey disabled")
        return

    try:
        _listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        _listener.daemon = True
        _listener.start()
        engine = ("Apple on-device speech" if (which("ffmpeg") or which("rec"))
                  else "macOS system dictation")
        print(f"  🎙️  Dictation ready — {HOTKEY_HINT} ({engine})")
    except Exception as e:
        print(f"  ⚠️  Dictation listener: {e}")
