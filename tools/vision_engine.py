"""
MARK — Vision Engine (Screen Sense)

Thin tool-facing wrapper over core.screen_sense, which does the real work:
accessibility tree, Apple's native OCR, and the multimodal model.
"""

from core import screen_sense


def capture_screenshot():
    """Capture the screen. Returns a file path, or '' on failure."""
    return screen_sense.capture() or ""


def analyze_screen(query="Describe what you see on the screen"):
    """
    Look at the screen and answer a question about it.

    Reports a permission failure with actionable wording, because a silent
    empty answer is indistinguishable from the model being unable to help.
    """
    print("  👁️  Vision: reading the screen...")
    return screen_sense.describe_screen(query)


def read_screen_text():
    """Return all text currently visible on screen."""
    text = screen_sense.ocr_text()
    if text:
        return text
    if not screen_sense.capture_available():
        return screen_sense.PERMISSION_HINT
    return "I couldn't find any readable text on screen, sir."
