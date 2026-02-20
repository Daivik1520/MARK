"""
MARK — Fast Router
Regex-based local command matcher that bypasses the AI entirely for common commands.
Executes in <100ms instead of 4-16 seconds.
"""

import re
from core.system_controller import execute_tool


# ─────────────────────────────────────────────
# FAST ROUTE PATTERNS
# Each entry: (compiled_regex, tool_name, arg_extractor_function)
# ─────────────────────────────────────────────

def _vol_args(m):
    return {"level": int(m.group(1))}

def _bright_args(m):
    return {"level": int(m.group(1))}

def _app_args(m):
    return {"app_name": m.group(1).strip()}

def _focus_args(m):
    return {"app_name": m.group(1).strip()}

def _music_args(m):
    song = m.group(1).strip()
    platform = "youtube"
    # Check if user specified platform
    lower = song.lower()
    if "on spotify" in lower:
        platform = "spotify"
        song = re.sub(r'\s+on\s+spotify', '', song, flags=re.I).strip()
    elif "on youtube" in lower:
        song = re.sub(r'\s+on\s+youtube', '', song, flags=re.I).strip()
    return {"query": song, "platform": platform}

def _website_args(m):
    url = m.group(1).strip()
    return {"url": url}

def _focus_dur_args(m):
    return {"duration_minutes": m.group(1)}

def _file_args(m):
    return {"file_path": m.group(1).strip()}

def _folder_args(m):
    return {"folder_path": m.group(1).strip()}

def _dim_args(m):
    return {"app_name": m.group(1).strip()}

def _move_args(m):
    return {"app_name": m.group(1).strip(), "position": m.group(2).strip()}

def _reminder_args(m):
    return {"message": m.group(1).strip(), "time_str": m.group(2).strip()}


