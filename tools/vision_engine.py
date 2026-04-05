"""
MARK — Vision Engine (Screen Sense)
Captures screenshots and analyzes them.
Note: Vision analysis requires a multimodal model. With Gemma 2 2B (text-only),
vision features are limited to OCR-based analysis via pytesseract if available.
"""

import os
import base64
import time
import subprocess
from dotenv import load_dotenv

load_dotenv()

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")


def _ensure_screenshot_dir():
    """Create screenshots directory if it doesn't exist."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def capture_screenshot() -> str:
    """
    Capture a screenshot using macOS screencapture.
    Returns the file path to the saved screenshot.
    """
    _ensure_screenshot_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.png")

    try:
        result = subprocess.run(
            ["screencapture", "-x", "-C", filepath],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return ""
        return filepath
    except Exception as e:
        print(f"Screenshot error: {e}")
        return ""


def analyze_screen(query: str = "Describe what you see on the screen") -> str:
    """
    Take a screenshot and analyze it.
    Uses OCR (pytesseract) to extract text, then local Gemma to interpret.
    """
    print(f"  👁️ Vision: Capturing screenshot...")
    screenshot_path = capture_screenshot()

    if not screenshot_path or not os.path.exists(screenshot_path):
        return "I wasn't able to capture the screen, sir. Please check screen recording permissions in System Settings > Privacy & Security."

    print(f"  👁️ Vision: Analyzing screen content...")

    try:
        # Try OCR-based analysis
        extracted_text = ""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(screenshot_path)
            extracted_text = pytesseract.image_to_string(img)
        except ImportError:
            # pytesseract not available, try basic approach
            extracted_text = "[OCR not available - pytesseract not installed]"
        except Exception as e:
            extracted_text = f"[OCR failed: {e}]"

        if extracted_text and len(extracted_text.strip()) > 20:
            # Use local LLM to interpret the extracted text
            from core.local_llm import local_chat

            prompt = (
                f"The user asked: {query}\n\n"
                f"Here is the text extracted from their screen via OCR:\n"
                f"---\n{extracted_text[:3000]}\n---\n\n"
                f"Based on this text, answer the user's question. Be concise and helpful. "
                f"Address the user as 'sir'."
            )

            response = local_chat(
                messages=[
                    {"role": "system", "content": "You are MARK's vision system. You analyze text extracted from screenshots. Be concise, accurate, and helpful."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=512,
                temperature=0.5,
            )

            # Clean up screenshot
            try:
                os.remove(screenshot_path)
            except OSError:
                pass

            if response:
                return response
            return f"I captured the screen but couldn't analyze it well, sir. Here's the raw text I could read:\n{extracted_text[:500]}"
        else:
            # Clean up
            try:
                os.remove(screenshot_path)
            except OSError:
                pass
            return "I captured the screen but couldn't extract readable text, sir. Vision features require a multimodal model. Consider installing pytesseract for OCR: brew install tesseract && pip install pytesseract"

    except Exception as e:
        print(f"  ✗ Vision error: {e}")
        try:
            if screenshot_path and os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except OSError:
            pass
        return f"Vision analysis failed, sir. Error: {str(e)}"
