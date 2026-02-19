"""
MARK — Smart Clipboard Manager
Background tracking of clipboard history with search/recall.
Uses macOS pbpaste to poll clipboard every 2 seconds.
"""

import subprocess
import threading
import time
import json
import os
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "clipboard_history.json")
MAX_ENTRIES = 200

_history = []
_last_content = ""
_running = False
_lock = threading.Lock()


def _load():
    global _history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                _history = json.load(f)
        except Exception:
            _history = []


def _save():
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(_history[-MAX_ENTRIES:], f, indent=2)
    except Exception:
        pass


def _poll():
    global _last_content, _running
    while _running:
        try:
            result = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=2
            )
            content = result.stdout.strip()
            if content and content != _last_content:
                _last_content = content
                entry = {
                    "content": content[:2000],
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "url" if content.startswith(("http://", "https://")) else "text",
                }
                with _lock:
                    _history.append(entry)
                    if len(_history) > MAX_ENTRIES:
                        _history[:] = _history[-MAX_ENTRIES:]
                    _save()
        except Exception:
            pass
        time.sleep(2)


def start_clipboard_monitor():
    global _running
    if _running:
        return
    _load()
    _running = True
    t = threading.Thread(target=_poll, daemon=True)
    t.start()
    print("  ✓ Clipboard monitor started")


def get_clipboard_history(count="10"):
    """Return the last N clipboard entries."""
    n = int(count) if str(count).isdigit() else 10
    n = min(n, 50)
    with _lock:
        items = list(reversed(_history[-n:]))
    if not items:
        return "No clipboard history yet. Copy something first!"
    lines = ["📋 Clipboard History (last {})".format(len(items)),
             "━" * 35]
    for i, e in enumerate(items, 1):
        preview = e["content"][:80].replace("\n", " ")
        if len(e["content"]) > 80:
            preview += "…"
        lines.append("{}. [{}] {}".format(i, e["time"][11:16], preview))
    return "\n".join(lines)


def search_clipboard(query=""):
    """Search clipboard history by keyword."""
    if not query:
        return "Please provide a search keyword."
    q = query.lower()
    with _lock:
        matches = [e for e in reversed(_history) if q in e["content"].lower()]
    if not matches:
        return "No clipboard entries matching '{}'.".format(query)
    lines = ["📋 Clipboard search: '{}' ({} results)".format(query, len(matches[:10])),
             "━" * 35]
    for i, e in enumerate(matches[:10], 1):
        preview = e["content"][:100].replace("\n", " ")
        lines.append("{}. [{}] {}".format(i, e["time"][11:16], preview))
    return "\n".join(lines)


def paste_from_history(index="1"):
    """Copy a specific item from history back to clipboard."""
    n = int(index) if str(index).isdigit() else 1
    with _lock:
        items = list(reversed(_history))
    if n < 1 or n > len(items):
        return "Invalid index. Use show_clipboard to see available entries."
    item = items[n - 1]
    try:
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(item["content"].encode("utf-8"))
        return "✅ Copied to clipboard: {}".format(item["content"][:80])
    except Exception as e:
        return "Failed to copy: {}".format(e)
