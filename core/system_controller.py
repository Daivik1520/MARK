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

# Import feature modules
# Import feature modules
from tools.memory_manager import save_memory, recall_memory, list_memories, delete_memory
from tools.vision_engine import analyze_screen
from services.routines import run_routine, list_routines, create_routine
from tools.reminder_manager import set_reminder, list_reminders, delete_reminder, clear_reminders
from tools.phone_tracker import track_number
from tools.clipboard_manager import get_clipboard_history, search_clipboard, paste_from_history, start_clipboard_monitor
from core.context_engine import get_context
from tools.news_briefing import get_news_briefing, get_news
from tools.code_runner import run_code
from tools.password_gen import generate_password
from services.proactive_monitor import get_system_stats
from tools.window_manager import tile_windows, focus_app, dim_all_except, move_window, show_all_windows, get_open_windows, maximize_window
from agents.web_steerer import web_search_deep, web_get_stock, web_book_restaurant, web_navigate
from tools.digital_janitor import clean_desktop, organize_downloads
from agents.code_writer import write_code
from agents.research_agent import research_topic
from tools.image_tools import edit_image
from services.focus_bubble import start_focus, stop_focus
from agents.browser_copilot import browser_do
from agents.universal_search import search_content
from agents.data_extractor import scrape_data
from tools.ghost_cursor import move_mouse, click_at, click_text, scroll_screen, type_text, drag_to, get_screen_size
from agents.website_builder import build_website
from tools.terminal import run_terminal, read_file, write_file, edit_file, list_directory, get_system_info
from core.mcp_client import (
    mcp_status, mcp_connect, mcp_disconnect, mcp_list_tools,
    mcp_add_server, mcp_remove_server, mcp_call_tool_sync, mcp_is_tool,
)
from tools.vision_click import vision_click, vision_find, vision_describe, vision_type, vision_interact
from tools.rag_memory import rag_remember, rag_recall, rag_forget, rag_list, rag_stats
from core.ollama_engine import check_ollama, list_ollama_models, pull_ollama_model, set_ollama_model


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
    """Open an application or alias efficiently."""
    import re
    aliases = {
        "yt": "YouTube",
        "fb": "Facebook",
        "ig": "Instagram",
        "whatsapp": "WhatsApp",
        "discord": "Discord",
        "vscode": "Visual Studio Code"
    }

    # Split by " and " or "," to handle multiple apps in one command
    parts = [p.strip() for p in re.split(r'\band\b|,', app_name, flags=re.IGNORECASE) if p.strip()]
    results = []

    for part in parts:
        target = aliases.get(part.lower(), part)

        # Check if the user is actually trying to run a routine 
        # (e.g. "open coding mode", "start study mode")
        if target.lower().endswith(" mode") or target.lower().endswith(" routine") or target.lower() == "good morning":
            from services.routines import run_routine
            # Try to run the routine instead of opening an app
            res = run_routine(target)
            results.append(target)
            continue

        # Handle website redirections for apps that are just sites
        if target.lower() in ("youtube", "youtube.com"):
            open_website("youtube.com")
            results.append("YouTube")
            continue
        elif target.lower() in ("facebook", "facebook.com"):
            open_website("facebook.com")
            results.append("Facebook")
            continue
        elif target.lower() in ("instagram", "instagram.com"):
            open_website("instagram.com")
            results.append("Instagram")
            continue

        # Try `open -a` first for speed and reliability, avoiding Spotlight UI
        ret = os.system(f'open -a "{target}" 2>/dev/null')
        if ret == 0:
            results.append(target)
        else:
            # Fallback to Spotlight search
            script = f'''
            tell application "System Events"
                key code 49 using command down
                delay 0.5
                keystroke "{target}"
                delay 1.0
                key code 36
            end tell
            '''
            _run_applescript(script)
            results.append(target)

    return f"Opened {', '.join(results)} now, sir."


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
    """Open WhatsApp, search for a contact using Cmd+F, and send a message."""
    # Use clipboard approach since WhatsApp text fields reject keystroke
    safe_contact = contact.replace('\\', '\\\\').replace('"', '\\"')
    safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
    
    script = f'''
    -- Step 1: Open WhatsApp
    tell application "WhatsApp" to activate
    delay 2.5
    
    tell application "System Events"
        tell process "WhatsApp"
            set frontmost to true
        end tell
        delay 0.5
        
        -- Step 2: Cmd+F to search chats (more reliable than Cmd+N)
        keystroke "f" using command down
        delay 1.5
    end tell
    
    -- Step 3: Paste the contact name via clipboard
    set the clipboard to "{safe_contact}"
    delay 0.3
    tell application "System Events"
        keystroke "v" using command down
        delay 2.5
        
        -- Step 4: Select first result
        key code 125  -- Down arrow
        delay 0.5
        key code 36   -- Enter to open chat
        delay 2.0
    end tell
    
    -- Step 5: Paste the message via clipboard
    set the clipboard to "{safe_message}"
    delay 0.3
    tell application "System Events"
        keystroke "v" using command down
        delay 0.8
        
        -- Step 6: Send
        key code 36   -- Enter to send
        delay 0.5
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
        import re

        # Scrape YouTube search results to find the first video ID
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            resp = req.get(search_url, headers=headers, timeout=10)
            # Extract the first video ID from the page
            match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
            if match:
                video_id = match.group(1)
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                script = f'open location "{video_url}"'
                _run_applescript(script)
                return f"Playing {query} on YouTube, sir."
        except Exception as e:
            print(f"  ✗ YouTube scrape error: {e}")

        # Fallback: open search results
        script = f'open location "{search_url}"'
        _run_applescript(script)
        return f"Playing {query} on YouTube, sir."


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
        import ctypes
        import ctypes.util

        level = int(float(level))
        level = max(0, min(100, level))
        fraction = level / 100.0

        # Use macOS DisplayServices private framework (works on Apple Silicon & Intel)
        CoreGraphics = ctypes.CDLL(ctypes.util.find_library('CoreGraphics'))
        DisplayServices = ctypes.CDLL(
            '/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices'
        )

        # Get main display ID
        CGMainDisplayID = CoreGraphics.CGMainDisplayID
        CGMainDisplayID.restype = ctypes.c_uint32
        display_id = CGMainDisplayID()

        # Set brightness via DisplayServices
        DisplayServicesSetBrightness = DisplayServices.DisplayServicesSetBrightness
        DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
        DisplayServicesSetBrightness.restype = ctypes.c_int

        err = DisplayServicesSetBrightness(display_id, ctypes.c_float(fraction))
        if err != 0:
            # Fallback: try the 'brightness' CLI tool (brew install brightness)
            result = _run_shell(f'brightness {fraction:.2f} 2>/dev/null')
            if 'not found' in result.lower() or 'error' in result.lower():
                return f"Brightness control failed (error code {err}). Try: brew install brightness"

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
    # Memory
    "save_memory": save_memory,
    "recall_memory": recall_memory,
    "list_memories": list_memories,
    "delete_memory": delete_memory,
    # Vision
    "analyze_screen": analyze_screen,
    # Routines
    "run_routine": run_routine,
    "list_routines": list_routines,
    "create_routine": create_routine,
    # Reminders
    "set_reminder": set_reminder,
    "list_reminders": list_reminders,
    "delete_reminder": delete_reminder,
    "clear_reminders": clear_reminders,
    # Phone
    "track_number": track_number,
    # Clipboard
    "get_clipboard_history": get_clipboard_history,
    "search_clipboard": search_clipboard,
    "paste_from_history": paste_from_history,
    # Context
    "get_context": get_context,
    # News
    "get_news_briefing": get_news_briefing,
    "get_news": get_news,
    # Code Runner
    "run_code": run_code,
    # Password
    "generate_password": generate_password,
    # System Health
    "get_system_stats": get_system_stats,
    # Window Management
    "tile_windows": tile_windows,
    "focus_app": focus_app,
    "dim_all_except": dim_all_except,
    "move_window": move_window,
    "show_all_windows": show_all_windows,
    "get_open_windows": get_open_windows,
    "maximize_window": maximize_window,
    # Web Steerer
    "web_search_deep": web_search_deep,
    "web_get_stock": web_get_stock,
    "web_book_restaurant": web_book_restaurant,
    "web_navigate": web_navigate,
    # Digital Janitor
    "clean_desktop": clean_desktop,
    "organize_downloads": organize_downloads,
    # Code Writer
    "write_code": write_code,
    # Research Agent
    "research_topic": research_topic,
    # Image Tools
    "edit_image": edit_image,
    # Focus Bubble
    "start_focus": start_focus,
    "stop_focus": stop_focus,
    # Browser Copilot
    "browser_do": browser_do,
    # Universal Search
    "search_content": search_content,
    # Data Extractor
    "scrape_data": scrape_data,
    # Ghost Cursor
    "move_mouse": move_mouse,
    "click_at": click_at,
    "click_text": click_text,
    "scroll_screen": scroll_screen,
    "type_text": type_text,
    "drag_to": drag_to,
    "get_screen_size": get_screen_size,
    # Website Builder
    "build_website": build_website,
    # Terminal Executor
    "run_terminal": run_terminal,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_directory": list_directory,
    "get_system_info": get_system_info,
    # MCP (Model Context Protocol)
    "mcp_status": mcp_status,
    "mcp_connect": mcp_connect,
    "mcp_disconnect": mcp_disconnect,
    "mcp_list_tools": mcp_list_tools,
    "mcp_add_server": mcp_add_server,
    "mcp_remove_server": mcp_remove_server,
    # Vision Click (AI-powered screen interaction)
    "vision_click": vision_click,
    "vision_find": vision_find,
    "vision_describe": vision_describe,
    "vision_type": vision_type,
    "vision_interact": vision_interact,
    # RAG Memory (semantic vector memory)
    "rag_remember": rag_remember,
    "rag_recall": rag_recall,
    "rag_forget": rag_forget,
    "rag_list": rag_list,
    "rag_stats": rag_stats,
    # Ollama
    "check_ollama": check_ollama,
    "list_ollama_models": list_ollama_models,
    "pull_ollama_model": pull_ollama_model,
    "set_ollama_model": set_ollama_model,
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
    "save_memory": {"label": "key", "name": "key", "topic": "key", "info": "value", "data": "value", "text": "value", "content": "value", "memory": "value"},
    "recall_memory": {"search": "query", "key": "query", "topic": "query", "memory": "query", "name": "query"},
    "delete_memory": {"name": "key", "topic": "key", "memory": "key", "label": "key"},
    "analyze_screen": {"question": "query", "prompt": "query", "text": "query", "ask": "query"},
    "run_routine": {"routine": "name", "mode": "name", "routine_name": "name"},
    "create_routine": {"routine_name": "name", "steps": "steps_json"},
    "set_reminder": {"text": "message", "reminder": "message", "msg": "message", "content": "message", "time": "time_str", "when": "time_str", "at": "time_str", "in": "time_str"},
    "delete_reminder": {"id": "reminder_id", "message": "reminder_id", "text": "reminder_id", "name": "reminder_id"},
    "track_number": {"number": "phone", "phone_number": "phone", "mobile": "phone", "num": "phone", "contact": "phone"},
    "get_clipboard_history": {"n": "count", "number": "count", "limit": "count"},
    "search_clipboard": {"search": "query", "keyword": "query", "text": "query", "find": "query"},
    "paste_from_history": {"i": "index", "number": "index", "num": "index", "item": "index"},
    "get_news_briefing": {"subject": "topic", "category": "topic", "about": "topic"},
    "get_news": {"subject": "topic", "category": "topic", "about": "topic", "number": "count", "limit": "count", "n": "count"},
    "run_code": {"script": "code", "program": "code", "source": "code", "lang": "language", "type": "language"},
    "generate_password": {"len": "length", "size": "length", "chars": "length", "type": "options", "flags": "options", "mode": "options"},
    "tile_windows": {"first": "app1", "second": "app2", "direction": "layout", "split": "layout", "mode": "layout"},
    "focus_app": {"app": "app_name", "application": "app_name", "window": "app_name"},
    "dim_all_except": {"app": "app_name", "application": "app_name", "keep": "app_name", "focus": "app_name"},
    "move_window": {"app": "app_name", "application": "app_name", "pos": "position", "where": "position", "location": "position"},
    "web_search_deep": {"search": "query", "q": "query", "topic": "query", "find": "query"},
    "web_get_stock": {"symbol": "ticker", "stock": "ticker", "company": "ticker"},
    "web_book_restaurant": {"food": "query", "type": "query", "cuisine": "query", "city": "location", "area": "location", "where": "location"},
    "web_navigate": {"link": "url", "site": "url", "page": "url", "address": "url"},
    "clean_desktop": {},
    "organize_downloads": {},
    "show_hud_card": {"text": "content", "body": "content", "message": "content", "heading": "title",
                      "emoji": "icon", "time": "duration", "seconds": "duration"},
    "write_code": {"desc": "description", "prompt": "description", "what": "description", "task": "description",
                   "lang": "language", "type": "language", "in": "language",
                   "name": "filename", "file": "filename", "save_as": "filename"},
    "research_topic": {"query": "topic", "subject": "topic", "about": "topic", "search": "topic",
                        "level": "depth", "mode": "depth", "type": "depth"},
    "edit_image": {"image": "input_path", "source": "input_path", "file": "input_path", "input": "input_path",
                   "output": "output_path", "save_as": "output_path", "dest": "output_path",
                   "ops": "operations", "actions": "operations", "edits": "operations", "do": "operations"},
    "start_focus": {"duration": "duration_minutes", "time": "duration_minutes", "minutes": "duration_minutes",
                    "apps": "blocked_apps", "block_apps": "blocked_apps",
                    "sites": "blocked_sites", "block_sites": "blocked_sites", "websites": "blocked_sites"},
    "stop_focus": {},
    "browser_do": {"action": "task", "command": "task", "do": "task", "request": "task", "instructions": "task"},
    "search_content": {"search": "query", "find": "query", "look_for": "query", "text": "query",
                        "dirs": "directories", "folders": "directories", "paths": "directories", "in": "directories"},
    "scrape_data": {"url": "task", "scrape": "task", "extract": "task", "from": "task",
                    "format": "output_format", "type": "output_format",
                    "limit": "max_items", "count": "max_items", "top": "max_items"},
    "move_mouse": {},
    "click_at": {"click": "button"},
    "click_text": {"find": "text", "label": "text", "button": "text"},
    "scroll_screen": {"dir": "direction", "steps": "amount", "lines": "amount"},
    "type_text": {"write": "text", "input": "text", "string": "text"},
    "drag_to": {},
    "get_screen_size": {},
    "build_website": {"desc": "description", "prompt": "description", "what": "description", "type": "description",
                      "project": "name", "folder": "name", "title": "name"},
    # Terminal Executor
    "run_terminal": {"cmd": "command", "shell": "command", "exec": "command", "run": "command",
                     "dir": "working_dir", "cwd": "working_dir", "path": "working_dir",
                     "time": "timeout", "max_time": "timeout"},
    "read_file": {"path": "file_path", "file": "file_path", "name": "file_path"},
    "write_file": {"path": "file_path", "file": "file_path", "name": "file_path",
                   "text": "content", "data": "content", "body": "content"},
    "edit_file": {"path": "file_path", "file": "file_path", "name": "file_path",
                  "find": "old_text", "search": "old_text", "original": "old_text",
                  "replace": "new_text", "replacement": "new_text", "with": "new_text"},
    "list_directory": {"dir": "path", "folder": "path", "directory": "path",
                       "hidden": "show_hidden", "all": "show_hidden"},
    "get_system_info": {},
    # MCP
    "mcp_status": {},
    "mcp_connect": {"name": "server_name", "server": "server_name"},
    "mcp_disconnect": {"name": "server_name", "server": "server_name"},
    "mcp_list_tools": {},
    "mcp_add_server": {"server": "name", "server_name": "name", "cmd": "command",
                       "arguments": "args", "params": "args",
                       "environment": "env", "env_vars": "env"},
    "mcp_remove_server": {"server": "name", "server_name": "name"},
    # Vision Click
    "vision_click": {"target": "instruction", "element": "instruction", "button": "instruction",
                     "what": "instruction", "find": "instruction", "click": "instruction"},
    "vision_find": {"target": "instruction", "element": "instruction", "what": "instruction",
                    "look_for": "instruction", "search": "instruction"},
    "vision_describe": {},
    "vision_type": {"target": "instruction", "field": "instruction", "input": "instruction",
                    "content": "text", "value": "text", "string": "text"},
    "vision_interact": {"what": "target", "element": "target", "with": "target",
                        "do": "action", "type": "action"},
    # RAG Memory
    "rag_remember": {"info": "text", "data": "text", "memory": "text", "content": "text",
                     "type": "category", "tag": "category", "from": "source"},
    "rag_recall": {"search": "query", "find": "query", "what": "query", "about": "query",
                   "limit": "n_results", "count": "n_results", "top": "n_results"},
    "rag_forget": {"delete": "query", "remove": "query", "text": "query", "memory": "query"},
    "rag_list": {"type": "category", "tag": "category", "filter": "category"},
    "rag_stats": {},
    # Ollama
    "check_ollama": {},
    "list_ollama_models": {},
    "pull_ollama_model": {"model": "model_name", "name": "model_name"},
    "set_ollama_model": {"model": "model", "name": "model"},
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
    # Handle MCP tools dynamically
    if mcp_is_tool(tool_name):
        return mcp_call_tool_sync(tool_name, arguments)

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
