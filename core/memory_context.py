"""
MARK — Working Memory

Previously, MARK only remembered something if the model explicitly chose to
call rag_recall — which meant it almost never did. This module makes recall
automatic: every turn, relevant memories are retrieved and injected into the
prompt, and salient facts the user states are captured without being asked.

Retrieval is deliberately cheap (a handful of short lines) so it costs very
little context, and silent — the user should experience it as MARK simply
knowing things.
"""

import re
import threading

# Things worth remembering without being told to.
_SALIENT = [
    re.compile(r"\bmy name is\s+(.{2,40})", re.I),
    re.compile(r"\bi(?:'m| am)\s+(?:a|an)\s+(.{3,60})", re.I),
    re.compile(r"\bi (?:like|love|prefer|enjoy)\s+(.{3,60})", re.I),
    re.compile(r"\bi (?:hate|dislike|can't stand)\s+(.{3,60})", re.I),
    re.compile(r"\bmy (?:favou?rite\s+\w+)\s+is\s+(.{2,60})", re.I),
    re.compile(r"\bi (?:work|study)\s+(?:at|on|for)\s+(.{3,60})", re.I),
    re.compile(r"\bi(?:'m| am) (?:working on|building)\s+(.{3,60})", re.I),
    re.compile(r"\bmy (?:birthday|address|email|phone|wifi)\b.{0,60}", re.I),
]

# Phrases where the user is explicitly asking us to store something. Those go
# through the tool path instead, so we do not double-store.
_EXPLICIT = re.compile(r"\b(remember|note that|don'?t forget|keep in mind|store this|save this)\b", re.I)

_lock = threading.Lock()
_last_injected = []


def recall_for(user_text, limit=4):
    """
    Return a short list of memory lines relevant to this turn.
    Never raises — memory is an enhancement, not a dependency.
    """
    global _last_injected
    if not user_text or len(user_text.strip()) < 3:
        return []

    try:
        from tools.rag_memory import rag_recall
        raw = rag_recall(user_text, n_results=limit)
    except Exception:
        return []

    if not raw or not isinstance(raw, str):
        return []
    low = raw.lower()
    if "don't have any memories" in low or "no memories" in low:
        return []

    lines = []
    for line in raw.split("\n")[1:]:
        line = line.strip()
        if not line:
            continue
        # Strip the "1. (87% match [personal] 2026-01-02)" decoration.
        cleaned = re.sub(r"^\d+\.\s*\([^)]*\)\s*", "", line).strip()
        if cleaned:
            lines.append(cleaned)
        if len(lines) >= limit:
            break

    with _lock:
        _last_injected = lines
    return lines


def as_prompt_block(user_text, limit=4):
    """Render recalled memories as a prompt fragment, or '' if there are none."""
    lines = recall_for(user_text, limit)
    if not lines:
        return ""
    body = "\n".join(f"- {ln}" for ln in lines)
    return (
        "\nTHINGS YOU ALREADY KNOW ABOUT HIM (use naturally, never recite this list):\n"
        f"{body}\n"
    )


def capture(user_text):
    """
    Store salient personal facts stated in passing.

    Returns the stored text, or None. Explicit "remember X" requests are left
    alone so the model's rag_remember call stays the single source of truth for
    those.
    """
    if not user_text or _EXPLICIT.search(user_text):
        return None

    for pattern in _SALIENT:
        match = pattern.search(user_text)
        if not match:
            continue
        fact = match.group(0).strip().rstrip(".,!?")
        if len(fact) < 6:
            continue
        try:
            from tools.rag_memory import rag_remember
            rag_remember(text=fact, category="personal", source="conversation")
            print(f"  🧠 Noted: {fact[:70]}")
            return fact
        except Exception:
            return None
    return None


def last_injected():
    with _lock:
        return list(_last_injected)
