"""
MARK — Smart Routines Engine
Predefined and custom multi-action routines triggered by a single command.
E.g., "Start coding mode" → Opens VS Code + Plays Lo-Fi + Sets DND.
"""

import json
import os
import time

ROUTINES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "routines.json")

# ─────────────────────────────────────────────
# DEFAULT ROUTINES (built-in)
# ─────────────────────────────────────────────

DEFAULT_ROUTINES = {
    "coding mode": {
        "description": "Set up the perfect coding environment",
        "steps": [
            {"action": "open_app", "args": {"app_name": "Visual Studio Code"}},
            {"action": "play_music", "args": {"query": "lofi hip hop beats", "platform": "youtube"}},
            {"action": "set_volume", "args": {"level": 30}},
            {"action": "set_brightness", "args": {"level": 70}}
        ]
    },
    "good morning": {
        "description": "Start the day with news, weather, and your calendar",
        "steps": [
            {"action": "set_brightness", "args": {"level": 80}},
            {"action": "set_volume", "args": {"level": 40}},
            {"action": "open_app", "args": {"app_name": "Calendar"}},
            {"action": "web_search", "args": {"query": "today's top news headlines"}},
            {"action": "open_website", "args": {"url": "https://weather.com"}}
        ]
    },
    "study mode": {
        "description": "Focus environment for studying",
        "steps": [
            {"action": "open_app", "args": {"app_name": "Notes"}},
            {"action": "play_music", "args": {"query": "study music concentration", "platform": "youtube"}},
            {"action": "set_volume", "args": {"level": 25}},
            {"action": "set_brightness", "args": {"level": 75}}
        ]
    },
    "presentation mode": {
        "description": "Prepare for giving a presentation",
        "steps": [
            {"action": "set_volume", "args": {"level": 60}},
            {"action": "set_brightness", "args": {"level": 100}},
            {"action": "mute_volume", "args": {}}
        ]
    },
    "relax mode": {
        "description": "Wind down with music and dimmed screen",
        "steps": [
            {"action": "set_brightness", "args": {"level": 40}},
            {"action": "set_volume", "args": {"level": 35}},
            {"action": "play_music", "args": {"query": "chill relaxing music", "platform": "youtube"}}
        ]
    },
    "gaming mode": {
        "description": "Optimize for gaming",
        "steps": [
            {"action": "set_brightness", "args": {"level": 90}},
            {"action": "set_volume", "args": {"level": 70}}
        ]
    },
    "night mode": {
        "description": "Prepare for late-night work with low brightness",
        "steps": [
            {"action": "set_brightness", "args": {"level": 20}},
            {"action": "set_volume", "args": {"level": 15}}
        ]
    },
    "meeting mode": {
        "description": "Prepare for a virtual meeting",
        "steps": [
            {"action": "set_volume", "args": {"level": 50}},
            {"action": "set_brightness", "args": {"level": 80}}
        ]
    }
}


def _load_custom_routines() -> dict:
    """Load custom routines from file."""
    if not os.path.exists(ROUTINES_FILE):
        return {}
    try:
        with open(ROUTINES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_custom_routines(data: dict):
    """Save custom routines to file."""
    with open(ROUTINES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_all_routines() -> dict:
    """Get all routines: defaults + custom."""
    all_routines = dict(DEFAULT_ROUTINES)
    all_routines.update(_load_custom_routines())
    return all_routines


def run_routine(name: str) -> str:
    """
    Execute a routine by name. Runs each step sequentially.
    Returns a summary of all actions taken.
    """
    name = name.strip().lower()
    routines = _get_all_routines()

    # Try exact match first, then fuzzy
    routine = routines.get(name)
    if not routine:
        for key, val in routines.items():
            if name in key or key in name:
                routine = val
                name = key
                break

    if not routine:
        available = ", ".join(routines.keys())
        return f"Routine '{name}' not found, sir. Available: {available}"

    steps = routine.get("steps", [])
    if not steps:
        return f"Routine '{name}' has no steps defined."

    # Import execute_tool here to avoid circular imports
    from system_controller import execute_tool

    results = []
    total = len(steps)

    for i, step in enumerate(steps, 1):
        action = step.get("action", "")
        args = step.get("args", {})

        try:
            result = execute_tool(action, args)
            results.append(f"✓ Step {i}/{total}: {action} — {result}")
        except Exception as e:
            results.append(f"✗ Step {i}/{total}: {action} — Error: {str(e)}")

        # Small delay between actions to let system catch up
        if i < total:
            time.sleep(0.5)

    summary = f"Routine '{name}' completed ({total} steps):\n" + "\n".join(results)
    return summary


def list_routines() -> str:
    """List all available routines with descriptions."""
    routines = _get_all_routines()

    if not routines:
        return "No routines available, sir."

    lines = [f"Available routines ({len(routines)} total):"]
    for name, data in routines.items():
        desc = data.get("description", "No description")
        step_count = len(data.get("steps", []))
        lines.append(f"• **{name}** — {desc} ({step_count} steps)")

    return "\n".join(lines)


def create_routine(name: str, description: str, steps_json: str) -> str:
    """
    Create a custom routine. Steps should be a JSON string with action/args pairs.
    """
    name = name.strip().lower()
    if not name:
        return "Routine name cannot be empty."

    try:
        steps = json.loads(steps_json) if isinstance(steps_json, str) else steps_json
        if not isinstance(steps, list):
            return "Steps must be a list of {action, args} objects."
    except json.JSONDecodeError:
        return "Invalid steps format. Please provide valid JSON."

    custom = _load_custom_routines()
    custom[name] = {
        "description": description or f"Custom routine: {name}",
        "steps": steps
    }
    _save_custom_routines(custom)

    return f"Routine '{name}' created with {len(steps)} steps, sir."


def delete_routine(name: str) -> str:
    """Delete a custom routine by name."""
    name = name.strip().lower()

    # Can't delete default routines
    if name in DEFAULT_ROUTINES:
        return f"Cannot delete built-in routine '{name}', sir."

    custom = _load_custom_routines()
    if name not in custom:
        return f"Custom routine '{name}' not found, sir."

    del custom[name]
    _save_custom_routines(custom)
    return f"Routine '{name}' deleted, sir."
