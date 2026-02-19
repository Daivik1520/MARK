"""
MARK — Proactive Voice Monitor
Background daemon: monitors RAM, CPU, disk, and meeting schedules.
Emits SocketIO events → frontend plays TTS alert.
"""

import os
import threading
import time
import psutil
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── State to avoid duplicate alerts ──
_alert_cooldowns = {}          # {key: last_alert_timestamp}
ALERT_COOLDOWN_SEC = 300       # 5 min between same alert


def _can_alert(key):
    now = time.time()
    last = _alert_cooldowns.get(key, 0)
    if now - last > ALERT_COOLDOWN_SEC:
        _alert_cooldowns[key] = now
        return True
    return False


def _emit_alert(socketio, message, severity="warning"):
    """Emit a proactive alert — frontend will speak it via TTS."""
    socketio.emit("proactive_alert", {
        "message": message,
        "severity": severity   # info / warning / critical
    })


def _check_meeting_alerts(socketio):
    """
    Read MARK_MEETINGS env var: semicolon-separated list of HH:MM|Title|URL
    Example: 09:30|Standup|https://zoom.us/j/123;14:00|1-on-1|https://meet.google.com/abc
    """
    meetings_raw = os.getenv("MARK_MEETINGS", "")
    if not meetings_raw.strip():
        return

    now = datetime.now()
    for entry in meetings_raw.split(";"):
        parts = entry.strip().split("|")
        if len(parts) < 2:
            continue
        time_str, title = parts[0].strip(), parts[1].strip()
        url = parts[2].strip() if len(parts) > 2 else None

        try:
            meeting_time = datetime.strptime(time_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
        except ValueError:
            continue

        delta_minutes = (meeting_time - now).total_seconds() / 60

        # Alert at 10 minutes before
        if 9.0 <= delta_minutes <= 11.0:
            key = f"meeting_10_{title}"
            if _can_alert(key):
                msg = f"Sir, you have '{title}' in 10 minutes."
                if url:
                    msg += f" Would you like me to open the link?"
                _emit_alert(socketio, msg, "info")

        # Alert at 2 minutes before
        elif 1.5 <= delta_minutes <= 2.5:
            key = f"meeting_2_{title}"
            if _can_alert(key):
                msg = f"Sir, '{title}' starts in 2 minutes."
                _emit_alert(socketio, msg, "warning")


def _monitor_loop(socketio):
    """Main monitoring loop — runs every 30 seconds."""
    # Wait 10s after boot before first check
    time.sleep(10)

    # Sustained CPU tracking (need two readings to confirm)
    _high_cpu_since = None

    while True:
        try:
            # ── RAM Check ──
            ram = psutil.virtual_memory()
            ram_pct = ram.percent
            if ram_pct >= 90:
                if _can_alert("ram_critical"):
                    _emit_alert(socketio,
                        f"Sir, RAM usage is critically high at {ram_pct:.0f}%. "
                        "Should I close some applications?",
                        "critical")
            elif ram_pct >= 82:
                if _can_alert("ram_high"):
                    _emit_alert(socketio,
                        f"Heads-up, sir — RAM usage is at {ram_pct:.0f}%.",
                        "warning")

            # ── CPU Check (sustained) ──
            cpu_pct = psutil.cpu_percent(interval=1)
            if cpu_pct >= 90:
                if _high_cpu_since is None:
                    _high_cpu_since = time.time()
                elif time.time() - _high_cpu_since >= 30:
                    if _can_alert("cpu_high"):
                        _emit_alert(socketio,
                            f"Sir, your CPU has been running at {cpu_pct:.0f}% for over 30 seconds. "
                            "Something might be pegging a core.",
                            "warning")
                    _high_cpu_since = None  # reset after alerting
            else:
                _high_cpu_since = None

            # ── Disk Check ──
            disk = psutil.disk_usage("/")
            free_gb = disk.free / (1024 ** 3)
            if free_gb < 5.0:
                if _can_alert("disk_low"):
                    _emit_alert(socketio,
                        f"Sir, you have only {free_gb:.1f} GB of disk space remaining. "
                        "You may want to clean up soon.",
                        "warning")

            # ── Meeting Alerts ──
            _check_meeting_alerts(socketio)

        except Exception as e:
            print(f"[ProactiveMonitor] Error: {e}")

        time.sleep(30)


def start_proactive_monitor(socketio):
    """Start the proactive monitor as a background daemon thread."""
    t = threading.Thread(target=_monitor_loop, args=(socketio,), daemon=True)
    t.start()
    print("  ✓ Proactive monitor started")


def get_system_stats():
    """Return a human-readable system health snapshot (used as an AI tool)."""
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    disk = psutil.disk_usage("/")
    battery = psutil.sensors_battery()
    net = psutil.net_io_counters()

    lines = [
        f"🖥️  CPU Usage     : {cpu:.1f}%",
        f"🧠 RAM Usage     : {ram.percent:.1f}% ({ram.used // (1024**3):.1f} GB / {ram.total // (1024**3):.1f} GB)",
        f"💾 Disk Free     : {disk.free / (1024**3):.1f} GB of {disk.total / (1024**3):.1f} GB",
        f"📡 Net Sent      : {net.bytes_sent // (1024**2):.0f} MB | Received: {net.bytes_recv // (1024**2):.0f} MB",
    ]

    if battery:
        charge = battery.percent
        plugged = "plugged in" if battery.power_plugged else "on battery"
        lines.append(f"🔋 Battery        : {charge:.0f}% ({plugged})")

    # Top 3 CPU-consuming processes
    procs = sorted(psutil.process_iter(["pid", "name", "cpu_percent"]),
                   key=lambda p: p.info.get("cpu_percent") or 0, reverse=True)[:3]
    top_procs = ", ".join(
        f"{p.info['name']} ({float(p.info.get('cpu_percent') or 0):.1f}%)" for p in procs
    )
    lines.append(f"🔥 Top Processes : {top_procs}")

    return "\n".join(lines)
