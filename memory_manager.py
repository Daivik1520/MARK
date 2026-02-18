"""
MARK — Long-Term Memory Manager
Persistent memory storage for personal information, preferences, and notes.
Stores data in memory.json alongside the application.
"""

import json
import os
import datetime

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")


def _load_memories() -> dict:
    """Load all memories from the JSON file."""
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_memories(data: dict):
    """Persist memories to the JSON file."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_memory(key: str, value: str) -> str:
    """
    Store a memory with a descriptive key and value.
    If the key already exists, it will be updated.
    """
    key = key.strip().lower()
    if not key or not value:
        return "Cannot save an empty memory."

    memories = _load_memories()
    is_update = key in memories

    memories[key] = {
        "value": value.strip(),
        "created": memories.get(key, {}).get("created", datetime.datetime.now().isoformat()),
        "updated": datetime.datetime.now().isoformat()
    }

    _save_memories(memories)

    if is_update:
        return f"Memory updated — '{key}' has been changed, sir."
    return f"Got it — I'll remember '{key}', sir."


def recall_memory(query: str) -> str:
    """
    Search memories by key or value. Returns matching memories.
    Supports partial/fuzzy matching.
    """
    query = query.strip().lower()
    if not query:
        return "Please specify what you'd like me to recall."

    memories = _load_memories()
    if not memories:
        return "I don't have any memories stored yet, sir."

    matches = []

    for key, data in memories.items():
        value = data["value"] if isinstance(data, dict) else str(data)

        # Exact key match
        if query == key:
            matches.insert(0, (key, value, 100))
            continue

        # Partial key match
        if query in key or key in query:
            matches.append((key, value, 80))
            continue

        # Value contains query
        if query in value.lower():
            matches.append((key, value, 60))
            continue

        # Word-level matching
        query_words = set(query.split())
        key_words = set(key.split())
        value_words = set(value.lower().split())
        overlap = query_words & (key_words | value_words)
        if overlap:
            score = len(overlap) / len(query_words) * 50
            matches.append((key, value, score))

    if not matches:
        return f"I don't have any memory matching '{query}', sir."

    # Sort by relevance score
    matches.sort(key=lambda x: x[2], reverse=True)

    results = []
    for key, value, _ in matches[:5]:
        results.append(f"• **{key}**: {value}")

    return "Here's what I remember:\n" + "\n".join(results)


def list_memories() -> str:
    """List all stored memory keys."""
    memories = _load_memories()
    if not memories:
        return "No memories stored yet, sir."

    items = []
    for key, data in memories.items():
        value = data["value"] if isinstance(data, dict) else str(data)
        preview = value[:60] + "..." if len(value) > 60 else value
        items.append(f"• **{key}**: {preview}")

    return f"I have {len(memories)} memories stored:\n" + "\n".join(items)


def delete_memory(key: str) -> str:
    """Delete a specific memory by key."""
    key = key.strip().lower()
    memories = _load_memories()

    if key not in memories:
        # Try fuzzy match
        for k in memories:
            if key in k or k in key:
                del memories[k]
                _save_memories(memories)
                return f"Memory '{k}' deleted, sir."
        return f"No memory found for '{key}', sir."

    del memories[key]
    _save_memories(memories)
    return f"Memory '{key}' has been forgotten, sir."
