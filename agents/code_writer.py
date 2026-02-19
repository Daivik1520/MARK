"""
MARK — Code Writer
Generates code from natural language descriptions using the AI model.
Writes the code to a file and opens it for review.
"""

import os
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Models to try (same as ai_engine.py)
MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-4-maverick:free",
]

CODE_SYSTEM_PROMPT = """You are an expert programmer. Given a description, write clean, production-ready code.

Rules:
- Output ONLY the code. No markdown fences, no explanations, no preamble.
- Include proper imports, error handling, and comments.
- Make the code complete and runnable as-is.
- Follow best practices for the specified language.
- If no language is specified, default to Python.
"""


def _generate_code(description, language="python"):
    """Call OpenRouter to generate code from a description."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": CODE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Language: {language}\n\nDescription: {description}"},
    ]

    for model in MODELS:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "max_tokens": 4096, "temperature": 0.3},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content:
                    # Strip markdown code fences if the model included them
                    if content.startswith("```"):
                        lines = content.split("\n")
                        # Remove first line (```python) and last line (```)
                        if lines[-1].strip() == "```":
                            lines = lines[1:-1]
                        else:
                            lines = lines[1:]
                        content = "\n".join(lines)
                    return content
            elif resp.status_code in (402, 404):
                continue  # Try next model
            elif resp.status_code == 429:
                import time
                time.sleep(2)
                continue
        except Exception:
            continue

    return None


# Language → file extension mapping
LANG_EXT = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "java": ".java",
    "cpp": ".cpp",
    "c": ".c",
    "go": ".go",
    "rust": ".rs",
    "ruby": ".rb",
    "swift": ".swift",
    "kotlin": ".kt",
    "html": ".html",
    "css": ".css",
    "sql": ".sql",
    "shell": ".sh",
    "bash": ".sh",
    "php": ".php",
    "r": ".r",
}


def write_code(description, language="python", filename=""):
    """
    Generate code from a natural language description, save to Desktop, and open it.
    
    Args:
        description: What the code should do
        language: Programming language (default: python)
        filename: Optional filename (auto-generated if empty)
    
    Returns:
        Confirmation message with file path
    """
    if not description:
        return "❌ Please provide a description of what code to write."

    language = language.lower().strip()
    ext = LANG_EXT.get(language, ".py")

    # Generate filename if not provided
    if not filename:
        # Create a clean filename from the description
        words = description.lower().split()[:4]
        safe_name = "_".join(w for w in words if w.isalnum())[:40]
        if not safe_name:
            safe_name = "generated_code"
        filename = safe_name + ext

    # Ensure correct extension
    if not os.path.splitext(filename)[1]:
        filename += ext

    # Generate the code
    code = _generate_code(description, language)
    if not code:
        return "❌ Failed to generate code. Please try again."

    # Write to Desktop
    filepath = os.path.join(os.path.expanduser("~/Desktop"), filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        return f"❌ Failed to write file: {e}"

    # Open in TextEdit
    try:
        subprocess.Popen(["open", "-a", "TextEdit", filepath])
    except Exception:
        pass

    line_count = code.count("\n") + 1
    return f"✅ Code generated and saved!\n📄 File: {filepath}\n📝 {line_count} lines of {language}\n📂 Opened in TextEdit for review."
