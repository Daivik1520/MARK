"""
MARK — Aura Window Manager
Voice-controlled window tiling, focusing, and dimming via AppleScript.
"""

import subprocess
import json
import re


def _run_apple(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def _get_screen_size():
    """Return (width, height) of primary screen."""
    script = """
    tell application "Finder"
        set bd to bounds of window of desktop
        return {item 3 of bd, item 4 of bd}
    end tell
    """
    raw = _run_apple(script)
    parts = raw.split(", ")
    try:
        return int(parts[0]), int(parts[1])
    except Exception:
        return 1920, 1080


def _set_window_bounds(app_name: str, x: int, y: int, w: int, h: int) -> str:
    """Move and resize a window of the given application."""
    script = f"""
    tell application "{app_name}"
        activate
        if (count windows) > 0 then
            set bounds of front window to {{{x}, {y}, {x + w}, {y + h}}}
        end if
    end tell
    """
    _run_apple(script)
    return f"✅ Moved {app_name}: ({x}, {y}, {w}×{h})"


def tile_windows(app1: str, app2: str, layout: str = "side-by-side") -> str:
    """
    Tile two application windows.
    layout: 'side-by-side' (left/right) | 'top-bottom' (top/bottom)
    """
    sw, sh = _get_screen_size()
    toolbar_h = 25  # macOS menu bar

    if layout in ("side-by-side", "horizontal", "left-right"):
        half_w = sw // 2
        _set_window_bounds(app1, 0,      toolbar_h, half_w, sh - toolbar_h)
        _set_window_bounds(app2, half_w, toolbar_h, half_w, sh - toolbar_h)
        return f"✅ Tiled {app1} (left) and {app2} (right) side-by-side."

    elif layout in ("top-bottom", "vertical", "stacked"):
        half_h = (sh - toolbar_h) // 2
        _set_window_bounds(app1, 0, toolbar_h,           sw, half_h)
        _set_window_bounds(app2, 0, toolbar_h + half_h,  sw, half_h)
        return f"✅ Tiled {app1} (top) and {app2} (bottom)."

    else:
        return f"❌ Unknown layout '{layout}'. Use 'side-by-side' or 'top-bottom'."


def focus_app(app_name: str) -> str:
    """Bring an application to the front screen, unminimizing and unhiding if needed."""
    import subprocess
    aliases = {
        "vscode": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
        "code": "Visual Studio Code",
        "terminal": "Terminal",
        "finder": "Finder",
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "safari": "Safari",
        "spotify": "Spotify",
        "calculator": "Calculator",
        "notes": "Notes",
        "settings": "System Settings",
        "system settings": "System Settings",
        "textedit": "TextEdit",
    }
    target = aliases.get(app_name.lower().strip(), app_name.strip())

    script = f'''
    tell application "{target}"
        reopen
        activate
    end tell

    tell application "System Events"
        try
            set proc to first process whose (name is "{target}" or title is "{target}")
            set visible of proc to true
            set frontmost of proc to true
            tell proc
                repeat with w in windows
                    try
                        set value of attribute "AXMinimized" of w to false
                    end try
                end repeat
            end tell
        end try
    end tell
    '''
    _run_apple(script)
    subprocess.run(["open", "-a", target], stderr=subprocess.DEVNULL)
    return f"Brought {target} to the front screen, sir."


def maximize_window(app_name: str) -> str:
    """Maximize a window to full screen size."""
    sw, sh = _get_screen_size()
    return _set_window_bounds(app_name, 0, 25, sw, sh - 25)


def move_window(app_name: str, position: str = "center") -> str:
    """
    Move a window to a named position: center, top-left, top-right, bottom-left, bottom-right.
    """
    sw, sh = _get_screen_size()
    toolbar_h = 25
    usable_h = sh - toolbar_h
    hw, hh = sw // 2, usable_h // 2

    positions = {
        "center":       (sw // 4, toolbar_h + usable_h // 4, hw, hh),
        "top-left":     (0,  toolbar_h,        hw, hh),
        "top-right":    (hw, toolbar_h,        hw, hh),
        "bottom-left":  (0,  toolbar_h + hh,   hw, hh),
        "bottom-right": (hw, toolbar_h + hh,   hw, hh),
        "left":         (0,  toolbar_h,        hw, usable_h),
        "right":        (hw, toolbar_h,        hw, usable_h),
        "top":          (0,  toolbar_h,        sw, hh),
        "bottom":       (0,  toolbar_h + hh,   sw, hh),
        "fullscreen":   (0,  toolbar_h,        sw, usable_h),
    }

    if position not in positions:
        return f"❌ Unknown position '{position}'. Options: {', '.join(positions.keys())}"

    x, y, w, h = positions[position]
    return _set_window_bounds(app_name, x, y, w, h)


def dim_all_except(app_name: str) -> str:
    """
    Focus the target app and hide all other visible apps.
    Uses macOS 'hide' which removes them from display without closing.
    """
    # First, bring the target app to front
    _run_apple(f'tell application "{app_name}" to activate')

    # Get all running apps and hide everything else
    script = """
    tell application "System Events"
        set all_procs to (every process whose visible is true and name is not "Finder" and name is not "Dock")
        set app_names to name of every item of all_procs
    end tell
    """
    raw = _run_apple(script)

    # Build hide script for everything except the target
    hide_script = f"""
    tell application "System Events"
        set all_procs to (every process whose visible is true and name is not "Finder" and name is not "Dock" and name is not "{app_name}")
        repeat with proc in all_procs
            set visible of proc to false
        end repeat
    end tell
    """
    _run_apple(hide_script)
    return f"✅ Focused on {app_name} — all other windows hidden. Say 'show all windows' to restore."


def show_all_windows() -> str:
    """Restore all hidden app windows."""
    script = """
    tell application "System Events"
        set all_procs to (every process)
        repeat with proc in all_procs
            try
                set visible of proc to true
            end try
        end repeat
    end tell
    """
    _run_apple(script)
    return "✅ All windows restored."


def get_open_windows() -> str:
    """List all visible open applications and their windows."""
    script = """
    tell application "System Events"
        set result_list to {}
        set all_procs to (every process whose visible is true)
        repeat with proc in all_procs
            set proc_name to name of proc
            set end of result_list to proc_name
        end repeat
    end tell
    return result_list
    """
    raw = _run_apple(script)
    if not raw:
        return "No visible applications found."
    apps = [a.strip() for a in raw.split(",") if a.strip()]
    return "Open applications: " + ", ".join(apps)
