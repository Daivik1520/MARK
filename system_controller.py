"""
MARK — System Controller
All macOS system control via osascript (AppleScript) and subprocess.
"""

import subprocess
import os
import time
import json
import datetime
import requests as req
from dotenv import load_dotenv

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


def _run_applescript(script: str) -> str:
    """Execute an AppleScript and return the output."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"


def _run_shell(cmd: str) -> str:
    """Execute a shell command and return the output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        return f"Error: {str(e)}"


# ─────────────────────────────────────────────
# APP LAUNCHING
# ─────────────────────────────────────────────

def open_app(app_name: str) -> str:
    """Open an application using Spotlight search via AppleScript."""
    script = f'''
    tell application "System Events"
        key code 49 using command down
        delay 0.5
        keystroke "{app_name}"
        delay 1.0
        key code 36
    end tell
    '''
    result = _run_applescript(script)
    if "Error" not in result:
        return f"Opening {app_name} now, sir."
    return f"I encountered an issue opening {app_name}: {result}"


# ─────────────────────────────────────────────
# WEBSITE OPENING
# ─────────────────────────────────────────────

def open_website(url: str) -> str:
    """Open a website in the default browser."""
    if not url.startswith("http"):
        url = "https://" + url
    script = f'open location "{url}"'
    result = _run_applescript(script)
    if "Error" not in result:
        return f"Opening {url} in your browser, sir."
    return f"Failed to open website: {result}"


# ─────────────────────────────────────────────
# WHATSAPP MESSAGING
# ─────────────────────────────────────────────

