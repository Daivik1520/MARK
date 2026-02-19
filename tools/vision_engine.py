"""
MARK — Vision Engine (Screen Sense)
Captures screenshots and analyzes them using OpenRouter vision models.
Enables MARK to "see" what's on the user's screen.
"""

import os
import base64
import time
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Vision-capable models (ordered by preference)
VISION_MODELS = [
    "google/gemini-2.0-flash-001",
    "google/gemini-flash-1.5",
    "meta-llama/llama-4-maverick:free",
]

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
        import subprocess
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


def _encode_image(filepath: str) -> str:
    """Read an image file and return base64-encoded string."""
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_screen(query: str = "Describe what you see on the screen") -> str:
    """
    Take a screenshot and analyze it using a vision model.
    The query allows the user to ask specific questions about the screen content.
    """
    print(f"  👁️ Vision: Capturing screenshot...")
    screenshot_path = capture_screenshot()

    if not screenshot_path or not os.path.exists(screenshot_path):
        return "I wasn't able to capture the screen, sir. Please check screen recording permissions in System Settings > Privacy & Security."

    print(f"  👁️ Vision: Analyzing with AI...")
    image_b64 = _encode_image(screenshot_path)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "MARK AI Vision"
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are MARK's vision system. You analyze screenshots from a macOS computer. "
                "Be concise, accurate, and helpful. Identify applications, text, errors, code, "
                "websites, images, or anything visible. When describing errors or code, provide "
                "actionable suggestions. Respond naturally as if you're the user's AI assistant "
                "who can see their screen. Address the user as 'sir'."
            )
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": query
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}"
                    }
                }
            ]
        }
    ]

    for model in VISION_MODELS:
        try:
            print(f"  👁️ Trying vision model: {model}")
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.5
            }

            resp = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        print(f"  ✓ Vision analysis complete with {model}")
                        # Clean up screenshot after analysis
                        try:
                            os.remove(screenshot_path)
                        except OSError:
                            pass
                        return content

            elif resp.status_code in (402, 404, 400):
                print(f"  ✗ Vision: {resp.status_code} on {model}, trying next...")
                continue

            elif resp.status_code == 429:
                print(f"  ⏳ Vision: Rate limited on {model}, waiting...")
                time.sleep(3)
                continue

            else:
                print(f"  ✗ Vision: {resp.status_code} on {model}")
                continue

        except requests.exceptions.Timeout:
            print(f"  ✗ Vision: Timeout on {model}")
            continue
        except Exception as e:
            print(f"  ✗ Vision error on {model}: {e}")
            continue

    return "I couldn't analyze the screen right now, sir. Vision models may be temporarily unavailable."
