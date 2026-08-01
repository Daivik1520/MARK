"""
MARK — Proactive Triggers

Ambient signals that let MARK speak first instead of only answering.

Everything here is local and cheap: no polling of remote services, no model
calls on the timer path. A trigger fires at most once per cooldown window, so
MARK stays useful rather than becoming a nagging notification source.
"""

import os
import time
import threading
import datetime

_sio = None
_thread = None
_stop = threading.Event()

# Trigger name -> last fire time.
_last_fired = {}

CHECK_INTERVAL = 60          # seconds between sweeps
DEFAULT_COOLDOWN = 3600      # do not repeat the same nudge within an hour


def _cooled(name, cooldown=DEFAULT_COOLDOWN):
    now = time.time()
    if now - _last_fired.get(name, 0) < cooldown:
        return False
    _last_fired[name] = now
    return True


def _notify(message, severity="info", speak=False):
    if not _sio:
        return
    try:
        _sio.emit("proactive_alert", {"message": message, "severity": severity})
        if speak:
            _sio.emit("proactive_speak", {"text": message})
    except Exception:
        pass


# ─────────────────────────────────────────────
# TRIGGERS
# ─────────────────────────────────────────────

def _check_battery():
    try:
        import psutil
        battery = psutil.sensors_battery()
        if not battery or battery.power_plugged:
            return
        if battery.percent <= 10 and _cooled("battery_critical", 900):
            _notify(f"Battery's at {int(battery.percent)} percent, sir. "
                    "You'll want a charger soon.", "warning", speak=True)
        elif battery.percent <= 20 and _cooled("battery_low"):
            _notify(f"Heads up — battery is down to {int(battery.percent)} percent.", "warning")
    except Exception:
        pass


def _check_disk():
    try:
        import psutil
        usage = psutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 5 and _cooled("disk_critical", 7200):
            _notify(f"Only {free_gb:.1f} gigabytes of disk left, sir. "
                    "Want me to clean up Downloads?", "warning", speak=True)
        elif usage.percent > 90 and _cooled("disk_low", 21600):
            _notify(f"Disk is {usage.percent:.0f} percent full.", "info")
    except Exception:
        pass


def _check_memory_pressure():
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 92 and _cooled("memory_pressure", 1800):
            top = []
            for proc in sorted(psutil.process_iter(["name", "memory_percent"]),
                               key=lambda p: p.info.get("memory_percent") or 0,
                               reverse=True)[:2]:
                name = proc.info.get("name")
                if name:
                    top.append(name)
            hint = f" {' and '.join(top)} are the biggest users." if top else ""
            _notify(f"Memory is at {mem.percent:.0f} percent.{hint}", "warning")
    except Exception:
        pass


def _check_long_session():
    """Nudge after a long uninterrupted stretch at the machine."""
    try:
        import subprocess
        output = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5
        ).stdout
        for line in output.split("\n"):
            if "HIDIdleTime" in line:
                idle_ns = int(line.split("=")[-1].strip())
                idle_minutes = idle_ns / 1e9 / 60
                # Active right now, and it is late.
                if idle_minutes < 2:
                    hour = datetime.datetime.now().hour
                    if hour >= 1 and hour < 5 and _cooled("late_night", 14400):
                        _notify("It's past one in the morning, sir. "
                                "Might be worth calling it a night.", "info", speak=True)
                break
    except Exception:
        pass


def _check_downloads_clutter():
    try:
        downloads = os.path.expanduser("~/Downloads")
        if not os.path.isdir(downloads):
            return
        count = sum(1 for name in os.listdir(downloads) if not name.startswith("."))
        if count > 120 and _cooled("downloads_clutter", 86400):
            _notify(f"Your Downloads folder has {count} items in it. "
                    "Say the word and I'll organise it.", "info")
    except Exception:
        pass


TRIGGERS = [
    _check_battery,
    _check_disk,
    _check_memory_pressure,
    _check_long_session,
    _check_downloads_clutter,
]


# ─────────────────────────────────────────────
# LOOP
# ─────────────────────────────────────────────

def _loop():
    # Let the machine settle before the first sweep.
    _stop.wait(45)
    while not _stop.is_set():
        for check in TRIGGERS:
            if _stop.is_set():
                break
            try:
                check()
            except Exception:
                pass
        _stop.wait(CHECK_INTERVAL)


def start_triggers(sio_instance=None):
    """Begin the ambient trigger sweep."""
    global _sio, _thread
    _sio = sio_instance
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="proactive-triggers")
    _thread.start()
    print(f"  🔔 Proactive triggers active ({len(TRIGGERS)} signals)")


def stop_triggers():
    _stop.set()
