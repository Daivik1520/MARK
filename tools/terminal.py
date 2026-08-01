"""
MARK — Terminal Executor
Production-grade shell command execution with safety controls.
Allows the AI to run any command on macOS with proper guardrails.
"""

import subprocess
import os
import time
import platform
import re
import stat
import datetime


MAX_OUTPUT = 10000
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 120

# ─────────────────────────────────────────────
# SAFETY — Commands that are NEVER allowed
# ─────────────────────────────────────────────

BLOCKED_COMMANDS = [
    r"rm\s+-rf\s+/\s*$",
    r"rm\s+-rf\s+~\s*$",
    r"rm\s+-rf\s+/\*",
    r"rm\s+-rf\s+~/\*",
    r"mkfs\b",
    r"dd\s+if=",
    r":\(\)\{\s*:\|:&\s*\};:",       # fork bomb
    r">\s*/dev/sd[a-z]",
    r"chmod\s+-R\s+777\s+/\s*$",
    r"sudo\s+rm\s+-rf\s+/",
    r"sudo\s+mkfs",
    r"sudo\s+dd\s+if=",
    r"format\s+[cC]:",
    r"rm\s+-rf\s+/System",
    r"rm\s+-rf\s+/Library",
    r"rm\s+-rf\s+/usr",
    r"rm\s+-rf\s+/bin",
    r"rm\s+-rf\s+/sbin",
    r"rm\s+-rf\s+/etc",
    r"rm\s+-rf\s+/var",
    r"rm\s+-rf\s+/private",
    r"launchctl\s+unload.*com\.apple",
    r"csrutil\s+disable",
    r"nvram\s+",
    r"diskutil\s+eraseDisk",
    r"diskutil\s+eraseVolume",
]

# Commands that get a warning but still execute
DANGEROUS_PATTERNS = [
    (r"\bsudo\b", "elevated privileges"),
    (r"rm\s+-rf\b", "recursive force delete"),
    (r"chmod\s+777\b", "world-writable permissions"),
    (r"\bkill\s+-9\b", "force kill process"),
    (r"\bpkill\b", "kill processes by name"),
    (r"\bkillall\b", "kill all matching processes"),
    (r"\bmv\s+/", "moving root-level paths"),
    (r"pip\s+install", "installing Python packages"),
    (r"brew\s+uninstall", "removing Homebrew packages"),
    (r"npm\s+install\s+-g", "global npm install"),
    (r">\s*/etc/", "writing to system config"),
    (r"curl\s+.*\|\s*(?:ba)?sh", "piping download to shell"),
]

_BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in BLOCKED_COMMANDS]
_DANGER_RE = [(re.compile(p, re.IGNORECASE), desc) for p, desc in DANGEROUS_PATTERNS]


def _check_safety(command: str) -> tuple:
    """Check command safety. Returns (allowed: bool, warning: str or None)."""
    cmd = command.strip()

    for pattern in _BLOCKED_RE:
        if pattern.search(cmd):
            return False, f"BLOCKED: This command matches a blocked pattern and cannot be executed for safety reasons."

    warnings = []
    for pattern, desc in _DANGER_RE:
        if pattern.search(cmd):
            warnings.append(desc)

    if warnings:
        return True, f"WARNING — This command involves: {', '.join(warnings)}"

    return True, None


def _get_env():
    """Build environment with common tool paths included."""
    env = os.environ.copy()
    extra_paths = ["/usr/local/bin", "/opt/homebrew/bin", "/opt/homebrew/sbin",
                   "/usr/local/sbin", os.path.expanduser("~/.local/bin")]
    existing = env.get("PATH", "")
    for p in extra_paths:
        if p not in existing:
            existing = p + ":" + existing
    env["PATH"] = existing
    return env


def _truncate(text: str, limit: int = MAX_OUTPUT) -> str:
    """Truncate text to limit with indicator."""
    if len(text) > limit:
        return text[:limit] + f"\n\n... (output truncated — {len(text)} chars total, showing first {limit})"
    return text


# ─────────────────────────────────────────────
# MAIN: run_terminal
# ─────────────────────────────────────────────

