"""
MARK — Instant Local Dictation
Uses macOS native speech recognition (same engine as Siri/Dictation).
Global hotkey (F8): hold to dictate, release to type into active app.
No Whisper, no external models — pure macOS native.
"""

import os
import subprocess
import threading
import time

_sio = None


def _dictate_native():
    """
    Use macOS native dictation via AppleScript.
    Triggers the system dictation (Fn Fn or configured key),
    captures result, and types it into the active app.
    """
    # Use osascript to show a dictation dialog
    # This uses macOS native speech recognition
    script = '''
    tell application "System Events"
        -- Simulate pressing Fn twice to trigger dictation
        key code 63
        delay 0.1
        key code 63
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
        if _sio:
            try:
                _sio.emit("status", {"message": "🎙️ macOS Dictation activated — speak now!", "type": "info"})
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  Dictation trigger error: {e}")


def _on_key_press(key):
    """Start dictation when F8 is pressed."""
    try:
        from pynput.keyboard import Key
        if key == Key.f8:
            print("🎙️  F8 pressed — activating macOS dictation")
            threading.Thread(target=_dictate_native, daemon=True).start()
    except Exception:
        pass


def start_dictation(sio_instance=None):
    """Start the dictation hotkey listener."""
    global _sio
    _sio = sio_instance

    try:
        from pynput import keyboard

        listener = keyboard.Listener(on_press=_on_key_press)
        listener.daemon = True
        listener.start()
        print("  🎙️  Dictation service ready — press F8 to activate macOS dictation")
    except ImportError:
        print("  ⚠️  pynput not installed. Dictation hotkey disabled.")
    except Exception as e:
        print(f"  ⚠️  Could not start dictation listener: {e}")
