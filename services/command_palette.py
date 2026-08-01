"""
MARK — Floating Command Palette
macOS menubar app + global hotkey (Option+Space) for instant MARK commands.
Uses rumps for menubar + pynput for hotkey + osascript for input dialog.
"""

import os
import threading
import subprocess
import requests


PORT = os.getenv("PORT", "5050")
MARK_API = f"http://localhost:{PORT}/api/command"


def _send_command(command):
    """Send a command to the MARK server and return the response."""
    try:
        resp = requests.post(MARK_API, json={"command": command}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", "Done, sir.")
        else:
            return f"Error: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return "MARK server is not running."
    except Exception as e:
        return f"Error: {str(e)}"


def _show_notification(title, message):
    """Show a macOS notification."""
    # Truncate for notification
    message = message[:200]
    script = f'''
    display notification "{message}" with title "{title}" sound name "Glass"
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception:
        pass


def _show_input_dialog():
    """Show a native macOS text input dialog and return the entered text."""
    script = '''
    tell application "System Events"
        activate
        set userInput to text returned of (display dialog "MARK Command:" default answer "" with title "⚡ MARK Command Palette" buttons {"Cancel", "Execute"} default button "Execute" with icon note)
        return userInput
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _handle_palette_command():
    """Show input dialog, execute command, show result notification."""
    command = _show_input_dialog()
    if not command:
        return

    response = _send_command(command)
    _show_notification("MARK", response)


def _start_hotkey_listener():
    """Listen for the Option+Space global hotkey."""
    try:
        from pynput import keyboard

        pressed = set()

        def on_press(key):
            pressed.add(key)
            try:
                # Option (Alt) + Space. Deliberately not Command+Space, which
                # macOS reserves for Spotlight.
                option_down = (keyboard.Key.alt in pressed
                               or keyboard.Key.alt_l in pressed
                               or keyboard.Key.alt_r in pressed)
                if option_down and key == keyboard.Key.space:
                    pressed.discard(keyboard.Key.space)
                    threading.Thread(target=_handle_palette_command, daemon=True).start()
            except Exception:
                pass

        def on_release(key):
            pressed.discard(key)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        print("  🎯 Command palette hotkey active (Option+Space)")
    except ImportError:
        print("  ⚠️  pynput not installed. Hotkey disabled.")
    except Exception as e:
        print(f"  ⚠️  Hotkey listener error: {e}")


def _start_menubar():
    """Start the macOS menubar app using rumps."""
    try:
        import rumps

        class MarkPalette(rumps.App):
            def __init__(self):
                super().__init__("🤖", quit_button=None)
                self.menu = [
                    rumps.MenuItem("⚡ Command MARK...", callback=self._open_palette),
                    None,  # separator
                    rumps.MenuItem("🔄 Reset Chat", callback=self._reset_chat),
                    rumps.MenuItem("📊 System Stats", callback=self._system_stats),
                    rumps.MenuItem("📸 Screenshot", callback=self._screenshot),
                    rumps.MenuItem("🧹 Clean Desktop", callback=self._clean_desktop),
                    None,
                    rumps.MenuItem("Quit MARK Palette", callback=self._quit),
                ]

            def _open_palette(self, _):
                threading.Thread(target=_handle_palette_command, daemon=True).start()

            def _reset_chat(self, _):
                resp = _send_command("reset")
                _show_notification("MARK", "Chat history reset.")

            def _system_stats(self, _):
                resp = _send_command("system stats")
                _show_notification("MARK System Stats", resp)

            def _screenshot(self, _):
                resp = _send_command("screenshot")
                _show_notification("MARK", resp)

            def _clean_desktop(self, _):
                resp = _send_command("clean desktop")
                _show_notification("MARK", resp)

            def _quit(self, _):
                rumps.quit_application()

        palette = MarkPalette()
        palette.run()

    except ImportError:
        print("  ⚠️  rumps not installed. Menubar disabled.")
    except Exception as e:
        print(f"  ⚠️  Menubar error: {e}")


def start_palette():
    """
    Run the palette. Blocks — rumps owns the thread it runs on.

    This must be the main thread of its process: AppKit aborts if an
    NSApplication event loop is started anywhere else. That is why the server
    launches this as a separate process rather than a thread.
    """
    _start_hotkey_listener()
    _start_menubar()


# ─────────────────────────────────────────────
# DETACHED LAUNCH (used by app.py)
# ─────────────────────────────────────────────

_child = None


def launch_detached(port=None):
    """
    Start the palette as its own process.

    uvicorn owns the server's main thread, and rumps needs a main thread of its
    own, so the two cannot coexist in one process — the previous build simply
    disabled the palette to avoid the crash.
    """
    global _child
    import sys

    if _child and _child.poll() is None:
        return _child

    env = os.environ.copy()
    if port:
        env["PORT"] = str(port)
    env["MARK_PALETTE_CHILD"] = "1"

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        _child = subprocess.Popen(
            [sys.executable, "-m", "services.command_palette"],
            cwd=project_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("  🎯 Command palette running (menubar + Option+Space)")
        return _child
    except Exception as e:
        print(f"  ⚠️  Command palette could not start: {e}")
        return None


def stop_detached():
    """Terminate the palette process, if we started one."""
    global _child
    if _child and _child.poll() is None:
        try:
            _child.terminate()
            _child.wait(timeout=3)
        except Exception:
            try:
                _child.kill()
            except Exception:
                pass
    _child = None


if __name__ == "__main__":
    start_palette()