def run_terminal(command: str = "", working_dir: str = "~", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Execute a shell command and return structured output.

    Args:
        command: The shell command to execute
        working_dir: Working directory (supports ~)
        timeout: Max execution time in seconds (max 120)
    """
    if not command or not command.strip():
        return "No command provided."

    command = command.strip()

    # Safety check
    allowed, warning = _check_safety(command)
    if not allowed:
        return warning

    # Clamp timeout
    try:
        timeout = min(int(timeout), MAX_TIMEOUT)
    except (ValueError, TypeError):
        timeout = DEFAULT_TIMEOUT

    # Resolve working directory
    cwd = os.path.expanduser(working_dir)
    if not os.path.isdir(cwd):
        return f"Working directory does not exist: {cwd}"

    # Execute
    start = time.time()
    try:
        result = subprocess.run(
            ["zsh", "-c", command],
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            env=_get_env(),
        )

        elapsed = round(time.time() - start, 2)

        # Decode output
        try:
            stdout = result.stdout.decode("utf-8", errors="replace").strip() if isinstance(result.stdout, bytes) else (result.stdout or "").strip()
        except Exception:
            stdout = repr(result.stdout)

        try:
            stderr = result.stderr.decode("utf-8", errors="replace").strip() if isinstance(result.stderr, bytes) else (result.stderr or "").strip()
        except Exception:
            stderr = repr(result.stderr)

        # Build response
        lines = [f"$ {command}", f"(cwd: {cwd} | {elapsed}s | exit: {result.returncode})"]

        if warning:
            lines.insert(0, warning)

        if stdout:
            lines.append("")
            lines.append(_truncate(stdout))

        if stderr:
            lines.append("")
            lines.append(f"STDERR: {_truncate(stderr)}")

        if result.returncode != 0 and not stdout and not stderr:
            lines.append(f"Command failed with exit code {result.returncode} (no output)")
        elif not stdout and not stderr and result.returncode == 0:
            lines.append("Command completed successfully (no output)")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - start, 2)
        return f"$ {command}\nTIMEOUT: Command did not complete within {timeout}s (ran for {elapsed}s)"
    except PermissionError:
        return f"$ {command}\nPERMISSION DENIED: Cannot execute this command. Try with sudo."
    except FileNotFoundError:
        return f"$ {command}\nNOT FOUND: Shell or command not found."
    except Exception as e:
        return f"$ {command}\nERROR: {type(e).__name__}: {str(e)}"


# ─────────────────────────────────────────────
# FILE OPERATIONS
# ─────────────────────────────────────────────

def read_file(file_path: str = "") -> str:
    """Read and return the contents of a file (up to 50KB)."""
    from core.paths import normalize
    file_path = normalize(file_path)

    if not file_path:
        return "No file path provided."

    path = os.path.expanduser(file_path.strip())

    if not os.path.exists(path):
        return f"File not found: {path}"

    if not os.path.isfile(path):
        return f"Not a file: {path} (is a directory)"

    size = os.path.getsize(path)
    if size > 50 * 1024:
        return f"File too large to read in full: {size:,} bytes ({size/1024:.1f}KB). Max is 50KB. Use 'head' or 'tail' commands for large files."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"File: {path} ({size:,} bytes, {line_count} lines)\n{'─' * 40}\n{content}"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(file_path: str = "", content: str = "") -> str:
    """Write content to a file. Creates parent directories if needed."""
    from core.paths import normalize
    file_path = normalize(file_path)

    if not file_path:
        return "No file path provided."

    path = os.path.expanduser(file_path.strip())

    # Create parent dirs
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception as e:
            return f"Cannot create parent directory: {e}"

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        size = os.path.getsize(path)
        return f"File written: {path} ({size:,} bytes)"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(file_path: str = "", old_text: str = "", new_text: str = "") -> str:
    """Find and replace text in a file."""
    from core.paths import normalize
    file_path = normalize(file_path)

    if not file_path:
        return "No file path provided."
    if not old_text:
        return "No search text (old_text) provided."

    path = os.path.expanduser(file_path.strip())

    if not os.path.exists(path):
        return f"File not found: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()

        count = original.count(old_text)
        if count == 0:
            # Show a preview of the file to help debug
            preview = original[:500]
            return f"Text not found in {path}. No changes made.\nFile preview:\n{preview}..."

        updated = original.replace(old_text, new_text)

        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)

        return f"File edited: {path} — replaced {count} occurrence(s)"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


# ─────────────────────────────────────────────
# DIRECTORY LISTING
# ─────────────────────────────────────────────

def list_directory(path: str = ".", show_hidden: str = "false") -> str:
    """List files and folders in a directory with details."""
    from core.paths import normalize
    path = normalize(path) if path not in ('.', '') else os.path.expanduser('~')

    expanded = os.path.expanduser(path.strip() if path else ".")

    if not os.path.exists(expanded):
        return f"Directory not found: {expanded}"
    if not os.path.isdir(expanded):
        return f"Not a directory: {expanded}"

    show_hidden_bool = str(show_hidden).lower() in ("true", "yes", "1")

    try:
        entries = sorted(os.listdir(expanded))
    except PermissionError:
        return f"Permission denied: {expanded}"

    if not show_hidden_bool:
        entries = [e for e in entries if not e.startswith(".")]

    if not entries:
        return f"Directory is empty: {expanded}"

    lines = [f"Directory: {expanded} ({len(entries)} items)", "─" * 50]

    for name in entries:
        full = os.path.join(expanded, name)
        try:
            st = os.stat(full, follow_symlinks=False)
            size = st.st_size
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")

            if stat.S_ISDIR(st.st_mode):
                kind = "DIR "
                size_str = ""
            elif stat.S_ISLNK(st.st_mode):
                kind = "LINK"
                target = os.readlink(full)
                size_str = f"-> {target}"
            else:
                kind = "FILE"
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f}KB"
                elif size < 1024 * 1024 * 1024:
                    size_str = f"{size/1024/1024:.1f}MB"
                else:
                    size_str = f"{size/1024/1024/1024:.1f}GB"

            lines.append(f"  {kind}  {mtime}  {size_str:>8s}  {name}")
        except Exception:
            lines.append(f"  ???   {'':>19s}  {'':>8s}  {name}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# SYSTEM INFO
# ─────────────────────────────────────────────

def get_system_info() -> str:
    """Get detailed macOS system information."""
    import socket
    info = []

    info.append(f"Hostname: {socket.gethostname()}")
    info.append(f"User: {os.getenv('USER', 'unknown')}")
    info.append(f"Home: {os.path.expanduser('~')}")
    info.append(f"Platform: {platform.platform()}")
    info.append(f"Architecture: {platform.machine()}")
    info.append(f"Python: {platform.python_version()}")

    # macOS version
    try:
        mac_ver = platform.mac_ver()
        if mac_ver[0]:
            info.append(f"macOS: {mac_ver[0]}")
    except Exception:
        pass

    # Shell
    info.append(f"Shell: {os.getenv('SHELL', 'unknown')}")

    # Uptime
    try:
        result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info.append(f"Uptime: {result.stdout.strip()}")
    except Exception:
        pass

    # Disk
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        info.append(f"Disk: {used/1024/1024/1024:.1f}GB used / {total/1024/1024/1024:.1f}GB total ({free/1024/1024/1024:.1f}GB free)")
    except Exception:
        pass

    # Memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        info.append(f"Memory: {mem.used/1024/1024/1024:.1f}GB used / {mem.total/1024/1024/1024:.1f}GB total ({mem.percent}%)")
    except ImportError:
        try:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                total_bytes = int(result.stdout.strip())
                info.append(f"Memory: {total_bytes/1024/1024/1024:.1f}GB total")
        except Exception:
            pass

    # CPU
    try:
        result = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info.append(f"CPU: {result.stdout.strip()}")
        cores = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, timeout=5)
        if cores.returncode == 0:
            info.append(f"CPU Cores: {cores.stdout.strip()}")
    except Exception:
        pass

    # Network interfaces
    try:
        result = subprocess.run(["ifconfig", "-l"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ifaces = result.stdout.strip().split()
            active = [i for i in ifaces if i.startswith(("en", "utun"))]
            info.append(f"Network interfaces: {', '.join(active)}")
    except Exception:
        pass

    # Homebrew package count
    try:
        result = subprocess.run(["brew", "list", "--formula", "-1"], capture_output=True, text=True, timeout=10, env=_get_env())
        if result.returncode == 0:
            count = len([l for l in result.stdout.strip().split("\n") if l.strip()])
            info.append(f"Homebrew packages: {count}")
    except Exception:
        pass

    # Current working directory
    info.append(f"CWD: {os.getcwd()}")

    return "System Information\n" + "─" * 40 + "\n" + "\n".join(info)
