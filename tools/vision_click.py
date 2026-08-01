"""
MARK — Vision Click (screen interaction)

Finds a UI element and acts on it. Element location comes from
core.screen_sense, which prefers the accessibility tree (exact frames reported
by the app itself) and falls back to Apple's native OCR.

The model never produces coordinates. It picks from a numbered list of elements
we located ourselves, so a wrong answer means clicking the wrong button rather
than clicking an arbitrary point on screen.
"""

import time
import pyautogui

from core import screen_sense

pyautogui.FAILSAFE = True


def _locate(instruction):
    """Resolve an instruction to an element. Returns (element, error_message)."""
    if not instruction or not instruction.strip():
        return None, "Tell me what to look for, sir — for example 'the Send button'."

    elements = screen_sense.element_map()
    if not elements:
        if not screen_sense.capture_available():
            return None, screen_sense.PERMISSION_HINT
        if not screen_sense.ax_available():
            return None, screen_sense.AX_PERMISSION_HINT
        return None, "I can't make out any interface elements on screen right now, sir."

    element = screen_sense.find_element(instruction, elements)
    if not element:
        visible = ", ".join(e["label"] for e in elements[:8])
        return None, (f"I couldn't find '{instruction}' on screen, sir. "
                      f"What I can see: {visible}")
    return element, None


def vision_click(instruction=""):
    """Find a UI element and click it."""
    print(f"  👁️  Looking for '{instruction}'...")
    element, error = _locate(instruction)
    if error:
        return error

    pyautogui.click(element["x"], element["y"])
    return f"Clicked '{element['label']}', sir."


def vision_find(instruction=""):
    """Locate a UI element without clicking it."""
    element, error = _locate(instruction)
    if error:
        return error
    return (f"'{element['label']}' is at ({element['x']}, {element['y']}) — "
            f"a {element.get('role', 'text element')}.")


def vision_describe():
    """List every interactive element currently on screen."""
    elements = screen_sense.element_map()
    if not elements:
        if not screen_sense.capture_available():
            return screen_sense.PERMISSION_HINT
        return "I can't make out any interface elements on screen right now, sir."

    lines = ["Elements on screen:"]
    for element in elements[:45]:
        role = element.get("role", "text")
        lines.append(f"  [{element['index']}] {role}: {element['label']} "
                     f"({element['x']}, {element['y']})")
    if len(elements) > 45:
        lines.append(f"  ... and {len(elements) - 45} more")
    return "\n".join(lines)


def vision_type(instruction="", text=""):
    """Click a text field, then type into it."""
    if not text:
        return "What should I type, sir?"

    element, error = _locate(instruction)
    if error:
        return error

    pyautogui.click(element["x"], element["y"])
    time.sleep(0.25)

    # Paste rather than keystroke — faster, and safe with non-ASCII text.
    try:
        import pyperclip
        previous = ""
        try:
            previous = pyperclip.paste()
        except Exception:
            pass
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("command", "v")
        time.sleep(0.15)
        if previous:
            try:
                pyperclip.copy(previous)
            except Exception:
                pass
    except ImportError:
        pyautogui.write(text, interval=0.02)

    preview = text[:50] + ("..." if len(text) > 50 else "")
    return f"Typed into '{element['label']}': {preview}"


def vision_interact(action="", target=""):
    """Click, double-click, right-click, hover over, or locate an element."""
    action = (action or "click").lower().strip()

    if action == "find":
        return vision_find(target)

    element, error = _locate(target)
    if error:
        return error

    x, y = element["x"], element["y"]
    label = element["label"]

    if action == "double_click":
        pyautogui.doubleClick(x, y)
        return f"Double-clicked '{label}', sir."
    if action == "right_click":
        pyautogui.rightClick(x, y)
        return f"Right-clicked '{label}', sir."
    if action == "hover":
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Hovering over '{label}', sir."

    pyautogui.click(x, y)
    return f"Clicked '{label}', sir."
