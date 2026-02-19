"""
MARK — Contextual Awareness Engine
Detects the active application, window title, browser URL, and current file.
Uses macOS AppleScript for real-time system state queries.
"""

import subprocess
import json


def _applescript(script):
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip()
    except Exception:
        return ""


def get_context():
    """Get full contextual awareness: active app, window, URL, file info."""
    info = {}

    # Active application
    app = _applescript(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )
    info["app"] = app or "Unknown"

    # Active window title
    title = _applescript(
        'tell application "System Events" to get name of front window of (first application process whose frontmost is true)'
    )
    info["window"] = title or "No window"

    # Browser URL (Safari or Chrome)
    if "Safari" in app:
        url = _applescript('tell application "Safari" to get URL of front document')
        page = _applescript('tell application "Safari" to get name of front document')
        info["url"] = url or ""
        info["page_title"] = page or ""
    elif "Chrome" in app or "Google Chrome" in app:
        url = _applescript(
            'tell application "Google Chrome" to get URL of active tab of front window'
        )
        page = _applescript(
            'tell application "Google Chrome" to get title of active tab of front window'
        )
        info["url"] = url or ""
        info["page_title"] = page or ""
    elif "Arc" in app:
        url = _applescript(
            'tell application "Arc" to get URL of active tab of front window'
        )
        info["url"] = url or ""
    elif "Firefox" in app:
        info["url"] = "(Firefox URL requires accessibility)"

    # File path for editors
    if "Code" in app or "VS Code" in app:
        info["editor"] = "VS Code"
        info["hint"] = "Window title usually shows the open file"
    elif "Xcode" in app:
        info["editor"] = "Xcode"
    elif "Sublime" in app:
        info["editor"] = "Sublime Text"
    elif "Terminal" in app or "iTerm" in app:
        info["editor"] = "Terminal"
        cwd = _applescript(
            'tell application "System Events" to get name of front window of application process "{}"'.format(app)
        )
        info["terminal_title"] = cwd or ""

    # Build response
    lines = ["🔍 Current Context",
             "━" * 30,
             "App      : {}".format(info.get("app", "Unknown")),
             "Window   : {}".format(info.get("window", "—"))]
    if info.get("url"):
        lines.append("URL      : {}".format(info["url"]))
    if info.get("page_title"):
        lines.append("Page     : {}".format(info["page_title"]))
    if info.get("editor"):
        lines.append("Editor   : {}".format(info["editor"]))
    if info.get("terminal_title"):
        lines.append("Terminal : {}".format(info["terminal_title"]))
    lines.append("━" * 30)

    return "\n".join(lines)
