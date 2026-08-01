"""
MARK — Ghost Cursor (Precision OS Control)
Full programmatic mouse/keyboard control via PyAutoGUI.
Includes OCR-based text clicking using macOS Vision framework.
"""

import os
import subprocess
import time
import pyautogui

# Safety: enable fail-safe (move mouse to corner to abort)
pyautogui.FAILSAFE = True
# Speed: minimal pause between actions
pyautogui.PAUSE = 0.05


def get_screen_size():
    """Get the current screen dimensions."""
    w, h = pyautogui.size()
    return f"Screen size: {w}×{h} pixels"


def move_mouse(x, y):
    """
    Move the mouse to absolute pixel coordinates.

    Args:
        x: X coordinate (pixels from left)
        y: Y coordinate (pixels from top)
    """
    try:
        x, y = int(x), int(y)
    except (ValueError, TypeError):
        return "❌ Invalid coordinates. Use numbers like: move_mouse 500 300"

    w, h = pyautogui.size()
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))

    pyautogui.moveTo(x, y, duration=0.15)
    return f"🖱️ Mouse moved to ({x}, {y})"


def click_at(x, y, button="left"):
    """
    Click at specific pixel coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
        button: "left", "right", or "double"
    """
    try:
        x, y = int(x), int(y)
    except (ValueError, TypeError):
        return "❌ Invalid coordinates."

    w, h = pyautogui.size()
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))

    if button == "double":
        pyautogui.doubleClick(x, y)
        return f"🖱️ Double-clicked at ({x}, {y})"
    elif button == "right":
        pyautogui.rightClick(x, y)
        return f"🖱️ Right-clicked at ({x}, {y})"
    else:
        pyautogui.click(x, y)
        return f"🖱️ Clicked at ({x}, {y})"


def scroll_screen(direction="down", amount="3"):
    """
    Scroll the screen.

    Args:
        direction: "up", "down", "left", "right"
        amount: Number of scroll steps (1-20)
    """
    try:
        amount = int(amount)
    except (ValueError, TypeError):
        amount = 3
    amount = max(1, min(amount, 20))

    if direction.lower() == "up":
        pyautogui.scroll(amount)
        return f"📜 Scrolled up {amount} steps"
    elif direction.lower() == "down":
        pyautogui.scroll(-amount)
        return f"📜 Scrolled down {amount} steps"
    elif direction.lower() == "left":
        pyautogui.hscroll(-amount)
        return f"📜 Scrolled left {amount} steps"
    elif direction.lower() == "right":
        pyautogui.hscroll(amount)
        return f"📜 Scrolled right {amount} steps"
    else:
        return f"❌ Unknown direction: {direction}. Use up/down/left/right."


def type_text(text):
    """
    Type text at the current cursor position.

    Args:
        text: Text to type
    """
    if not text:
        return "❌ No text to type."

    # Use pyperclip for non-ASCII characters
    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("command", "v")
        return f"⌨️ Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
    except ImportError:
        # Fall back to pyautogui.write (ASCII only)
        pyautogui.write(text, interval=0.02)
        return f"⌨️ Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


def drag_to(start_x, start_y, end_x, end_y):
    """
    Click and drag from one position to another.

    Args:
        start_x, start_y: Starting coordinates
        end_x, end_y: Ending coordinates
    """
    try:
        sx, sy = int(start_x), int(start_y)
        ex, ey = int(end_x), int(end_y)
    except (ValueError, TypeError):
        return "❌ Invalid coordinates."

    pyautogui.moveTo(sx, sy, duration=0.1)
    pyautogui.drag(ex - sx, ey - sy, duration=0.3)
    return f"🖱️ Dragged from ({sx},{sy}) to ({ex},{ey})"


def click_text(text):
    """
    Find text on screen and click it.

    Delegates to core.screen_sense, which uses the accessibility tree first and
    Apple's Vision OCR second. The previous implementation compiled a Swift
    program at call time, which meant every click depended on the Xcode
    toolchain being installed and on a ~1s compile.
    """
    if not text:
        return "Tell me what to click, sir."

    from core import screen_sense

    elements = screen_sense.element_map()
    if not elements:
        if not screen_sense.capture_available():
            return screen_sense.PERMISSION_HINT
        return "I couldn't read anything on screen, sir."

    element = screen_sense.find_element(text, elements)
    if not element:
        visible = ", ".join(e["label"] for e in elements[:8])
        return f"I couldn't find '{text}' on screen, sir. What I can see: {visible}"

    pyautogui.click(element["x"], element["y"])
    return f"Clicked '{element['label']}', sir."



def _get_display_scale():
    """Get Retina display scale factor."""
    try:
        result = subprocess.run(
            ["python3", "-c", "import Quartz; d = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID()); print(Quartz.CGDisplayPixelsWide(Quartz.CGMainDisplayID()) / d.size.width)"],
            capture_output=True, text=True, timeout=5,
        )
        return float(result.stdout.strip())
    except Exception:
        return 2.0  # Default Retina
