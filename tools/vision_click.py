"""
MARK — Vision Click (AI-Powered Screen Interaction)
Take a screenshot, use OCR to locate UI elements, then click them.
Note: With a text-only local model, this uses OCR (pytesseract) for element detection
instead of multimodal AI vision.
"""

import os
import re
import json
import time
import base64
import subprocess
import pyautogui
from dotenv import load_dotenv

load_dotenv()

pyautogui.FAILSAFE = True


# ─────────────────────────────────────────────
# SCREENSHOT CAPTURE
# ─────────────────────────────────────────────

def _capture_screen():
    """Capture full screen, return (filepath, width, height) or (None, 0, 0)."""
    path = "/tmp/mark_vision_click.png"
    try:
        subprocess.run(["screencapture", "-x", "-C", path], timeout=5, check=True)
        if not os.path.exists(path):
            return None, 0, 0

        result = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
            capture_output=True, text=True, timeout=5,
        )
        w, h = 0, 0
        for line in result.stdout.split("\n"):
            if "pixelWidth" in line:
                w = int(line.split(":")[-1].strip())
            elif "pixelHeight" in line:
                h = int(line.split(":")[-1].strip())

        return path, w, h
    except Exception as e:
        print(f"  ✗ Screenshot error: {e}")
        return None, 0, 0


def _get_display_scale():
    """Get Retina display scale factor."""
    try:
        result = subprocess.run(
            ["python3", "-c",
             "import Quartz; d = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID()); "
             "print(Quartz.CGDisplayPixelsWide(Quartz.CGMainDisplayID()) / d.size.width)"],
            capture_output=True, text=True, timeout=5,
        )
        return float(result.stdout.strip())
    except Exception:
        return 2.0


# ─────────────────────────────────────────────
# OCR-BASED ELEMENT FINDING
# ─────────────────────────────────────────────

def _find_with_ocr(image_path, instruction, img_w, img_h):
    """Use OCR (pytesseract) to find text on screen and return coordinates."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        # Get bounding box data
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        instruction_lower = instruction.lower()
        # Search for matching text
        best_match = None
        best_score = 0

        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            text_lower = text.strip().lower()

            # Check if any word in instruction matches OCR text
            for word in instruction_lower.split():
                if len(word) >= 3 and word in text_lower:
                    score = len(word) / len(text_lower) if text_lower else 0
                    conf = int(data["conf"][i]) if data["conf"][i] != "-1" else 0
                    weighted = score * (conf / 100.0) if conf > 0 else score * 0.5

                    if weighted > best_score:
                        x = data["left"][i] + data["width"][i] // 2
                        y = data["top"][i] + data["height"][i] // 2
                        best_score = weighted
                        best_match = {"x": x, "y": y, "element": text.strip()}

        return best_match

    except ImportError:
        print("  ✗ pytesseract not installed. Install: brew install tesseract && pip install pytesseract")
        return None
    except Exception as e:
        print(f"  ✗ OCR error: {e}")
        return None


# ─────────────────────────────────────────────
# MAIN TOOLS
# ─────────────────────────────────────────────

def vision_click(instruction=""):
    """
    Find a UI element on screen using OCR and click it.
    """
    if not instruction:
        return "Please describe what to click, e.g., 'the Send button' or 'the search bar'."

    print(f"  👁️ Vision Click: Looking for '{instruction}'...")

    path, img_w, img_h = _capture_screen()
    if not path:
        return "Could not capture screen. Check screen recording permissions."

    result = _find_with_ocr(path, instruction, img_w, img_h)

    try:
        os.remove(path)
    except OSError:
        pass

    if not result:
        return f"Could not find '{instruction}' on screen. Make sure the element is visible. (Note: OCR-based detection works best with visible text labels.)"

    scale = _get_display_scale()
    screen_x = int(result["x"] / scale)
    screen_y = int(result["y"] / scale)

    pyautogui.click(screen_x, screen_y)
    return f"Clicked '{result['element']}' at ({screen_x}, {screen_y}), sir."


def vision_find(instruction=""):
    """
    Find a UI element on screen and return its coordinates WITHOUT clicking.
    """
    if not instruction:
        return "Please describe what to find on screen."

    print(f"  👁️ Vision Find: Looking for '{instruction}'...")

    path, img_w, img_h = _capture_screen()
    if not path:
        return "Could not capture screen."

    result = _find_with_ocr(path, instruction, img_w, img_h)

    try:
        os.remove(path)
    except OSError:
        pass

    if not result:
        return f"Could not find '{instruction}' on screen."

    scale = _get_display_scale()
    screen_x = int(result["x"] / scale)
    screen_y = int(result["y"] / scale)

    return f"Found '{result['element']}' at screen coordinates ({screen_x}, {screen_y})."


def vision_describe():
    """
    Take a screenshot and list visible text elements on screen using OCR.
    """
    print("  👁️ Vision Describe: Analyzing screen layout...")

    path, img_w, img_h = _capture_screen()
    if not path:
        return "Could not capture screen."

    try:
        import pytesseract
        from PIL import Image

        img = Image.open(path)
        text = pytesseract.image_to_string(img)

        try:
            os.remove(path)
        except OSError:
            pass

        if text and text.strip():
            return f"Visible text on screen:\n\n{text[:2000]}"
        return "Could not detect readable text on screen."

    except ImportError:
        try:
            os.remove(path)
        except OSError:
            pass
        return "Vision describe requires pytesseract. Install: brew install tesseract && pip install pytesseract"
    except Exception as e:
        try:
            os.remove(path)
        except OSError:
            pass
        return f"Vision analysis error: {e}"


def vision_type(instruction="", text=""):
    """
    Find a text field on screen using OCR, click it, then type text.
    """
    if not instruction:
        return "Describe which text field to target."
    if not text:
        return "Specify what text to type."

    click_result = vision_click(instruction)
    if "Could not find" in click_result:
        return click_result

    time.sleep(0.3)

    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("command", "v")
    except ImportError:
        pyautogui.write(text, interval=0.02)

    return f"Clicked '{instruction}' and typed: {text[:50]}{'...' if len(text) > 50 else ''}"


def vision_interact(action="", target=""):
    """
    Perform various interactions with screen elements found by OCR.
    """
    if not target:
        return "Describe what to interact with on screen."

    action = (action or "click").lower().strip()

    if action == "find":
        return vision_find(target)

    print(f"  👁️ Vision {action}: '{target}'...")

    path, img_w, img_h = _capture_screen()
    if not path:
        return "Could not capture screen."

    result = _find_with_ocr(path, target, img_w, img_h)

    try:
        os.remove(path)
    except OSError:
        pass

    if not result:
        return f"Could not find '{target}' on screen."

    scale = _get_display_scale()
    x = int(result["x"] / scale)
    y = int(result["y"] / scale)

    if action == "double_click":
        pyautogui.doubleClick(x, y)
        return f"Double-clicked '{result['element']}' at ({x}, {y})."
    elif action == "right_click":
        pyautogui.rightClick(x, y)
        return f"Right-clicked '{result['element']}' at ({x}, {y})."
    elif action == "hover":
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Hovering over '{result['element']}' at ({x}, {y})."
    else:
        pyautogui.click(x, y)
        return f"Clicked '{result['element']}' at ({x}, {y})."
