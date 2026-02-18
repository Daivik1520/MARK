"""
MARK — Gesture Controller
Executes macOS system actions triggered by hand gestures.
"""
import subprocess

try:
    from Quartz import (
        CGEventCreateScrollWheelEvent, kCGScrollEventUnitLine,
        CGEventPost, kCGHIDEventTap
    )
    _HAS_QUARTZ = True
except ImportError:
    _HAS_QUARTZ = False


def _applescript(script):
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception as e:
        print(f"  ✗ Gesture error: {e}")


def execute_gesture(gesture_type):
    if gesture_type == "swipe_left":
        _applescript('tell application "System Events" to key code 124 using {control down}')
        return "next space"
    elif gesture_type == "swipe_right":
        _applescript('tell application "System Events" to key code 123 using {control down}')
        return "previous space"
    elif gesture_type == "swipe_up":
        _scroll("down")
        return "scrolled down"
    elif gesture_type == "swipe_down":
        _scroll("up")
        return "scrolled up"
    return "unknown"


def _scroll(direction):
    if _HAS_QUARTZ:
        amount = -5 if direction == "down" else 5
        ev = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, amount)
        if ev:
            CGEventPost(kCGHIDEventTap, ev)
    else:
        key = 121 if direction == "down" else 116
        _applescript(f'tell application "System Events" to key code {key}')
