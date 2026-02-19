"""
MARK — Reminder Manager
Context-aware temporal alerts with persistent storage and background scheduling.
Fires macOS native notifications when reminders are due.
Stores reminders in reminders.json alongside the application.
"""

import json
import os
import time
import datetime
import threading
import subprocess
import re

REMINDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")

_scheduler_running = False
_scheduler_thread = None
_socketio_ref = None  # Will be set by app.py to emit events to the client


def _load_reminders() -> list:
    """Load all reminders from file."""
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_reminders(reminders: list):
    """Persist reminders to file."""
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, indent=2, ensure_ascii=False)


def _send_macos_notification(title: str, message: str):
    """Send a native macOS notification via osascript."""
    safe_title = title.replace('"', '\\"').replace("'", "'")
    safe_message = message.replace('"', '\\"').replace("'", "'")
    script = f'display notification "{safe_message}" with title "{safe_title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception as e:
        print(f"  ✗ Notification error: {e}")


def _say_reminder(message: str):
    """Use macOS TTS to speak the reminder aloud."""
    safe = message.replace('"', '\\"')
    try:
        subprocess.run(["say", "-v", "Samantha", safe], capture_output=True, timeout=15)
    except Exception:
        pass


def _parse_time(time_str: str) -> datetime.datetime | None:
    """
    Parse a human-readable time string into a datetime.
    Supports:
      - "in X minutes/hours/seconds"
      - "at HH:MM" or "at H:MM PM"
      - "tomorrow at HH:MM"
      - "in X hours and Y minutes"
      - Absolute: "2026-02-18 19:30"
    """
    now = datetime.datetime.now()
    text = time_str.strip().lower()

    # ── "in X minutes/hours/seconds" ──
    delta_match = re.match(
        r"in\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)(?:\s+(?:and\s+)?(\d+)\s*(minutes?|mins?|m|seconds?|secs?|s))?",
        text
    )
    if delta_match:
        amount1 = int(delta_match.group(1))
        unit1 = delta_match.group(2)
        delta = datetime.timedelta()

        if unit1.startswith("s"):
            delta += datetime.timedelta(seconds=amount1)
        elif unit1.startswith("m"):
            delta += datetime.timedelta(minutes=amount1)
        elif unit1.startswith("h"):
            delta += datetime.timedelta(hours=amount1)

        if delta_match.group(3) and delta_match.group(4):
            amount2 = int(delta_match.group(3))
            unit2 = delta_match.group(4)
            if unit2.startswith("s"):
                delta += datetime.timedelta(seconds=amount2)
            elif unit2.startswith("m"):
                delta += datetime.timedelta(minutes=amount2)

        return now + delta

    # ── "at HH:MM" or "at H:MM AM/PM" ──
    at_match = re.match(r"(?:at\s+)?(\d{1,2}):(\d{2})\s*(am|pm)?", text)
    if at_match:
        hour = int(at_match.group(1))
        minute = int(at_match.group(2))
        ampm = at_match.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)  # Next day
        return target

    # ── "tomorrow at HH:MM" ──
    tmr_match = re.match(r"tomorrow\s+(?:at\s+)?(\d{1,2}):(\d{2})\s*(am|pm)?", text)
    if tmr_match:
        hour = int(tmr_match.group(1))
        minute = int(tmr_match.group(2))
        ampm = tmr_match.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        target = (now + datetime.timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target

    # ── Absolute datetime "YYYY-MM-DD HH:MM" ──
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        pass

    # ── Just a number (assume minutes) ──
    just_num = re.match(r"^(\d+)$", text)
    if just_num:
        return now + datetime.timedelta(minutes=int(just_num.group(1)))

    return None


def set_reminder(message: str, time_str: str) -> str:
    """
    Set a reminder with a message and time.
    Time can be relative ("in 10 minutes") or absolute ("at 3:30 PM").
    """
    if not message or not time_str:
        return "Please provide both a reminder message and a time."

    trigger_time = _parse_time(time_str)
    if not trigger_time:
        return f"I couldn't understand the time '{time_str}'. Try 'in 10 minutes', 'at 3:30 PM', or 'tomorrow at 9:00'."

    reminder = {
        "id": int(time.time() * 1000),
        "message": message.strip(),
        "trigger_at": trigger_time.isoformat(),
        "created_at": datetime.datetime.now().isoformat(),
        "fired": False
    }

    reminders = _load_reminders()
    reminders.append(reminder)
    _save_reminders(reminders)

    # Format the time nicely for confirmation
    time_diff = trigger_time - datetime.datetime.now()
    if time_diff.total_seconds() < 60:
        eta = f"{int(time_diff.total_seconds())} seconds"
    elif time_diff.total_seconds() < 3600:
        eta = f"{int(time_diff.total_seconds() / 60)} minutes"
    elif time_diff.total_seconds() < 86400:
        hours = int(time_diff.total_seconds() / 3600)
        mins = int((time_diff.total_seconds() % 3600) / 60)
        eta = f"{hours}h {mins}m" if mins else f"{hours} hours"
    else:
        eta = trigger_time.strftime("%b %d at %I:%M %p")

    formatted_time = trigger_time.strftime("%I:%M %p")

    return f"Reminder set for {formatted_time} ({eta} from now): \"{message}\""


def list_reminders() -> str:
    """List all active (unfired) reminders."""
    reminders = _load_reminders()
    active = [r for r in reminders if not r.get("fired", False)]

    if not active:
        return "No active reminders, sir."

    lines = [f"You have {len(active)} active reminder(s):"]
    for r in sorted(active, key=lambda x: x["trigger_at"]):
        trigger = datetime.datetime.fromisoformat(r["trigger_at"])
        time_str = trigger.strftime("%I:%M %p, %b %d")
        lines.append(f"• {time_str} — {r['message']}")

    return "\n".join(lines)


def delete_reminder(reminder_id: str) -> str:
    """Delete a reminder by its ID or by matching message text."""
    reminders = _load_reminders()
    original_count = len(reminders)

    # Try matching by ID
    try:
        rid = int(reminder_id)
        reminders = [r for r in reminders if r.get("id") != rid]
    except (ValueError, TypeError):
        # Try matching by message text
        query = reminder_id.strip().lower()
        reminders = [r for r in reminders if query not in r.get("message", "").lower()]

    if len(reminders) == original_count:
        return "No matching reminder found to delete, sir."

    _save_reminders(reminders)
    return "Reminder deleted, sir."


def clear_reminders() -> str:
    """Clear all reminders."""
    _save_reminders([])
    return "All reminders cleared, sir."


# ─────────────────────────────────────────────
# BACKGROUND SCHEDULER
# ─────────────────────────────────────────────

def _check_reminders():
    """Background loop: checks for due reminders every 15 seconds."""
    global _scheduler_running

    while _scheduler_running:
        try:
            now = datetime.datetime.now()
            reminders = _load_reminders()
            changed = False

            for r in reminders:
                if r.get("fired", False):
                    continue

                trigger = datetime.datetime.fromisoformat(r["trigger_at"])
                if now >= trigger:
                    r["fired"] = True
                    changed = True

                    msg = r["message"]
                    print(f"  🔔 Reminder fired: {msg}")

                    # macOS notification
                    _send_macos_notification("🔔 M.A.R.K. Reminder", msg)

                    # Speak it
                    _say_reminder(f"Reminder, sir. {msg}")

                    # Notify the client via WebSocket
                    if _socketio_ref:
                        try:
                            _socketio_ref.emit("reminder_fired", {
                                "message": msg,
                                "time": trigger.strftime("%I:%M %p")
                            })
                        except Exception:
                            pass

            if changed:
                # Clean up fired reminders older than 24 hours
                cutoff = now - datetime.timedelta(hours=24)
                reminders = [
                    r for r in reminders
                    if not r.get("fired") or datetime.datetime.fromisoformat(r["trigger_at"]) > cutoff
                ]
                _save_reminders(reminders)

        except Exception as e:
            print(f"  ✗ Reminder scheduler error: {e}")

        time.sleep(15)


def start_scheduler(socketio=None):
    """Start the background reminder scheduler."""
    global _scheduler_running, _scheduler_thread, _socketio_ref

    if _scheduler_running:
        return

    _socketio_ref = socketio
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_check_reminders, daemon=True, name="ReminderScheduler")
    _scheduler_thread.start()
    print("  ✓ Reminder scheduler started")


def stop_scheduler():
    """Stop the background reminder scheduler."""
    global _scheduler_running
    _scheduler_running = False
