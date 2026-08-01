"""
MARK — Permission & Audit Layer

Every tool call passes through here before it touches the machine.

Tiers
  SAFE      — read-only or trivially reversible. Runs immediately.
  MUTATING  — writes files, moves things, controls apps. Runs, but is
              recorded in the undo log so it can be reversed.
  SENSITIVE — shell, code execution, messaging, power. Requires an
              approved confirmation unless the user pre-authorised it.

A 4B model hallucinating a tool call must never be able to wipe a disk, so the
decision is made from a static table here — never from the model's own opinion
about how dangerous its request is.
"""

import os
import json
import time
import shutil
import datetime
import threading

SAFE = "safe"
MUTATING = "mutating"
SENSITIVE = "sensitive"

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AUDIT_DIR = os.path.join(_PROJECT_DIR, "audit")
_UNDO_LOG = os.path.join(_AUDIT_DIR, "undo_log.json")
_TRASH_DIR = os.path.join(_AUDIT_DIR, "trash")
_AUDIT_LOG = os.path.join(_AUDIT_DIR, "tool_calls.jsonl")

os.makedirs(_AUDIT_DIR, exist_ok=True)
os.makedirs(_TRASH_DIR, exist_ok=True)

_lock = threading.Lock()


# ─────────────────────────────────────────────
# TIER TABLE
# ─────────────────────────────────────────────

TIERS = {
    # ── SENSITIVE: can execute arbitrary code, spend money, message humans,
    #    or take the machine down. Always confirmed.
    "run_terminal": SENSITIVE,
    "run_code": SENSITIVE,
    "system_shutdown": SENSITIVE,
    "system_restart": SENSITIVE,
    "send_whatsapp": SENSITIVE,
    "browser_do": SENSITIVE,
    "scrape_data": SENSITIVE,
    "pull_ollama_model": SENSITIVE,
    "mcp_add_server": SENSITIVE,
    "mcp_remove_server": SENSITIVE,

    # ── MUTATING: changes state on disk or in apps, reversible via undo log.
    "write_file": MUTATING,
    "edit_file": MUTATING,
    "create_file": MUTATING,
    "create_folder": MUTATING,
    "take_notes": MUTATING,
    "clean_desktop": MUTATING,
    "organize_downloads": MUTATING,
    "edit_image": MUTATING,
    "write_code": MUTATING,
    "build_website": MUTATING,
    "research_topic": MUTATING,
    "rag_forget": MUTATING,
    "delete_memory": MUTATING,
    "save_memory": MUTATING,
    "rag_remember": MUTATING,
    "set_reminder": MUTATING,
    "delete_reminder": MUTATING,
    "clear_reminders": MUTATING,
    "create_routine": MUTATING,
    "run_routine": MUTATING,
    "start_focus": MUTATING,
    "stop_focus": MUTATING,
    "system_sleep": MUTATING,
    "add_iot_device": MUTATING,
    "control_iot_device": MUTATING,
    "set_ollama_model": MUTATING,
    # Direct machine input control — reversible but should be logged.
    "click_at": MUTATING,
    "click_text": MUTATING,
    "type_text": MUTATING,
    "drag_to": MUTATING,
    "vision_click": MUTATING,
    "vision_type": MUTATING,
    "vision_interact": MUTATING,
    "paste_from_history": MUTATING,
}

# Everything not listed is SAFE (reads, queries, window focus, volume, etc).


def get_tier(tool_name):
    """Return the permission tier for a tool."""
    return TIERS.get(tool_name, SAFE)


# ─────────────────────────────────────────────
# PRE-AUTHORISATION
# ─────────────────────────────────────────────
# The user can grant a standing approval ("yes, and stop asking") either for a
# single tool or for a whole session. Auto-approve is opt-in and off by default.

_session_grants = set()
_auto_approve_all = False


def grant(tool_name):
    """Pre-authorise a tool for the rest of this session."""
    _session_grants.add(tool_name)
    return f"Standing approval granted for {tool_name} this session."


def revoke(tool_name=None):
    """Revoke a standing approval, or all of them."""
    global _auto_approve_all
    if tool_name:
        _session_grants.discard(tool_name)
        return f"Approval revoked for {tool_name}."
    _session_grants.clear()
    _auto_approve_all = False
    return "All standing approvals revoked."


def set_auto_approve(enabled):
    """Turn blanket auto-approval on or off (used by trusted headless runs)."""
    global _auto_approve_all
    _auto_approve_all = bool(enabled)
    return _auto_approve_all


def is_auto_approve():
    return _auto_approve_all


