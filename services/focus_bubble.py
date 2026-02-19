"""
MARK — Focus Bubble (Distraction Shield)
Background daemon that blocks distracting apps/sites for a set duration.
Emits HUD warnings to keep the user on track.
"""

import os
import subprocess
import threading
import time
import datetime


# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────

_focus_state = {
    "active": False,
    "end_time": None,
    "thread": None,
    "blocked_apps": [],
    "blocked_sites": [],
    "kills": 0,
    "start_time": None,
    "socketio": None,
}

# Default distracting apps (process names)
DEFAULT_BLOCKED_APPS = [
    "Twitter", "Discord", "Slack", "Telegram", "WhatsApp",
    "Instagram", "TikTok", "Reddit", "Facebook",
    "Messages", "FaceTime",
]

# Default distracting domains
DEFAULT_BLOCKED_SITES = [
    "twitter.com", "x.com",
    "reddit.com", "old.reddit.com",
    "youtube.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com", "fb.com",
    "discord.com",
    "twitch.tv",
    "netflix.com",
    "hulu.com",
]


def set_socketio(sio):
    """Set the socketio instance for HUD card emissions."""
    _focus_state["socketio"] = sio


def _emit_hud(title, content, icon="🛡️", duration=6):
    """Emit a HUD card if socketio is available."""
    sio = _focus_state.get("socketio")
    if sio:
        try:
            sio.emit("hud_card", {
                "title": title,
                "content": content,
                "icon": icon,
                "duration": duration,
            })
        except Exception:
            pass


def _kill_app(app_name):
    """Quit an app via AppleScript (graceful, no sudo needed)."""
    try:
        script = f'tell application "{app_name}" to quit'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=3
        )
        return True
    except Exception:
        return False


def _get_running_apps():
    """Get list of currently running application names."""
    try:
        script = 'tell application "System Events" to get name of every application process whose background only is false'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return [a.strip() for a in result.stdout.strip().split(",")]
    except Exception:
        pass
    return []


def _block_sites_applescript(sites):
    """Block sites by injecting a JS blocker page into Safari/Chrome (no sudo needed)."""
    # We'll use a simple approach: if the user tries to visit a blocked site,
    # close that tab. We check running browsers and close tabs with blocked URLs.
    for browser in ["Safari", "Google Chrome"]:
        for site in sites:
            try:
                if browser == "Safari":
                    script = f'''
                    tell application "Safari"
                        if (count of windows) > 0 then
                            repeat with t in tabs of window 1
                                if URL of t contains "{site}" then
                                    close t
                                end if
                            end repeat
                        end if
                    end tell
                    '''
                else:
                    script = f'''
                    tell application "Google Chrome"
                        if (count of windows) > 0 then
                            repeat with t in tabs of window 1
                                if URL of t contains "{site}" then
                                    close t
                                end if
                            end repeat
                        end if
                    end tell
                    '''
                subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, timeout=3
                )
            except Exception:
                pass


def _focus_daemon():
    """Background thread that enforces the focus bubble."""
    state = _focus_state
    check_interval = 10  # seconds
    hud_interval = 900   # 15 minutes for periodic reminders
    last_hud_time = time.time()

    while state["active"] and time.time() < state["end_time"]:
        remaining = state["end_time"] - time.time()
        remaining_min = int(remaining / 60)

        # Kill distracting apps
        running = _get_running_apps()
        for app in state["blocked_apps"]:
            # Case-insensitive match
            for running_app in running:
                if app.lower() in running_app.lower():
                    if _kill_app(running_app):
                        state["kills"] += 1
                        _emit_hud(
                            "FOCUS SHIELD",
                            f"<strong>{running_app}</strong> was blocked.<br>Stay focused, sir. {remaining_min} min remaining.",
                            "🚫", 5
                        )
                    break

        # Block sites in browsers
        _block_sites_applescript(state["blocked_sites"])

        # Periodic motivation HUD
        elapsed = time.time() - last_hud_time
        if elapsed >= hud_interval and remaining_min > 5:
            last_hud_time = time.time()
            _emit_hud(
                "FOCUS ACTIVE",
                f"<strong>{remaining_min} minutes</strong> remaining.<br>You're doing great, sir. Stay locked in. 💪",
                "🛡️", 6
            )

        time.sleep(check_interval)

    # Session ended
    if state["active"]:
        _end_session()


