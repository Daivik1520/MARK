"""
MARK — Fast Router

Deterministic regex shortcuts for unambiguous imperative commands, so "volume
40" costs 30ms instead of a model round-trip.

Design rules, learned the hard way:

  1. Only match commands that are *unambiguous imperatives*. The old router
     sent anything starting with who/what/why straight to a web search, so
     "what is my favourite colour" opened a browser tab instead of consulting
     memory. Questions now always reach the model.

  2. No catch-all patterns. A trailing `.*` on "open X" swallowed entire
     sentences. Every pattern here is anchored and bounded.

  3. This runs *before* the model, never after it. Using it as a fallback meant
     a perfectly good spoken answer got thrown away and replaced by a search.

Anything that does not match falls through to the model, which is the correct
default — the model is now fast enough that the shortcut is a bonus, not a
crutch.
"""

import re
from core.tool_executor import run_tool

# Never shortcut these — they are conversation, not commands.
_QUESTION = re.compile(
    r"^\s*(?:who|what|what's|whats|where|when|why|how|which|is|are|am|do|does|did|"
    r"can|could|should|would|will|tell me|explain|show me why)\b",
    re.I,
)
_CONVERSATIONAL = re.compile(
    r"^\s*(?:hi|hey|hello|yo|thanks|thank you|good (?:morning|evening|night)|"
    r"mark|please|sorry|ok|okay|cool|nice|nvm|never mind)\b\s*[.!?]?\s*$",
    re.I,
)


# ─────────────────────────────────────────────
# ARGUMENT EXTRACTORS
# ─────────────────────────────────────────────

def _level(m):
    return {"level": int(m.group(1))}


def _app(m):
    return {"app_name": m.group(1).strip()}


def _url(m):
    return {"url": m.group(1).strip()}


def _music(m):
    song = m.group(1).strip()
    platform = "youtube"
    low = song.lower()
    if re.search(r"\b(?:on|in)\s+spotify\b", low):
        platform = "spotify"
        song = re.sub(r"\s+(?:on|in)\s+spotify\b", "", song, flags=re.I).strip()
    elif re.search(r"\b(?:on|in)\s+youtube\b", low):
        song = re.sub(r"\s+(?:on|in)\s+youtube\b", "", song, flags=re.I).strip()
    return {"query": song, "platform": platform}


def _folder(m):
    return {"folder_path": m.group(1).strip()}


def _file(m):
    return {"file_path": m.group(1).strip()}


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
# Ordered: most specific first. Every pattern is fully anchored.

FAST_ROUTES = [
    # ── Volume ──
    (re.compile(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})%?\s*$", re.I), "set_volume", _level),
    (re.compile(r"^mute(?:\s+(?:the\s+)?(?:volume|sound|audio))?\s*$", re.I), "mute_volume", lambda m: {}),
    (re.compile(r"^unmute(?:\s+(?:the\s+)?(?:volume|sound|audio))?\s*$", re.I), "unmute_volume", lambda m: {}),
    (re.compile(r"^(?:turn\s+(?:it\s+|the\s+volume\s+)?)?(?:up|louder)\s*$", re.I), "set_volume", lambda m: {"level": 70}),
    (re.compile(r"^(?:turn\s+(?:it\s+|the\s+volume\s+)?)?(?:down|quieter)\s*$", re.I), "set_volume", lambda m: {"level": 30}),

    # ── Brightness ──
    (re.compile(r"^(?:set\s+)?brightness\s+(?:to\s+)?(\d{1,3})%?\s*$", re.I), "set_brightness", _level),
    (re.compile(r"^brightness\s+(?:up|max|full|high)\s*$", re.I), "set_brightness", lambda m: {"level": 100}),
    (re.compile(r"^brightness\s+(?:down|low|dim)\s*$", re.I), "set_brightness", lambda m: {"level": 20}),

    # ── Power ──
    (re.compile(r"^(?:go\s+to\s+)?sleep\s*$|^put\s+(?:the\s+)?(?:system|computer|mac)\s+to\s+sleep\s*$", re.I), "system_sleep", lambda m: {}),

    # ── Screenshot ──
    (re.compile(r"^(?:take\s+(?:a\s+)?)?screenshot\s*$|^screen\s?grab\s*$", re.I), "take_screenshot", lambda m: {}),

    # ── Windows ──
    (re.compile(r"^(?:list|show)\s+(?:all\s+)?(?:the\s+)?(?:open\s+)?windows\s*$", re.I), "list_windows", lambda m: {}),
    (re.compile(r"^(?:switch\s+to|focus(?:\s+on)?)\s+([\w .+-]{2,30}?)(?:\s+app)?\s*$", re.I), "focus_app", _app),

    # ── Music ──
    (re.compile(r"^play\s+(.{2,80}?)\s*$", re.I), "play_music", _music),

    # ── Files & folders (must precede open_app) ──
    (re.compile(r"^(?:create|make|new)\s+(?:a\s+)?folder\s+(?:named\s+|called\s+)?(.{1,80})$", re.I), "create_folder", _folder),
    (re.compile(r"^(?:create|make|new)\s+(?:a\s+)?file\s+(?:named\s+|called\s+)?(.{1,80})$", re.I), "create_file", _file),
    (re.compile(r"^open\s+(?:the\s+)?folder\s+(.{1,80})$", re.I), "open_folder", _folder),
    (re.compile(r"^open\s+(?:the\s+)?file\s+(.{1,80})$", re.I), "open_file", _file),

    # ── Websites (explicit domain or a known site name) ──
    (re.compile(
        r"^(?:open|opne|go\s+to|visit|navigate\s+to)\s+"
        r"((?:https?://)?(?:www\.)?[\w-]+\.[a-z]{2,}(?:/\S*)?"
        r"|youtube|facebook|instagram|github|google|twitter|reddit|netflix|amazon|gmail)"
        r"\s*$", re.I), "open_website", _url),

    # ── Applications: a short bare noun only. No trailing clauses. ──
    (re.compile(r"^(?:open|opne|launch|start)\s+(?:the\s+)?([\w .+-]{2,30}?)(?:\s+app)?\s*$", re.I), "open_app", _app),
]


def try_fast_route(user_text):
    """
    Attempt a deterministic shortcut.

    Returns {"text", "tool_calls", "fast_routed"} on a confident match,
    otherwise None so the model handles the turn.
    """
    text = (user_text or "").strip()
    if not text:
        return None

    # Questions and pleasantries are conversation. Always let the model answer.
    if _QUESTION.match(text) or _CONVERSATIONAL.match(text):
        return None

    # Never shortcut past a pending yes/no.
    from core.tool_executor import get_pending
    if get_pending():
        return None

    # Multi-clause requests are compound tasks — the agent loop handles those.
    if re.search(r"\b(?:and then|after that|then\s+\w+\s+(?:it|the|a)\b)", text, re.I):
        return None

    for pattern, tool_name, extract in FAST_ROUTES:
        match = pattern.match(text)
        if not match:
            continue
        try:
            args = extract(match)
        except Exception as e:
            print(f"  ⚡ Fast route arg error for {tool_name}: {e}")
            return None

        result = run_tool(tool_name, args)
        return {
            "text": result,
            "tool_calls": [{"name": tool_name, "args": args, "result": result}],
            "fast_routed": True,
        }

    return None
