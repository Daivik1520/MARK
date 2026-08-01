"""
MARK — Tool Router (context budget control)

MARK has 106 tools. Serialising all of them costs ~3,450 tokens, which used to
blow the whole context window on every single turn. This module picks the
handful of tools that are actually plausible for the current request, so a
typical prompt carries ~350 tokens of tool schema instead.

The scorer is purely lexical: deterministic, instant, no network, no model
download, and easy to assert on in tests. Recall is protected three ways:
  1. an always-present core set of everyday tools,
  2. a curated trigger-word map for intents whose wording does not overlap
     with the tool name ("tidy up my desktop" -> clean_desktop),
  3. a generous top-k, since 14 tools still only costs ~450 tokens.
"""

import re
from core.tool_schemas import TOOLS, TOOLS_BY_NAME

# Tools that stay in the prompt no matter what the user said. These are the
# ones a general assistant reaches for constantly, plus the escape hatches.
CORE_TOOLS = [
    "open_app",
    "open_website",
    "web_search",
    "get_context",
    "rag_remember",
    "rag_recall",
    "run_terminal",
    "get_system_stats",
]

# Words that should pull in a tool even though they do not appear in its name
# or description. Keys are tool names, values are trigger phrases.
TRIGGERS = {
    "clean_desktop":       ["tidy", "messy", "clutter", "organize desktop", "clean up desktop"],
    "organize_downloads":  ["tidy downloads", "messy downloads", "clean up downloads"],
    "set_volume":          ["loud", "quiet", "louder", "quieter", "sound level", "turn it up", "turn it down"],
    "mute_volume":         ["silence", "shut up", "be quiet"],
    "set_brightness":      ["dim", "brighter", "darker", "screen light"],
    "play_music":          ["song", "track", "album", "artist", "spotify", "youtube music", "put on"],
    "take_screenshot":     ["capture screen", "screen grab", "screenshot"],
    "analyze_screen":      ["look at my screen", "what do you see", "read this", "what is this",
                            "on my screen", "help me with this error", "summarize this"],
    "vision_click":        ["click the", "press the button", "tap the", "hit the button"],
    "vision_describe":     ["what is on screen", "describe the screen", "what can you see"],
    "click_text":          ["click on", "click the text"],
    "set_reminder":        ["remind", "alert me", "notify me", "don't let me forget", "wake me"],
    "list_reminders":      ["my reminders", "what reminders"],
    "rag_remember":        ["remember", "note that", "keep in mind", "don't forget", "store this",
                            "save this", "my name is", "i like", "i prefer", "my favourite", "my favorite"],
    "rag_recall":          ["what did i", "do you remember", "what is my", "what's my", "recall",
                            "did i tell you", "what do you know about me"],
    "rag_list":            ["what do you remember", "list memories", "show memories"],
    "start_focus":         ["focus session", "deep work", "stop distracting", "block distractions",
                            "pomodoro", "concentrate"],
    "stop_focus":          ["end focus", "stop focus", "unblock"],
    "run_routine":         ["mode", "routine", "good morning", "night mode", "coding mode"],
    "list_routines":       ["what modes", "what routines"],
    "tile_windows":        ["side by side", "split screen", "next to each other"],
    "dim_all_except":      ["hide everything else", "just show", "only show"],
    "move_window":         ["move window", "snap to", "left half", "right half"],
    "get_system_stats":    ["how is my mac", "cpu", "ram", "memory usage", "battery", "disk space",
                            "how fast", "slow", "temperature"],
    "search_files":        ["find a file", "where is the file", "locate file"],
    "search_content":      ["find the document about", "which file mentions", "search inside"],
    "research_topic":      ["research", "deep dive", "write a report", "look into"],
    "web_search_deep":     ["look it up properly", "search thoroughly"],
    "build_website":       ["make a website", "build a site", "landing page", "web page for"],
    "write_code":          ["write a script", "write a program", "code that", "make a program"],
    "run_code":            ["run this code", "execute this", "what does this code output"],
    "generate_password":   ["password", "passphrase", "pin code"],
    "track_number":        ["phone number", "whose number", "trace number"],
    "get_news_briefing":   ["briefing", "catch me up", "what's happening", "morning update"],
    "get_news":            ["news", "headlines"],
    "web_get_stock":       ["stock", "share price", "ticker", "market"],
    "send_whatsapp":       ["text", "message", "whatsapp", "tell him", "tell her", "send a msg"],
    "get_clipboard_history": ["clipboard", "what did i copy", "copied earlier"],
    "control_iot_device":  ["lamp", "light on", "light off", "smart home", "thermostat", "ac ", "fan"],
    "list_iot_devices":    ["my devices", "smart devices", "what devices"],
    "system_sleep":        ["go to sleep", "sleep now"],
    "system_shutdown":     ["shut down", "power off", "turn off the computer"],
    "undo_last_action":    ["undo", "revert", "take that back", "reverse that"],
    "edit_image":          ["resize image", "crop", "watermark", "rotate photo"],
    "read_file":           ["what is in the file", "show me the file", "open and read"],
    "write_file":          ["save to a file", "write to file", "create a file with"],
    "list_directory":      ["what is in the folder", "list the folder", "contents of"],
    "browser_do":          ["in the browser", "log into", "fill the form", "book a"],
    "scrape_data":         ["scrape", "extract data", "export to csv", "collect listings"],
}