def _end_session():
    """Clean up and report on the focus session."""
    state = _focus_state
    state["active"] = False

    duration = time.time() - state["start_time"] if state["start_time"] else 0
    duration_min = int(duration / 60)

    _emit_hud(
        "FOCUS COMPLETE",
        f"<strong>{duration_min} minutes</strong> of deep work.<br>Distractions blocked: {state['kills']}<br>Excellent discipline, sir. 🎯",
        "✅", 10
    )


def start_focus(duration_minutes="60", blocked_apps="", blocked_sites=""):
    """
    Start a focus session that blocks distracting apps and websites.
    
    Args:
        duration_minutes: How long to stay focused (default: 60)
        blocked_apps: Comma-separated app names to block (default: social media apps)
        blocked_sites: Comma-separated domains to block (default: social media sites)
    
    Returns:
        Confirmation message
    """
    state = _focus_state

    if state["active"]:
        remaining = state["end_time"] - time.time()
        remaining_min = int(remaining / 60)
        return f"🛡️ Focus Bubble is already active! {remaining_min} minutes remaining. Use stop_focus to end early."

    # Parse duration
    try:
        duration = int(str(duration_minutes).strip())
    except (ValueError, TypeError):
        duration = 60

    # Parse apps
    if blocked_apps and blocked_apps.strip():
        apps = [a.strip() for a in blocked_apps.split(",") if a.strip()]
    else:
        apps = DEFAULT_BLOCKED_APPS[:]

    # Parse sites
    if blocked_sites and blocked_sites.strip():
        sites = [s.strip() for s in blocked_sites.split(",") if s.strip()]
    else:
        sites = DEFAULT_BLOCKED_SITES[:]

    # Set state
    state["active"] = True
    state["start_time"] = time.time()
    state["end_time"] = time.time() + (duration * 60)
    state["blocked_apps"] = apps
    state["blocked_sites"] = sites
    state["kills"] = 0

    # Start daemon thread
    thread = threading.Thread(target=_focus_daemon, daemon=True, name="FocusBubble")
    thread.start()
    state["thread"] = thread

    end_time_str = datetime.datetime.fromtimestamp(state["end_time"]).strftime("%I:%M %p")

    # Emit startup HUD
    _emit_hud(
        "FOCUS BUBBLE ACTIVATED",
        f"<strong>{duration} minutes</strong> of deep work begins now.<br>Ends at {end_time_str}.<br>Blocking {len(apps)} apps and {len(sites)} sites.",
        "🛡️", 8
    )

    return (
        f"🛡️ **Focus Bubble Activated**\n\n"
        f"⏱️ Duration: {duration} minutes (until {end_time_str})\n"
        f"📵 Blocking {len(apps)} apps: {', '.join(apps[:5])}{'...' if len(apps) > 5 else ''}\n"
        f"🌐 Blocking {len(sites)} sites: {', '.join(sites[:5])}{'...' if len(sites) > 5 else ''}\n\n"
        f"Stay focused, sir. I'll guard your attention."
    )


def stop_focus():
    """
    End the current focus session early.
    
    Returns:
        Session summary
    """
    state = _focus_state

    if not state["active"]:
        return "🛡️ No active focus session. Use start_focus to begin one."

    duration = time.time() - state["start_time"]
    duration_min = int(duration / 60)

    state["active"] = False
    state["end_time"] = 0  # Signal daemon to stop

    return (
        f"🛡️ **Focus Bubble Deactivated**\n\n"
        f"⏱️ Duration: {duration_min} minutes\n"
        f"🚫 Distractions blocked: {state['kills']}\n\n"
        f"Good session, sir."
    )
