"""
MARK — Code Writer
Generates code from natural language descriptions using local Gemma 2 2B.
Writes the code to a file and opens it for review.
"""

import os
import subprocess
from dotenv import load_dotenv

load_dotenv()


CODE_SYSTEM_PROMPT = """You are an expert programmer. Given a description, write clean, production-ready code.

Rules:
- Output ONLY the code. No markdown fences, no explanations, no preamble.
- Include proper imports, error handling, and comments.
- Make the code complete and runnable as-is.
- Follow best practices for the specified language.
- If no language is specified, default to Python.
"""



def _generate_code(description, language="python"):
    """Call local Gemma model to generate code from a description."""
    try:
        from core.local_llm import local_chat
        response = local_chat(
            messages=[
                {"role": "system", "content": CODE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Language: {language}\n\nDescription: {description}"},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
        if not response:
            return None
        content = response.strip()
        # Strip markdown code fences if included
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            content = "\n".join(lines)
        return content
    except Exception as e:
        print(f"  ✗ Code writer AI error: {e}")
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
    """
    if not description:
        return "❌ Please provide a description of what code to write."

    language = language.lower().strip()
    ext = LANG_EXT.get(language, ".py")

    if not filename:
        words = description.lower().split()[:4]
        safe_name = "_".join(w for w in words if w.isalnum())[:40]
        if not safe_name:
            safe_name = "generated_code"
        filename = safe_name + ext

    if not os.path.splitext(filename)[1]:
        filename += ext

    code = _generate_code(description, language)
    if not code:
        return "❌ Failed to generate code. Please try again."

    filepath = os.path.join(os.path.expanduser("~/Desktop"), filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        return f"❌ Failed to write file: {e}"

    try:
        subprocess.Popen(["open", "-a", "TextEdit", filepath])
    except Exception:
        pass

    line_count = code.count("\n") + 1
    return f"✅ Code generated and saved!\n📄 File: {filepath}\n📝 {line_count} lines of {language}\n📂 Opened in TextEdit for review."
