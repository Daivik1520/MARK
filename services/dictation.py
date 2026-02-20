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


_pressed_keys = set()


def _on_key_press(key):
    """Track pressed keys and trigger dictation on Ctrl+Option+Shift."""
    _pressed_keys.add(key)
    try:
        from pynput.keyboard import Key
        # Ctrl + Option (Alt) + Shift — all three held at once
        has_ctrl  = Key.ctrl  in _pressed_keys or Key.ctrl_l  in _pressed_keys or Key.ctrl_r  in _pressed_keys
        has_alt   = Key.alt   in _pressed_keys or Key.alt_l   in _pressed_keys or Key.alt_r   in _pressed_keys
        has_shift = Key.shift in _pressed_keys or Key.shift_l in _pressed_keys or Key.shift_r in _pressed_keys

        if has_ctrl and has_alt and has_shift:
            # Clear so it doesn't fire repeatedly while held
            _pressed_keys.clear()
            print("🎙️  Ctrl+Option+Shift — activating macOS dictation")
            threading.Thread(target=_dictate_native, daemon=True).start()
    except Exception:
        pass


def _on_key_release(key):
    """Remove released keys from tracker."""
    _pressed_keys.discard(key)

def start_dictation(sio_instance=None):
    """Start the dictation hotkey listener."""
    global _sio
    _sio = sio_instance

    try:
        from pynput import keyboard

        listener = keyboard.Listener(on_press=_on_key_press, on_release=_on_key_release)
        listener.daemon = True
        listener.start()
        print("  🎙️  Dictation service ready — press Ctrl+Option+Shift to activate macOS dictation")
    except ImportError:
        print("  ⚠️  pynput not installed. Dictation hotkey disabled.")
    except Exception as e:
        print(f"  ⚠️  Could not start dictation listener: {e}")