def needs_confirmation(tool_name):
    """True if this call must be confirmed by the user before running."""
    if get_tier(tool_name) != SENSITIVE:
        return False
    if _auto_approve_all or tool_name in _session_grants:
        return False
    return True


def describe(tool_name, args):
    """Human-readable one-liner describing what is about to happen."""
    tier = get_tier(tool_name)
    detail = ""
    if tool_name == "run_terminal":
        detail = args.get("command", "")
    elif tool_name == "run_code":
        detail = f"{args.get('language', 'code')}: {str(args.get('code', ''))[:120]}"
    elif tool_name in ("write_file", "edit_file", "create_file", "read_file"):
        detail = args.get("file_path", "")
    elif tool_name == "send_whatsapp":
        detail = f"to {args.get('contact', '?')}: {args.get('message', '')[:60]}"
    else:
        detail = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(args.items())[:3])
    return f"[{tier}] {tool_name}({detail})"


# ─────────────────────────────────────────────
# UNDO LOG
# ─────────────────────────────────────────────

def _load_undo():
    if not os.path.exists(_UNDO_LOG):
        return []
    try:
        with open(_UNDO_LOG) as f:
            return json.load(f)
    except Exception:
        return []


def _save_undo(entries):
    tmp = _UNDO_LOG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries[-200:], f, indent=2)
    os.replace(tmp, _UNDO_LOG)


def snapshot_before(tool_name, args):
    """
    Back up whatever a mutating tool is about to overwrite, so it can be undone.
    Returns an undo record (or None if there is nothing to preserve).
    """
    path = args.get("file_path") or args.get("output_path")
    if not path:
        return None
    path = os.path.expanduser(str(path))

    record = {
        "id": f"{int(time.time() * 1000)}",
        "tool": tool_name,
        "path": path,
        "when": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    if os.path.isfile(path):
        backup = os.path.join(_TRASH_DIR, f"{record['id']}_{os.path.basename(path)}")
        try:
            shutil.copy2(path, backup)
            record["action"] = "restore"
            record["backup"] = backup
        except Exception:
            return None
    else:
        # File does not exist yet — undoing means deleting what we create.
        record["action"] = "delete"

    return record


def commit_undo(record):
    """Persist an undo record after the tool succeeded."""
    if not record:
        return
    with _lock:
        entries = _load_undo()
        entries.append(record)
        _save_undo(entries)


def list_undo(count=10):
    """Show the most recent reversible actions."""
    entries = _load_undo()
    if not entries:
        return "Nothing to undo — no reversible actions recorded yet."
    lines = ["Recent reversible actions (newest first):"]
    for i, e in enumerate(reversed(entries[-int(count):]), 1):
        lines.append(f"  {i}. [{e['when']}] {e['tool']} → {e['path']}")
    return "\n".join(lines)


def undo_last():
    """Reverse the most recent mutating file action."""
    with _lock:
        entries = _load_undo()
        if not entries:
            return "There is nothing to undo, sir."
        record = entries.pop()
        _save_undo(entries)

    path = record["path"]
    try:
        if record["action"] == "restore":
            shutil.copy2(record["backup"], path)
            return f"Restored the previous version of {os.path.basename(path)}, sir."
        if record["action"] == "delete":
            if os.path.isfile(path):
                os.remove(path)
                return f"Removed {os.path.basename(path)} — back to how it was, sir."
            return f"{os.path.basename(path)} was already gone, sir."
    except Exception as e:
        return f"Could not undo that: {e}"
    return "Nothing to undo."


# ─────────────────────────────────────────────
# AUDIT TRAIL
# ─────────────────────────────────────────────

def audit(tool_name, args, result, tier, elapsed_ms, blocked=False):
    """Append one line to the audit trail. Never raises."""
    try:
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "tool": tool_name,
            "tier": tier,
            "args": {k: str(v)[:200] for k, v in (args or {}).items()},
            "blocked": blocked,
            "ms": elapsed_ms,
            "result": str(result)[:300],
        }
        with open(_AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def recent_audit(count=20):
    """Read back the most recent tool calls."""
    if not os.path.exists(_AUDIT_LOG):
        return "No tool calls recorded yet."
    try:
        with open(_AUDIT_LOG) as f:
            lines = f.readlines()[-int(count):]
        out = ["Recent tool calls:"]
        for ln in lines:
            e = json.loads(ln)
            flag = " BLOCKED" if e.get("blocked") else ""
            out.append(f"  [{e['ts']}]{flag} {e['tool']} ({e['ms']}ms) → {e['result'][:80]}")
        return "\n".join(out)
    except Exception as e:
        return f"Could not read audit log: {e}"
