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
    Find text on screen using OCR and click on it.
    Uses macOS screencapture + Vision framework.

    Args:
        text: Text to find and click on screen
    """
    if not text:
        return "❌ No text specified."

    text_lower = text.lower().strip()

    # Take screenshot
    tmp_path = "/tmp/mark_ghost_screenshot.png"
    subprocess.run(["screencapture", "-x", tmp_path], timeout=5)

    if not os.path.exists(tmp_path):
        return "❌ Could not take screenshot."

    # Use macOS Vision framework via Swift for OCR
    swift_code = f'''
import Foundation
import Vision
import AppKit

let imagePath = "{tmp_path}"
guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {{
    print("ERROR:NO_IMAGE")
    exit(1)
}}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try handler.perform([request])

guard let observations = request.results else {{
    print("ERROR:NO_RESULTS")
    exit(1)
}}

let searchText = "{text_lower}"
let imageWidth = Double(cgImage.width)
let imageHeight = Double(cgImage.height)

for observation in observations {{
    guard let candidate = observation.topCandidates(1).first else {{ continue }}
    let found = candidate.string.lowercased()
    if found.contains(searchText) {{
        let box = observation.boundingBox
        // Vision uses bottom-left origin, convert to top-left
        let centerX = Int((box.origin.x + box.width / 2) * imageWidth)
        let centerY = Int((1.0 - (box.origin.y + box.height / 2)) * imageHeight)
        print("FOUND:\\(centerX),\\(centerY)")
        exit(0)
    }}
}}

print("NOT_FOUND")
'''

    swift_path = "/tmp/mark_ocr.swift"
    with open(swift_path, "w") as f:
        f.write(swift_code)

    try:
        result = subprocess.run(
            ["swift", swift_path],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip()

        if output.startswith("FOUND:"):
            coords = output.split(":")[1]
            cx, cy = coords.split(",")
            cx, cy = int(cx), int(cy)

            # Account for Retina display scaling (2x)
            scale = _get_display_scale()
            cx = int(cx / scale)
            cy = int(cy / scale)

            pyautogui.click(cx, cy)
            return f"🖱️ Found '{text}' and clicked at ({cx}, {cy})"
        elif output == "NOT_FOUND":
            return f"❌ Could not find '{text}' on screen."
        else:
            return f"❌ OCR error: {output}"

    except subprocess.TimeoutExpired:
        return "❌ OCR timed out."
    except Exception as e:
        return f"❌ OCR error: {str(e)}"
    finally:
        # Cleanup
        for f in [tmp_path, swift_path]:
            try:
                os.remove(f)
            except OSError:
                pass


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
