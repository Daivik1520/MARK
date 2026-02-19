"""
MARK — Code Runner
Executes Python, JavaScript, and shell code snippets safely.
Uses subprocess with timeout and output capture.
"""

import subprocess
import tempfile
import os
import shutil


MAX_OUTPUT = 3000
TIMEOUT = 15


def run_code(code="", language="python"):
    """Execute code and return the output. Supports python, javascript, shell."""
    if not code or not code.strip():
        return "No code provided. Send the code you want to run."

    lang = language.lower().strip()

    # Normalize language aliases
    aliases = {
        "py": "python", "python3": "python", "python2": "python",
        "js": "javascript", "node": "javascript", "nodejs": "javascript",
        "sh": "shell", "bash": "shell", "zsh": "shell", "terminal": "shell",
        "cmd": "shell", "command": "shell",
    }
    lang = aliases.get(lang, lang)

    if lang == "python":
        return _run_python(code)
    elif lang == "javascript":
        return _run_javascript(code)
    elif lang == "shell":
        return _run_shell(code)
    else:
        return "Unsupported language: {}. Supported: python, javascript, shell".format(language)


def _run_python(code):
    """Run Python code."""
    tmpdir = tempfile.mkdtemp(prefix="mark_py_")
    fpath = os.path.join(tmpdir, "script.py")
    try:
        with open(fpath, "w") as f:
            f.write(code)
        result = subprocess.run(
            ["python3", fpath],
            capture_output=True, text=True,
            timeout=TIMEOUT, cwd=tmpdir
        )
        return _format_result(result, "Python")
    except subprocess.TimeoutExpired:
        return "⏱️ Python: Timed out after {}s".format(TIMEOUT)
    except Exception as e:
        return "❌ Python error: {}".format(e)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_javascript(code):
    """Run JavaScript code with Node.js."""
    # Check if node is available
    if not shutil.which("node"):
        return "❌ Node.js is not installed. Install it to run JavaScript."
    tmpdir = tempfile.mkdtemp(prefix="mark_js_")
    fpath = os.path.join(tmpdir, "script.js")
    try:
        with open(fpath, "w") as f:
            f.write(code)
        result = subprocess.run(
            ["node", fpath],
            capture_output=True, text=True,
            timeout=TIMEOUT, cwd=tmpdir
        )
        return _format_result(result, "JavaScript")
    except subprocess.TimeoutExpired:
        return "⏱️ JavaScript: Timed out after {}s".format(TIMEOUT)
    except Exception as e:
        return "❌ JavaScript error: {}".format(e)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_shell(code):
    """Run shell commands."""
    try:
        result = subprocess.run(
            ["zsh", "-c", code],
            capture_output=True, text=True,
            timeout=TIMEOUT
        )
        return _format_result(result, "Shell")
    except subprocess.TimeoutExpired:
        return "⏱️ Shell: Timed out after {}s".format(TIMEOUT)
    except Exception as e:
        return "❌ Shell error: {}".format(e)


def _format_result(result, lang):
    """Format subprocess result into a readable output."""
    lines = ["▶️ {} Execution Result".format(lang), "━" * 30]

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if stdout:
        if len(stdout) > MAX_OUTPUT:
            stdout = stdout[:MAX_OUTPUT] + "\n… (output truncated)"
        lines.append(stdout)

    if stderr:
        if len(stderr) > MAX_OUTPUT:
            stderr = stderr[:MAX_OUTPUT] + "\n… (error truncated)"
        lines.append("\n⚠️ Stderr:\n{}".format(stderr))

    if result.returncode != 0:
        lines.append("\n❌ Exit code: {}".format(result.returncode))
    elif not stdout and not stderr:
        lines.append("✅ Completed (no output)")
    else:
        lines.append("\n✅ Exit code: 0")

    return "\n".join(lines)