def send_whatsapp(contact: str, message: str) -> str:
    """Open WhatsApp, search for a contact, and send a message."""
    script = f'''
    tell application "System Events"
        key code 49 using command down
        delay 0.5
        keystroke "WhatsApp"
        delay 1.5
        key code 36
        delay 2.0
    end tell

    delay 1.0

    tell application "System Events"
        tell process "WhatsApp"
            set frontmost to true
            delay 0.5
            -- Open search
            keystroke "f" using command down
            delay 0.5
            keystroke "{contact}"
            delay 1.5
            key code 36
            delay 1.0
            keystroke "{message}"
            delay 0.3
            key code 36
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if "Error" not in result:
        return f"Message sent to {contact} on WhatsApp, sir."
    return f"Could not send WhatsApp message: {result}"


# ─────────────────────────────────────────────
# FILE & FOLDER OPERATIONS
# ─────────────────────────────────────────────

def open_file(file_path: str) -> str:
    """Open a file with its default application."""
    expanded = os.path.expanduser(file_path)
    if not os.path.exists(expanded):
        return f"File not found: {file_path}"
    result = _run_shell(f'open "{expanded}"')
    if not result or "Error" not in result:
        return f"Opening {os.path.basename(file_path)}, sir."
    return f"Could not open file: {result}"


def open_folder(folder_path: str) -> str:
    """Open a folder in Finder."""
    expanded = os.path.expanduser(folder_path)
    if not os.path.exists(expanded):
        return f"Folder not found: {folder_path}"
    result = _run_shell(f'open "{expanded}"')
    if not result or "Error" not in result:
        return f"Opening folder {os.path.basename(folder_path)} in Finder, sir."
    return f"Could not open folder: {result}"


def create_file(file_path: str, content: str = "") -> str:
    """Create a new file with optional content."""
    expanded = os.path.expanduser(file_path)
    parent = os.path.dirname(expanded)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    try:
        with open(expanded, "w") as f:
            f.write(content)
        return f"File created at {file_path}, sir."
    except Exception as e:
        return f"Could not create file: {str(e)}"


def create_folder(folder_path: str) -> str:
    """Create a new folder."""
    expanded = os.path.expanduser(folder_path)
    try:
        os.makedirs(expanded, exist_ok=True)
        return f"Folder created at {folder_path}, sir."
    except Exception as e:
        return f"Could not create folder: {str(e)}"


# ─────────────────────────────────────────────
# NOTES / NOTEPAD
# ─────────────────────────────────────────────

def take_notes(text: str) -> str:
    """Open TextEdit and write notes."""
    escaped = text.replace('"', '\\"').replace("'", "'\\''")
    script = f'''
    tell application "TextEdit"
        activate
        make new document
        delay 0.5
        set text of front document to "{escaped}"
    end tell
    '''
    result = _run_applescript(script)
    if "Error" not in result:
        return "Notes written in TextEdit, sir."
    return f"Could not write notes: {result}"


# ─────────────────────────────────────────────
# WINDOW MANAGEMENT
# ─────────────────────────────────────────────

def list_windows() -> str:
    """List all open application windows."""
    script = '''
    set windowList to ""
    tell application "System Events"
        set appList to name of every application process whose visible is true
        repeat with appName in appList
            set windowList to windowList & appName & "\\n"
        end repeat
    end tell
    return windowList
    '''
    result = _run_applescript(script)
    if result and "Error" not in result:
        apps = [a.strip() for a in result.split("\n") if a.strip()]
        formatted = ", ".join(apps)
        return f"Currently open windows: {formatted}"
    return "Could not retrieve window list."


def focus_window(app_name: str) -> str:
    """Bring a specific application window to the front."""
    script = f'''
    tell application "{app_name}"
        activate
    end tell
    '''
    result = _run_applescript(script)
    if "Error" not in result:
        return f"Brought {app_name} to the front, sir."
    return f"Could not focus {app_name}: {result}"


# ─────────────────────────────────────────────
# SYSTEM POWER CONTROLS
# ─────────────────────────────────────────────

def system_shutdown() -> str:
    """Shut down the system."""
    script = 'tell application "System Events" to shut down'
    _run_applescript(script)
    return "Shutting down the system, sir. Goodbye."


def system_sleep() -> str:
    """Put the system to sleep."""
    script = 'tell application "System Events" to sleep'
    _run_applescript(script)
    return "Putting the system to sleep, sir."


def system_restart() -> str:
    """Restart the system."""
    script = 'tell application "System Events" to restart'
    _run_applescript(script)
    return "Restarting the system, sir."


# ─────────────────────────────────────────────
# SCREENSHOT
# ─────────────────────────────────────────────

def take_screenshot() -> str:
    """Take a screenshot and save it to the Desktop."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    path = os.path.expanduser(f"~/Desktop/{filename}")
    result = _run_shell(f'screencapture -x "{path}"')
    if os.path.exists(path):
        return f"Screenshot saved to Desktop as {filename}, sir."
    return f"Could not take screenshot: {result}"


# ─────────────────────────────────────────────
# MUSIC
# ─────────────────────────────────────────────

def play_music(query: str, platform: str = "youtube") -> str:
    """Play music on Spotify or YouTube."""
    if platform.lower() == "spotify":
        script = f'''
        tell application "System Events"
            key code 49 using command down
            delay 0.5
            keystroke "Spotify"
            delay 1.5
            key code 36
            delay 2.0
        end tell

        delay 1.5

        tell application "Spotify"
            activate
        end tell

        delay 1.0

        tell application "System Events"
            tell process "Spotify"
                set frontmost to true
                delay 0.3
                keystroke "l" using command down
                delay 0.5
                keystroke "{query}"
                delay 1.0
                key code 36
                delay 1.5
                key code 36
            end tell
        end tell
        '''
        result = _run_applescript(script)
        if "Error" not in result:
            return f"Playing {query} on Spotify, sir."
        return f"Could not play on Spotify: {result}"
    else:
        import urllib.parse
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        script = f'open location "{search_url}"'
        result = _run_applescript(script)
        if "Error" not in result:
            return f"Searching for {query} on YouTube, sir."
        return f"Could not open YouTube: {result}"


# ─────────────────────────────────────────────
# SEARCH FILES
# ─────────────────────────────────────────────

def search_files(query: str, directory: str = "~") -> str:
    """Search for files matching a query."""
    expanded = os.path.expanduser(directory)
    result = _run_shell(f'find "{expanded}" -maxdepth 4 -iname "*{query}*" 2>/dev/null | head -10')
    if result:
        files = result.split("\n")
        return f"Found {len(files)} matching files:\n" + "\n".join(files)
    return f"No files found matching '{query}'."


# ─────────────────────────────────────────────
# VOLUME CONTROL
# ─────────────────────────────────────────────

def set_volume(level: int) -> str:
    """Set system volume (0-100)."""
    level = max(0, min(100, level))
    mac_vol = int(level * 7 / 100)  # macOS volume is 0-7
    script = f'set volume output volume {level}'
    _run_applescript(script)
    return f"Volume set to {level}%, sir."


def mute_volume() -> str:
    """Mute system volume."""
    _run_applescript('set volume output muted true')
    return "System muted, sir."


def unmute_volume() -> str:
    """Unmute system volume."""
    _run_applescript('set volume output muted false')
    return "System unmuted, sir."


# ─────────────────────────────────────────────
# BRIGHTNESS
# ─────────────────────────────────────────────

def set_brightness(level) -> str:
    """Set screen brightness (0-100 percent)."""
    try:
        level = int(float(level))
        level = max(0, min(100, level))
        fraction = round(level / 100.0, 2)
        # Try the 'brightness' CLI tool first (brew install brightness)
        result = _run_shell(f'brightness {fraction} 2>/dev/null')
        if 'not found' in result.lower() or 'error' in result.lower():
            # Fallback: use AppleScript with keyboard brightness keys
            # This uses System Events to simulate brightness adjustment
            steps = int(level / 6.25)  # 16 steps total on Mac
            _run_shell('osascript -e \'tell application "System Events" to key code 145\' ' * 16)  # Min brightness
            for _ in range(steps):
                _run_shell('osascript -e \'tell application "System Events" to key code 144\'')  # Increase
        return f"Brightness set to {level}%, sir."
    except Exception as e:
        return f"Brightness control error: {str(e)}"


# ─────────────────────────────────────────────
# WEB SEARCH (SerpAPI)
# ─────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web using SerpAPI and return top results."""
    if not SERPAPI_KEY:
        return "SerpAPI key not configured. Cannot perform web search."
    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "engine": "google",
            "num": 5
        }
        resp = req.get("https://serpapi.com/search", params=params, timeout=15)
        if resp.status_code != 200:
            return f"Search failed with status {resp.status_code}"
        data = resp.json()

        # Build a clean summary from organic results
        results = []
        for item in data.get("organic_results", [])[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            results.append(f"• {title}\n  {snippet}\n  {link}")

        # Also grab the answer box if present
        answer_box = data.get("answer_box", {})
        direct_answer = answer_box.get("answer") or answer_box.get("snippet") or ""

        output = ""
        if direct_answer:
            output += f"Direct answer: {direct_answer}\n\n"
        if results:
            output += "Top results:\n" + "\n\n".join(results)
        else:
            output += "No results found."

        return output
    except Exception as e:
        return f"Web search error: {str(e)}"


# ─────────────────────────────────────────────
# COMMAND DISPATCHER (with argument normalization)
# ─────────────────────────────────────────────

TOOL_MAP = {
    "open_app": open_app,
    "open_website": open_website,
    "send_whatsapp": send_whatsapp,
    "open_file": open_file,
    "open_folder": open_folder,
    "create_file": create_file,
    "create_folder": create_folder,
    "take_notes": take_notes,
    "list_windows": list_windows,
    "focus_window": focus_window,
    "system_shutdown": system_shutdown,
    "system_sleep": system_sleep,
    "system_restart": system_restart,
    "take_screenshot": take_screenshot,
    "play_music": play_music,
    "search_files": search_files,
    "set_volume": set_volume,
    "mute_volume": mute_volume,
    "unmute_volume": unmute_volume,
    "set_brightness": set_brightness,
    "web_search": web_search,
}

# Free models often send wrong param names. Map common variants to correct ones.
ARGUMENT_ALIASES = {
    "create_folder": {"path": "folder_path", "name": "folder_path", "directory": "folder_path", "dir": "folder_path", "folderpath": "folder_path", "folder": "folder_path"},
    "create_file": {"path": "file_path", "name": "file_path", "filename": "file_path", "filepath": "file_path", "file": "file_path", "text": "content", "body": "content", "data": "content"},
    "open_file": {"path": "file_path", "name": "file_path", "filename": "file_path", "filepath": "file_path", "file": "file_path"},
    "open_folder": {"path": "folder_path", "name": "folder_path", "directory": "folder_path", "dir": "folder_path", "folderpath": "folder_path", "folder": "folder_path"},
    "open_app": {"name": "app_name", "app": "app_name", "application": "app_name", "appname": "app_name"},
    "open_website": {"website": "url", "link": "url", "site": "url", "address": "url"},
    "send_whatsapp": {"name": "contact", "to": "contact", "recipient": "contact", "text": "message", "msg": "message", "body": "message"},
    "play_music": {"song": "query", "search": "query", "name": "query", "track": "query", "music": "query"},
    "search_files": {"search": "query", "name": "query", "filename": "query", "pattern": "query", "path": "directory", "dir": "directory", "folder": "directory"},
    "set_volume": {"volume": "level", "value": "level", "percent": "level"},
    "web_search": {"search": "query", "q": "query", "term": "query", "text": "query"},
    "take_notes": {"content": "text", "notes": "text", "note": "text", "body": "text", "message": "text"},
    "focus_window": {"name": "app_name", "app": "app_name", "window": "app_name"},
    "set_brightness": {"value": "level", "brightness": "level", "percent": "level"},
}


def _normalize_args(tool_name, args):
    """Normalize argument names using aliases, handling free model quirks."""
    aliases = ARGUMENT_ALIASES.get(tool_name, {})
    normalized = {}
    for key, value in args.items():
        # Use alias if available, otherwise keep original
        canonical = aliases.get(key.lower(), key)
        normalized[canonical] = value
    return normalized


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments. Includes argument normalization."""
    func = TOOL_MAP.get(tool_name)
    if not func:
        return f"Unknown tool: {tool_name}"

    # Normalize argument names
    normalized = _normalize_args(tool_name, arguments)

    try:
        return func(**normalized)
    except TypeError as e:
        # If still failing, try to match by position using inspect
        import inspect
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            values = list(normalized.values())

            # Try positional mapping
            if values and params:
                positional_args = {}
                for i, param_name in enumerate(params):
                    if param_name in normalized:
                        positional_args[param_name] = normalized[param_name]
                    elif i < len(values):
                        positional_args[param_name] = values[i]
                return func(**positional_args)
        except Exception:
            pass
        return f"Error executing {tool_name}: {str(e)}"
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"