FAST_ROUTES = [
    # ── Volume ──
    (re.compile(r'(?:set\s+)?volume\s+(?:to\s+)?(\d+)', re.I), "set_volume", _vol_args),
    (re.compile(r'^mute$|^mute\s+(?:the\s+)?(?:volume|sound|audio)', re.I), "mute_volume", lambda m: {}),
    (re.compile(r'^unmute$|^unmute\s+(?:the\s+)?(?:volume|sound|audio)', re.I), "unmute_volume", lambda m: {}),

    # ── Brightness ──
    (re.compile(r'(?:set\s+)?brightness\s+(?:to\s+)?(\d+)', re.I), "set_brightness", _bright_args),

    # ── Screenshot ──
    (re.compile(r'(?:take\s+(?:a\s+)?)?screenshot', re.I), "take_screenshot", lambda m: {}),

    # ── System Power ──
    (re.compile(r'^(?:go\s+to\s+)?sleep$|^put\s+(?:the\s+)?(?:system|computer|mac)\s+to\s+sleep', re.I), "system_sleep", lambda m: {}),
    (re.compile(r'^shutdown$|^shut\s*down(?:\s+the)?(?:\s+system|\s+computer|\s+mac)?', re.I), "system_shutdown", lambda m: {}),
    (re.compile(r'^restart$|^restart\s+(?:the\s+)?(?:system|computer|mac)', re.I), "system_restart", lambda m: {}),

    # ── Open App ──
    (re.compile(r'(?:open|launch|start)\s+(?:the\s+)?(?:app\s+)?(.+?)(?:\s+app)?$', re.I), "open_app", _app_args),

    # ── Open Website ──
    (re.compile(r'(?:open|go\s+to|visit|navigate\s+to)\s+((?:https?://)?(?:www\.)?[\w.-]+\.\w{2,}(?:/\S*)?)', re.I), "open_website", _website_args),

    # ── Focus App ──
    (re.compile(r'focus\s+(?:on\s+)?(.+)', re.I), "focus_app", _focus_args),

    # ── Dim All Except ──
    (re.compile(r'dim\s+(?:all\s+|everything\s+)?(?:except|but)\s+(.+)', re.I), "dim_all_except", _dim_args),

    # ── Show All Windows ──
    (re.compile(r'show\s+all\s+windows|restore\s+(?:all\s+)?windows', re.I), "show_all_windows", lambda m: {}),

    # ── Play Music ──
    (re.compile(r'play\s+(.+)', re.I), "play_music", _music_args),

    # ── Clean Desktop/Downloads ──
    (re.compile(r'clean\s+(?:my\s+)?(?:the\s+)?desktop|tidy\s+(?:up\s+)?(?:my\s+)?desktop|organize\s+(?:my\s+)?desktop', re.I), "clean_desktop", lambda m: {}),
    (re.compile(r'clean\s+(?:my\s+)?(?:the\s+)?downloads|organize\s+(?:my\s+)?downloads', re.I), "organize_downloads", lambda m: {}),

    # ── Focus Bubble ──
    (re.compile(r'(?:lock\s+me\s+in|focus\s+mode|no\s+distractions|start\s+focus)(?:\s+for\s+(\d+)\s*(?:min|minute|minutes|hour|hours|hr|hrs))?', re.I), "start_focus", lambda m: {"duration_minutes": m.group(1) or "60"}),
    (re.compile(r'(?:stop|end|exit|cancel)\s+focus(?:\s+mode)?|(?:unlock|unfocus)', re.I), "stop_focus", lambda m: {}),

    # ── List Windows ──
    (re.compile(r'(?:list|show)\s+(?:all\s+)?(?:open\s+)?windows|what(?:\'s| is)\s+open', re.I), "list_windows", lambda m: {}),

    # ── System Stats ──
    (re.compile(r'system\s+(?:stats|health|status)|how\s+is\s+my\s+(?:system|computer|mac)', re.I), "get_system_stats", lambda m: {}),

    # ── List Reminders ──
    (re.compile(r'(?:list|show|what are)\s+(?:my\s+)?reminders', re.I), "list_reminders", lambda m: {}),

    # ── Clear Reminders ──
    (re.compile(r'clear\s+(?:all\s+)?reminders', re.I), "clear_reminders", lambda m: {}),

    # ── List Memories ──
    (re.compile(r'(?:list|show|what do you)\s+(?:all\s+)?(?:my\s+)?memories|what\s+do\s+you\s+remember', re.I), "list_memories", lambda m: {}),

    # ── List Routines ──
    (re.compile(r'(?:list|show|what)\s+(?:all\s+)?routines|what\s+modes', re.I), "list_routines", lambda m: {}),

    # ── Clipboard ──
    (re.compile(r'(?:show|get)\s+(?:my\s+)?clipboard(?:\s+history)?|what\s+did\s+I\s+copy', re.I), "get_clipboard_history", lambda m: {}),

    # ── Context ──
    (re.compile(r'what\s+(?:am\s+I|app\s+is)\s+(?:looking\s+at|in|using)|(?:get|show)\s+context', re.I), "get_context", lambda m: {}),

    # ── Open File ──
    (re.compile(r'open\s+(?:the\s+)?file\s+(.+)', re.I), "open_file", _file_args),

    # ── Open Folder ──
    (re.compile(r'open\s+(?:the\s+)?folder\s+(.+)', re.I), "open_folder", _folder_args),

    # ── Ghost Cursor ──
    (re.compile(r'move\s+(?:the\s+)?mouse\s+(?:to\s+)?(\d+)\s+(\d+)', re.I), "move_mouse", lambda m: {"x": m.group(1), "y": m.group(2)}),
    (re.compile(r'click\s+(?:at\s+)?(\d+)\s+(\d+)', re.I), "click_at", lambda m: {"x": m.group(1), "y": m.group(2)}),
    (re.compile(r'scroll\s+(up|down|left|right)(?:\s+(\d+))?', re.I), "scroll_screen", lambda m: {"direction": m.group(1), "amount": m.group(2) or "3"}),
    (re.compile(r'(?:get\s+)?screen\s+size', re.I), "get_screen_size", lambda m: {}),

    # ── Website Builder ──
    (re.compile(r'(?:make|build|create|generate)\s+(?:me\s+)?(?:a\s+)?(.+?)\s+(?:website|site|page|webpage)', re.I), "build_website", lambda m: {"description": m.group(1).strip() + " website"}),
]

# Commands that should NOT be fast-routed (need AI reasoning)
SKIP_PATTERNS = [
    re.compile(r'(what|how|why|when|where|who|can you|could you|tell me|explain|describe|help)', re.I),
]


def try_fast_route(user_text):
    """
    Try to match the user's text against fast-route patterns.
    Returns: {"text": str, "tool_calls": list} if matched, None if not.
    """
    text = user_text.strip()
    if not text:
        return None

    # Skip phrases that clearly need AI reasoning
    # But only if they DON'T also match a clear command pattern
    # e.g. "what's open" should still fast-route to list_windows
    words = text.lower().split()

    # Very short inputs or greetings → let AI handle
    if len(words) <= 1 and text.lower() not in ("mute", "unmute", "screenshot", "shutdown", "restart", "sleep"):
        return None

    # Try each fast route pattern
    for pattern, tool_name, arg_extractor in FAST_ROUTES:
        match = pattern.search(text)
        if match:
            try:
                args = arg_extractor(match)
                result = execute_tool(tool_name, args)
                return {
                    "text": result,
                    "tool_calls": [{"name": tool_name, "result": result}],
                    "fast_routed": True,
                }
            except Exception as e:
                # If fast route fails, fall through to AI
                print(f"  ⚡ Fast route failed for {tool_name}: {e}")
                return None

    return None
