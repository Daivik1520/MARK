"""
MARK — Tool Executor

The single choke point through which every tool call must pass, whether it came
from the chat path, the agent loop, the fast router or an MCP server.

Responsibilities:
  * enforce the permission tier (confirm sensitive actions before running)
  * snapshot state so mutating file actions can be undone
  * time, audit and truncate every result
  * never let a tool exception reach the caller as a crash

Keeping this separate from system_controller means the dispatch table stays a
plain name->function map, and the policy lives in exactly one place.
"""

import time
import threading

from core import permissions
from core.permissions import SAFE, MUTATING, SENSITIVE

# A sensitive call that is awaiting a yes/no from the user.
_pending = None
_pending_lock = threading.Lock()

_AFFIRMATIVE = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "do it", "go ahead",
    "confirm", "confirmed", "please do", "affirmative", "proceed", "run it",
    "send it", "go", "y", "do that", "yes please", "go for it",
}
_NEGATIVE = {
    "no", "nope", "nah", "cancel", "stop", "don't", "dont", "abort",
    "never mind", "nevermind", "forget it", "n", "no thanks",
}


def get_pending():
    """Return the call awaiting confirmation, if any."""
    with _pending_lock:
        return dict(_pending) if _pending else None


def clear_pending():
    global _pending
    with _pending_lock:
        _pending = None


def _set_pending(tool_name, args):
    global _pending
    with _pending_lock:
        _pending = {"tool": tool_name, "args": args, "at": time.time()}


def classify_confirmation(text):
    """
    Interpret a short reply as approval / refusal of a pending action.
    Returns "yes", "no", or None if it is not a confirmation at all.
    """
    t = (text or "").strip().lower().rstrip(".!")
    if not t:
        return None
    if t in _AFFIRMATIVE:
        return "yes"
    if t in _NEGATIVE:
        return "no"
    # Allow a little padding: "yes, do it sir"
    words = set(t.replace(",", " ").split())
    if words & {"yes", "yeah", "yep", "confirm", "proceed", "go"}:
        return "yes"
    if words & {"no", "cancel", "stop", "abort", "nope"}:
        return "no"
    return None


def resolve_pending(decision):
    """
    Run or discard the pending sensitive call.
    Returns (text, tool_calls) ready to hand back to the user.
    """
    pending = get_pending()
    clear_pending()
    if not pending:
        return "There was nothing waiting for confirmation, sir.", None

    if decision != "yes":
        permissions.audit(pending["tool"], pending["args"], "declined by user",
                          SENSITIVE, 0, blocked=True)
        return "Cancelled, sir. I haven't touched anything.", None

    result = run_tool(pending["tool"], pending["args"], confirmed=True)
    return result, [{"name": pending["tool"], "result": result}]


def run_tool(tool_name, args, confirmed=False, allow_sensitive=None):
    """
    Execute a tool under policy.

    confirmed        — this call has already been approved by the user.
    allow_sensitive  — when True, skip the confirmation prompt entirely (used by
                       the agent loop once the whole plan has been approved).

    Returns the tool's result string. If confirmation is required, returns a
    question and parks the call in `_pending`.
    """
    from core.system_controller import execute_tool

    args = args or {}
    tier = permissions.get_tier(tool_name)

    # ── Gate ──
    if tier == SENSITIVE and not confirmed and not allow_sensitive:
        if permissions.needs_confirmation(tool_name):
            _set_pending(tool_name, args)
            summary = permissions.describe(tool_name, args)
            permissions.audit(tool_name, args, "awaiting confirmation", tier, 0, blocked=True)
            return (f"That one needs your go-ahead, sir — {summary}. "
                    f"Say yes to run it, or no to cancel.")

    # ── Snapshot for undo ──
    undo_record = None
    if tier == MUTATING:
        try:
            undo_record = permissions.snapshot_before(tool_name, args)
        except Exception:
            undo_record = None

    # ── Execute ──
    start = time.time()
    try:
        result = execute_tool(tool_name, args)
    except Exception as e:
        result = f"Error executing {tool_name}: {type(e).__name__}: {e}"
    elapsed_ms = int((time.time() - start) * 1000)

    result_str = str(result) if result is not None else "Done."

    # Only record an undo entry if the action actually appears to have worked.
    if undo_record and not result_str.lower().startswith(("error", "could not", "failed")):
        permissions.commit_undo(undo_record)

    permissions.audit(tool_name, args, result_str, tier, elapsed_ms)
    return result_str


# ─────────────────────────────────────────────
# META TOOLS
# ─────────────────────────────────────────────
# Exposed to the model so the user can talk to the safety layer directly.

def undo_last_action():
    """Reverse the most recent reversible action."""
    return permissions.undo_last()


def list_recent_actions(count="10"):
    """Show what MARK has done recently."""
    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 10
    return permissions.recent_audit(count)


def list_undoable():
    """Show which actions can still be undone."""
    return permissions.list_undo()


def always_allow(tool_name=""):
    """Grant a standing approval for a sensitive tool for this session."""
    if not tool_name:
        return "Which tool should I stop asking about, sir?"
    return permissions.grant(tool_name)
