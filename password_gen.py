"""
MARK — Password Generator
Generates cryptographically secure passwords with customizable options.
Uses Python's secrets module for true randomness.
"""

import secrets
import string
import subprocess


def generate_password(length="16", options=""):
    """
    Generate a strong password.
    length: number of characters (default 16)
    options: comma-separated flags like "no-symbols", "numbers-only", "pin",
             "memorable", "copy" (auto-copy to clipboard)
    """
    try:
        n = int(length)
    except (ValueError, TypeError):
        n = 16
    n = max(4, min(n, 128))

    opts = set(o.strip().lower() for o in (options or "").split(",") if o.strip())
    auto_copy = "copy" in opts

    if "pin" in opts:
        pwd = "".join(secrets.choice(string.digits) for _ in range(n))
        label = "PIN"
    elif "numbers-only" in opts or "numeric" in opts:
        pwd = "".join(secrets.choice(string.digits) for _ in range(n))
        label = "Numeric"
    elif "no-symbols" in opts or "alphanumeric" in opts:
        chars = string.ascii_letters + string.digits
        pwd = _generate_strong(chars, n, require_symbol=False)
        label = "Alphanumeric"
    elif "memorable" in opts:
        pwd = _generate_memorable(n)
        label = "Memorable"
    else:
        chars = string.ascii_letters + string.digits + "!@#$%&*_+-=?"
        pwd = _generate_strong(chars, n, require_symbol=True)
        label = "Strong"

    # Calculate strength
    strength = _assess_strength(pwd)

    lines = [
        "🔐 Password Generated",
        "━" * 30,
        "Password : {}".format(pwd),
        "Length   : {}".format(len(pwd)),
        "Type     : {}".format(label),
        "Strength : {}".format(strength),
        "━" * 30,
    ]

    if auto_copy:
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(pwd.encode("utf-8"))
            lines.append("✅ Copied to clipboard!")
        except Exception:
            lines.append("⚠️ Could not copy to clipboard")
    else:
        lines.append("💡 Say 'copy' to copy it to clipboard")

    return "\n".join(lines)


def _generate_strong(chars, length, require_symbol=True):
    """Generate a password ensuring character variety."""
    for _ in range(100):
        pwd = "".join(secrets.choice(chars) for _ in range(length))
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        if has_upper and has_lower and has_digit:
            if not require_symbol:
                return pwd
            has_sym = any(c in "!@#$%&*_+-=?" for c in pwd)
            if has_sym:
                return pwd
    return pwd


def _generate_memorable(word_count):
    """Generate a memorable passphrase with random words."""
    words = [
        "alpha", "blaze", "coral", "drift", "ember", "frost", "grove", "haven",
        "ivory", "jade", "knack", "lunar", "maple", "nexus", "orbit", "prism",
        "quest", "raven", "solar", "tiger", "ultra", "vivid", "wired", "xenon",
        "yield", "zen", "arrow", "bolt", "crypt", "delta", "eagle", "flame",
        "ghost", "hawk", "iron", "joker", "karma", "lemon", "magic", "noble",
        "ocean", "pixel", "quake", "rapid", "storm", "torch", "unity", "venom",
        "wolf", "zephyr", "blitz", "cipher", "dynamo", "echo", "flux", "glyph",
        "hyper", "intel", "jazz", "kite", "laser", "micro", "nano", "omega",
        "pulse", "radar", "spark", "turbo", "apex", "blade"
    ]
    count = max(3, min(word_count // 4, 8))
    chosen = [secrets.choice(words).capitalize() for _ in range(count)]
    # Add a random number between words
    num = str(secrets.randbelow(900) + 100)
    pos = secrets.randbelow(len(chosen))
    chosen.insert(pos, num)
    return "-".join(chosen)


def _assess_strength(pwd):
    """Rate password strength."""
    score = 0
    if len(pwd) >= 8: score += 1
    if len(pwd) >= 12: score += 1
    if len(pwd) >= 16: score += 1
    if any(c.isupper() for c in pwd): score += 1
    if any(c.islower() for c in pwd): score += 1
    if any(c.isdigit() for c in pwd): score += 1
    if any(c in string.punctuation for c in pwd): score += 1
    unique_ratio = len(set(pwd)) / len(pwd) if pwd else 0
    if unique_ratio > 0.7: score += 1

    if score >= 7: return "🟢 Excellent"
    if score >= 5: return "🟡 Good"
    if score >= 3: return "🟠 Moderate"
    return "🔴 Weak"