_STOP = {
    "a", "an", "the", "to", "for", "of", "in", "on", "at", "is", "it", "and", "or",
    "my", "me", "i", "you", "your", "please", "can", "could", "would", "do", "does",
    "with", "that", "this", "be", "am", "are", "was", "were", "will", "just", "now",
    "hey", "mark", "sir", "up", "down", "out", "some", "get", "got", "make", "let",
}


def _tokens(text):
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in _STOP and len(w) > 1]


# Pre-build a searchable document per tool: name words + description words +
# parameter names. Built once at import.
def _build_index():
    index = {}
    for tool in TOOLS:
        fn = tool["function"]
        name = fn["name"]
        words = name.replace("_", " ")
        desc = fn.get("description", "")
        params = " ".join(fn.get("parameters", {}).get("properties", {}).keys()).replace("_", " ")
        doc = f"{words} {words} {desc} {params}"  # name weighted double
        index[name] = set(_tokens(doc))
    return index


_INDEX = _build_index()


def score_tools(user_text):
    """Score every tool against the user's text. Returns {tool_name: score}."""
    query = user_text.lower()
    q_tokens = set(_tokens(query))
    scores = {}

    for name, doc_tokens in _INDEX.items():
        score = 0.0

        # Exact tool name mentioned ("use run_terminal") — decisive.
        if name in query or name.replace("_", " ") in query:
            score += 12.0

        # Lexical overlap, normalised so verbose descriptions do not dominate.
        overlap = q_tokens & doc_tokens
        if overlap:
            score += 2.0 * len(overlap) / (1 + len(doc_tokens) ** 0.5)
            # Reward rare, specific matches (longer words carry more signal).
            score += 0.35 * sum(1 for w in overlap if len(w) > 5)

        # Curated trigger phrases.
        for phrase in TRIGGERS.get(name, []):
            if phrase in query:
                score += 6.0

        if score > 0:
            scores[name] = round(score, 3)

    return scores


def select_tools(user_text, max_tools=14, extra=()):
    """
    Return the tool schemas most relevant to `user_text`.

    Always includes CORE_TOOLS and anything named in `extra` (used by the agent
    loop to keep previously-used tools available across steps).
    """
    scores = score_tools(user_text)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    chosen = []
    seen = set()

    def add(name):
        if name in seen or name not in TOOLS_BY_NAME:
            return
        seen.add(name)
        chosen.append(TOOLS_BY_NAME[name])

    # Explicitly requested tools first, then best matches, then the core set.
    for name in extra:
        add(name)
    for name, _ in ranked:
        if len(chosen) >= max_tools:
            break
        add(name)
    for name in CORE_TOOLS:
        add(name)

    return chosen


def explain(user_text, top=8):
    """Debug helper — show why tools were picked. Used by the eval harness."""
    ranked = sorted(score_tools(user_text).items(), key=lambda kv: kv[1], reverse=True)[:top]
    return "\n".join(f"  {score:6.2f}  {name}" for name, score in ranked) or "  (no lexical matches)"
