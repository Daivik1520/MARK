"""
MARK — Digital Janitor
Automated file organization for Desktop and Downloads.
Moves files into categorized folders, deletes old installers.
"""

import os
import shutil
import time
import datetime


# ── File Categories ──

CATEGORIES = {
    "Screenshots": {
        "extensions": {".png", ".jpg", ".jpeg"},
        "name_patterns": ["Screenshot", "Screen Shot", "screen_shot", "Capture"],
        "dest": os.path.expanduser("~/Pictures/Screenshots"),
        "use_date_subfolder": True,
    },
    "Images": {
        "extensions": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic"},
        "dest": os.path.expanduser("~/Pictures/Organized"),
    },
    "PDFs": {
        "extensions": {".pdf"},
        "dest": os.path.expanduser("~/Documents/Papers"),
    },
    "Documents": {
        "extensions": {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".csv", ".txt", ".rtf"},
        "dest": os.path.expanduser("~/Documents/Organized"),
    },
    "Code": {
        "extensions": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs", ".rb",
                       ".swift", ".kt", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".bash"},
        "dest": os.path.expanduser("~/Documents/Code"),
    },
    "Archives": {
        "extensions": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
        "dest": os.path.expanduser("~/Documents/Archives"),
    },
    "Videos": {
        "extensions": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"},
        "dest": os.path.expanduser("~/Movies/Organized"),
    },
    "Audio": {
        "extensions": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
        "dest": os.path.expanduser("~/Music/Organized"),
    },
}

# Installer extensions to auto-delete if older than 7 days
INSTALLER_EXTS = {".dmg", ".pkg", ".app"}
ARCHIVE_CLEANUP_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
CLEANUP_AGE_DAYS = 7


def _is_screenshot(filename):
    """Check if a file is a screenshot based on name patterns."""
    lower = filename.lower()
    for pattern in CATEGORIES["Screenshots"]["name_patterns"]:
        if pattern.lower() in lower:
            return True
    return False


def _get_date_subfolder(file_path):
    """Get YYYY-MM subfolder based on file modification time."""
    mtime = os.path.getmtime(file_path)
    dt = datetime.datetime.fromtimestamp(mtime)
    return dt.strftime("%Y-%m")


def _categorize_file(filepath):
    """Determine the category for a file. Returns (category_name, dest_path) or None."""
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()

    # Skip hidden files and system files
    if filename.startswith(".") or filename.startswith("~"):
        return None

    # Screenshots first (subset of images but specific folder)
    if ext in CATEGORIES["Screenshots"]["extensions"] and _is_screenshot(filename):
        cat = CATEGORIES["Screenshots"]
        dest = cat["dest"]
        if cat.get("use_date_subfolder"):
            dest = os.path.join(dest, _get_date_subfolder(filepath))
        return ("Screenshots", dest)

    # Check remaining categories (order: PDFs, Documents, Code, Videos, Audio, Archives, then Images)
    priority_order = ["PDFs", "Documents", "Code", "Videos", "Audio", "Archives", "Images"]
    for cat_name in priority_order:
        cat = CATEGORIES[cat_name]
        if ext in cat["extensions"]:
            return (cat_name, cat["dest"])

    return None


def _safe_move(src, dest_dir):
    """Move file to dest, renaming if a file with the same name exists."""
    os.makedirs(dest_dir, exist_ok=True)
    basename = os.path.basename(src)
    dest_path = os.path.join(dest_dir, basename)

    # Avoid overwriting by adding a suffix
    if os.path.exists(dest_path):
        name, ext = os.path.splitext(basename)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")
            counter += 1

    shutil.move(src, dest_path)
    return dest_path


def clean_desktop():
    """Organize all files on the Desktop into categorized folders."""
    desktop = os.path.expanduser("~/Desktop")
    return _organize_directory(desktop)


def organize_downloads():
    """Organize all files in ~/Downloads into categorized folders."""
    downloads = os.path.expanduser("~/Downloads")
    return _organize_directory(downloads)


def _organize_directory(directory):
    """Core logic: organize files in a directory and clean up old installers."""
    if not os.path.isdir(directory):
        return f"❌ Directory not found: {directory}"

    moved = {}       # category -> count
    deleted = []
    skipped = 0
    errors = []

    now = time.time()
    age_threshold = CLEANUP_AGE_DAYS * 86400  # 7 days in seconds

    for item in os.listdir(directory):
        filepath = os.path.join(directory, item)

        # Skip directories, hidden files
        if os.path.isdir(filepath):
            continue
        if item.startswith("."):
            skipped += 1
            continue

        ext = os.path.splitext(item)[1].lower()

        # Delete old installers/DMGs
        if ext in INSTALLER_EXTS:
            age = now - os.path.getmtime(filepath)
            if age > age_threshold:
                try:
                    os.remove(filepath)
                    deleted.append(item)
                except Exception as e:
                    errors.append(f"Delete {item}: {e}")
                continue

        # Categorize and move
        result = _categorize_file(filepath)
        if result:
            cat_name, dest_dir = result
            try:
                _safe_move(filepath, dest_dir)
                moved[cat_name] = moved.get(cat_name, 0) + 1
            except Exception as e:
                errors.append(f"Move {item}: {e}")
        else:
            skipped += 1

    # Build summary
    dir_name = os.path.basename(directory)
    lines = [f"🧹 **{dir_name} Cleanup Complete**\n"]

    if moved:
        for cat, count in sorted(moved.items()):
            lines.append(f"  📁 {cat}: {count} file{'s' if count > 1 else ''} moved")

    if deleted:
        lines.append(f"  🗑️ Deleted {len(deleted)} old installer{'s' if len(deleted) > 1 else ''}: {', '.join(deleted[:5])}")

    if not moved and not deleted:
        lines.append("  ✨ Already clean — nothing to organize!")

    if skipped:
        lines.append(f"  ⏭️ Skipped {skipped} file{'s' if skipped > 1 else ''} (hidden/uncategorized)")

    if errors:
        lines.append(f"  ⚠️ {len(errors)} error{'s' if len(errors) > 1 else ''}: {errors[0]}")

    return "\n".join(lines)
