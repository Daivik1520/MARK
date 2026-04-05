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

def _search_args(m):
    return {"query": m.group(1).strip()}

def _recall_args(m):
    return {"query": m.group(1).strip()}

def _save_mem_args(m):
    return {"key": m.group(1).strip(), "value": m.group(2).strip()}

def _track_args(m):
    return {"phone": m.group(1).strip()}

def _news_args(m):
    topic = m.group(1).strip() if m.lastindex and m.group(1) else ""
    return {"topic": topic}

def _research_args(m):
    return {"topic": m.group(1).strip()}

def _scroll_args(m):
    return {"direction": m.group(1), "amount": m.group(2) or "3"}

def _tile_args(m):
    return {"app1": m.group(1).strip(), "app2": m.group(2).strip()}

def _move_win_args(m):
    return {"app_name": m.group(1).strip(), "position": m.group(2).strip()}


FAST_ROUTES = [
    # ── Volume ──
    (re.compile(r'(?:set\s+)?volume\s+(?:to\s+)?(\d+)', re.I), "set_volume", _vol_args),
    (re.compile(r'^mute$|^mute\s+(?:the\s+)?(?:volume|sound|audio)', re.I), "mute_volume", lambda m: {}),
    (re.compile(r'^unmute$|^unmute\s+(?:the\s+)?(?:volume|sound|audio)', re.I), "unmute_volume", lambda m: {}),
    (re.compile(r'(?:turn\s+)?(?:volume\s+)?(?:up|louder)\s*$', re.I), "set_volume", lambda m: {"level": 70}),
    (re.compile(r'(?:turn\s+)?(?:volume\s+)?(?:down|quieter|lower)\s*$', re.I), "set_volume", lambda m: {"level": 30}),

    # ── Brightness ──
    (re.compile(r'(?:set\s+)?brightness\s+(?:to\s+)?(\d+)', re.I), "set_brightness", _bright_args),
    (re.compile(r'brightness\s+(?:up|max|full|high)', re.I), "set_brightness", lambda m: {"level": 100}),
    (re.compile(r'brightness\s+(?:down|low|dim)', re.I), "set_brightness", lambda m: {"level": 20}),

    # ── Screenshot ──
    (re.compile(r'(?:take\s+(?:a\s+)?)?screenshot', re.I), "take_screenshot", lambda m: {}),

    # ── System Power ──
    (re.compile(r'^(?:go\s+to\s+)?sleep$|^put\s+(?:the\s+)?(?:system|computer|mac)\s+to\s+sleep', re.I), "system_sleep", lambda m: {}),
    (re.compile(r'^shutdown$|^shut\s*down(?:\s+the)?(?:\s+system|\s+computer|\s+mac)?', re.I), "system_shutdown", lambda m: {}),
    (re.compile(r'^restart$|^restart\s+(?:the\s+)?(?:system|computer|mac)', re.I), "system_restart", lambda m: {}),

    # ── System Info ──
    (re.compile(r'system\s+(?:stats|health|status|info(?:rmation)?)|(?:how\s+is\s+my\s+)?(?:cpu|ram|memory|disk|battery)\s*(?:usage|status|level)?|(?:check|show)\s+(?:my\s+)?(?:system|cpu|ram|memory)', re.I), "get_system_stats", lambda m: {}),
    (re.compile(r'(?:get|show)\s+system\s+info(?:rmation)?', re.I), "get_system_info", lambda m: {}),

    # ── Run Routine ──
    (re.compile(r'(?:start|activate|begin|run)\s+((?:\w+\s+)*(?:mode|routine)|good\s+morning)', re.I), "run_routine", lambda m: {"name": m.group(1).strip()}),
    (re.compile(r'(?:list|show|what)\s+(?:are\s+(?:the|my)\s+)?(?:all\s+)?routines|what\s+modes', re.I), "list_routines", lambda m: {}),

    # ── Open App ──
    (re.compile(r'(?:open|launch|start)\s+(?:the\s+)?(?:app\s+)?(.+?)(?:\s+app)?$', re.I), "open_app", _app_args),

    # ── Open Website ──
    (re.compile(r'(?:open|go\s+to|visit|navigate\s+to)\s+((?:https?://)?(?:www\.)?[\w.-]+\.\w{2,}(?:/\S*)?)', re.I), "open_website", _website_args),

    # ── Focus / Tile / Window Management ──
    (re.compile(r'focus\s+(?:on\s+)?(.+)', re.I), "focus_app", _focus_args),
    (re.compile(r'dim\s+(?:all\s+|everything\s+)?(?:except|but)\s+(.+)', re.I), "dim_all_except", _dim_args),
    (re.compile(r'show\s+all\s+windows|restore\s+(?:all\s+)?windows', re.I), "show_all_windows", lambda m: {}),
    (re.compile(r'tile\s+(.+?)\s+(?:and|with)\s+(.+)', re.I), "tile_windows", _tile_args),
    (re.compile(r'move\s+(.+?)\s+(?:window\s+)?to\s+(left|right|center|top|bottom|fullscreen|top-left|top-right|bottom-left|bottom-right)', re.I), "move_window", _move_win_args),

    # ── Windows List ──
    (re.compile(r'(?:list|show|what\s+are)\s+(?:the\s+)?(?:open\s+|opened\s+|current\s+)?windows|what(?:\'s|\s+is)\s+(?:currently\s+)?open|(?:what|which)\s+(?:apps|applications)\s+(?:are\s+)?(?:open|running|currently)', re.I), "list_windows", lambda m: {}),

    # ── Play Music ──
    (re.compile(r'play\s+(.+)', re.I), "play_music", _music_args),

    # ── Clean Up ──
    (re.compile(r'clean\s+(?:my\s+)?(?:the\s+)?desktop|tidy\s+(?:up\s+)?(?:my\s+)?desktop|organize\s+(?:my\s+)?desktop', re.I), "clean_desktop", lambda m: {}),
    (re.compile(r'clean\s+(?:my\s+)?(?:the\s+)?downloads|organize\s+(?:my\s+)?downloads', re.I), "organize_downloads", lambda m: {}),

    # ── Focus Bubble ──
    (re.compile(r'(?:lock\s+me\s+in|focus\s+mode|no\s+distractions|start\s+focus)(?:\s+for\s+(\d+)\s*(?:min|minute|minutes|hour|hours|hr|hrs))?', re.I), "start_focus", lambda m: {"duration_minutes": m.group(1) or "60"}),
    (re.compile(r'(?:stop|end|exit|cancel)\s+focus(?:\s+mode)?|(?:unlock|unfocus)', re.I), "stop_focus", lambda m: {}),

    # ── Screen Analysis ──
    (re.compile(r'(?:what(?:\'s|\s+is)\s+on\s+my\s+screen|analyze\s+(?:my\s+)?screen|look\s+at\s+my\s+screen|read\s+(?:my\s+)?screen|what\s+(?:do\s+you\s+see|can\s+you\s+see)|describe\s+(?:my\s+)?screen)', re.I), "analyze_screen", lambda m: {"query": "Describe what you see on the screen"}),

    # ── Context ──
    (re.compile(r'what\s+(?:am\s+I|app\s+is)\s+(?:looking\s+at|in|using)|(?:get|show)\s+context|what\s+(?:page|tab|website)\s+(?:am\s+I|is)\s+(?:on|open)', re.I), "get_context", lambda m: {}),

    # ── Memory ──
    (re.compile(r'(?:list|show|what\s+do\s+you)\s+(?:all\s+)?(?:my\s+)?memories|what\s+do\s+you\s+remember', re.I), "list_memories", lambda m: {}),
    (re.compile(r'(?:recall|remember|what(?:\'s|\s+is)\s+(?:my|the))\s+(.+)', re.I), "recall_memory", _recall_args),
    (re.compile(r'rag\s+stats|memory\s+stats', re.I), "rag_stats", lambda m: {}),

    # ── Reminders ──
    (re.compile(r'(?:list|show|what\s+are)\s+(?:my\s+)?reminders', re.I), "list_reminders", lambda m: {}),
    (re.compile(r'clear\s+(?:all\s+)?reminders', re.I), "clear_reminders", lambda m: {}),
    (re.compile(r'remind\s+me\s+(?:to\s+)?(.+?)\s+(?:in|at|on|tomorrow)\s+(.+)', re.I), "set_reminder", _reminder_args),

    # ── Clipboard ──
    (re.compile(r'(?:show|get)\s+(?:my\s+)?clipboard(?:\s+history)?|what\s+did\s+I\s+copy', re.I), "get_clipboard_history", lambda m: {}),

    # ── Web Search ──
    (re.compile(r'(?:search\s+(?:for|the\s+web\s+for|google)\s+|google\s+)(.+)', re.I), "web_search", _search_args),

    # ── News ──
    (re.compile(r'(?:give\s+me\s+(?:a\s+)?|what(?:\'s|\s+is)\s+(?:the\s+)?)(?:news|headlines|briefing|morning\s+update|what(?:\'s|\s+is)\s+happening)(?:\s+(?:about|on)\s+(.+))?', re.I), "get_news_briefing", _news_args),
    (re.compile(r'news\s+(?:about|on)\s+(.+)', re.I), "get_news", _news_args),

    # ── Research ──
    (re.compile(r'research\s+(?:the\s+topic\s+of\s+|about\s+)?(.+)', re.I), "research_topic", _research_args),

    # ── Track Phone ──
    (re.compile(r'(?:track|look\s+up|find|check)\s+(?:(?:the\s+)?number\s+|phone\s+number\s+)?(\+?[\d\s\-]{7,})', re.I), "track_number", _track_args),

    # ── Password ──
    (re.compile(r'(?:generate|create|make)\s+(?:a\s+)?(?:strong\s+|secure\s+)?password', re.I), "generate_password", lambda m: {}),

    # ── Open File/Folder ──
    (re.compile(r'open\s+(?:the\s+)?file\s+(.+)', re.I), "open_file", _file_args),
    (re.compile(r'open\s+(?:the\s+)?folder\s+(.+)', re.I), "open_folder", _folder_args),

    # ── Ghost Cursor ──
    (re.compile(r'move\s+(?:the\s+)?mouse\s+(?:to\s+)?(\d+)\s+(\d+)', re.I), "move_mouse", lambda m: {"x": m.group(1), "y": m.group(2)}),
    (re.compile(r'click\s+(?:at\s+)?(\d+)\s+(\d+)', re.I), "click_at", lambda m: {"x": m.group(1), "y": m.group(2)}),
    (re.compile(r'scroll\s+(up|down|left|right)(?:\s+(\d+))?', re.I), "scroll_screen", _scroll_args),
    (re.compile(r'(?:get\s+)?screen\s+size', re.I), "get_screen_size", lambda m: {}),

    # ── Vision ──
    (re.compile(r'(?:click(?:\s+on)?|press)\s+(?:the\s+)?(.+?)(?:\s+button|\s+icon|\s+link)?$', re.I), "vision_click", lambda m: {"instruction": m.group(1).strip()}),
    (re.compile(r'describe\s+(?:what\'s\s+on\s+screen|all\s+(?:buttons|ui\s+elements))', re.I), "vision_describe", lambda m: {}),

    # ── Website Builder ──
    (re.compile(r'(?:make|build|create|generate)\s+(?:me\s+)?(?:a\s+)?(.+?)\s+(?:website|site|page|webpage)', re.I), "build_website", lambda m: {"description": m.group(1).strip() + " website"}),

    # ── Code Writer ──
    (re.compile(r'(?:write|create|generate|make)\s+(?:me\s+)?(?:a\s+)?(.+?)\s+(?:script|program|code|function)(?:\s+in\s+(\w+))?', re.I), "write_code", lambda m: {"description": m.group(1).strip(), "language": m.group(2) or "python"}),
]


def try_fast_route(user_text):
    """
    Try to match the user's text against fast-route patterns.
    Returns: {"text": str, "tool_calls": list} if matched, None if not.
    """
    text = user_text.strip()
    if not text:
        return None

    words = text.lower().split()

    # Very short inputs → always let AI handle (greetings, etc.)
    single_word_cmds = {"mute", "unmute", "screenshot", "shutdown", "restart", "sleep"}
    if len(words) <= 1 and text.lower() not in single_word_cmds:
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
