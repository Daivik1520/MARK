"""
MARK — Path Normalisation

Small models trained mostly on Windows and Linux examples will happily produce
`C:/Users/YourUsername/Desktop/notes.txt` when asked for a path on a Mac. Left
alone, that creates a literal directory named `C:` wherever the process
happens to be running.

Every tool that touches the filesystem routes its path through here first, so a
plausible-looking but wrong path is corrected rather than obeyed.
"""

import os
import re

HOME = os.path.expanduser("~")

# Windows drive letter, with either slash direction.
_WINDOWS_DRIVE = re.compile(r"^[a-zA-Z]:[\\/]+")
# Placeholder usernames these models reach for.
_PLACEHOLDER_USER = re.compile(
    r"^(?:Users|home)[\\/]+"
    r"(?:YourUsername|username|user|<username>|yourname|me|Your Name|\{username\})"
    r"[\\/]+", re.I,
)
# Linux home that is not this machine's home.
_LINUX_HOME = re.compile(r"^/home/[^/]+/")

# Folder names we can confidently re-root under the real home directory.
_KNOWN_FOLDERS = {
    "desktop": "Desktop",
    "documents": "Documents",
    "downloads": "Downloads",
    "pictures": "Pictures",
    "movies": "Movies",
    "music": "Music",
    "library": "Library",
    "applications": "Applications",
}


def normalize(path):
    """
    Turn a model-supplied path into a sane absolute macOS path.

    Rules, in order:
      * strip a Windows drive prefix and any placeholder user segment
      * rewrite a foreign Linux home to this machine's home
      * expand ~ and environment variables
      * re-root a bare known folder name (Desktop/Documents/...) under $HOME
      * resolve anything still relative against $HOME rather than the process
        working directory, so a stray write cannot land inside the repo
    """
    if not path:
        return path

    original = str(path).strip().strip('"').strip("'")
    if not original:
        return original

    cleaned = original

    # C:\Users\YourUsername\Desktop\x  ->  Users/YourUsername/Desktop/x
    if _WINDOWS_DRIVE.match(cleaned):
        cleaned = _WINDOWS_DRIVE.sub("", cleaned)
        cleaned = cleaned.replace("\\", "/")

    # Users/YourUsername/Desktop/x  ->  Desktop/x
    cleaned = _PLACEHOLDER_USER.sub("", cleaned)

    # /home/bob/notes.txt -> ~/notes.txt
    cleaned = _LINUX_HOME.sub("~/", cleaned)

    # A real /Users/<someone>/ that is not us — keep the tail only.
    if cleaned.startswith("/Users/"):
        parts = cleaned.split("/", 3)
        if len(parts) >= 3 and parts[2] and parts[2] != os.path.basename(HOME):
            cleaned = "~/" + (parts[3] if len(parts) > 3 else "")

    cleaned = os.path.expanduser(os.path.expandvars(cleaned))

    if os.path.isabs(cleaned):
        return os.path.normpath(cleaned)

    # Relative: re-root a known folder, otherwise resolve under home.
    head = cleaned.split("/", 1)[0].lower()
    if head in _KNOWN_FOLDERS:
        rest = cleaned.split("/", 1)[1] if "/" in cleaned else ""
        return os.path.normpath(os.path.join(HOME, _KNOWN_FOLDERS[head], rest))

    return os.path.normpath(os.path.join(HOME, cleaned))


def looks_foreign(path):
    """True if a path was clearly written for another operating system."""
    if not path:
        return False
    text = str(path)
    return bool(
        _WINDOWS_DRIVE.match(text)
        or _PLACEHOLDER_USER.match(text)
        or _LINUX_HOME.match(text)
        or "\\" in text
    )
