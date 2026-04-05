"""
MARK — AI Engine
Fully local: Gemma 2 2B-IT (Metal GPU) via llama-cpp-python.
No cloud APIs needed. 100% private.
"""

import os
import json
import re
import time
from dotenv import load_dotenv
from core.system_controller import execute_tool

load_dotenv()

# ─────────────────────────────────────────────
# BACKEND — local only (Gemma 2 2B via llama-cpp-python)
# ─────────────────────────────────────────────

_llm_backend = "local"

def get_llm_backend():
    return _llm_backend

def set_llm_backend(backend):
    global _llm_backend
    if backend in ("local",):
        _llm_backend = backend
        print(f"  🔄 LLM backend set to: {backend}")
        return True
    return False

PRIMARY_MODEL = "gemma-2-2b-it"  # Local model identifier

# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are MARK — Daivik's personal AI companion and system controller. He built you. You're loyal, sharp, and always present. Think of yourself as his closest friend who controls his entire computer.

PERSONALITY: Talk like a REAL HUMAN — warm, casual, natural. Use contractions, occasional fillers ("hmm", "well...", "ah"), micro-reactions ("got it", "boom, done", "on it"). Call him "sir" naturally. Keep responses SHORT. Vary energy. Be witty but not annoying.

If someone just says "MARK" or "Hey Mark", respond naturally: "yeah?", "what's up?", "I'm here, sir".

RULES:
- Just act — use the right tool without explaining. Don't ask for confirmation on safe operations.
- Only confirm DANGEROUS operations (shutdown, delete files) casually.
- NEVER paste code in chat — use write_code, build_website, or write_file tools.
- For websites, ALWAYS use build_website tool immediately. Never write HTML in chat.
- For music: ask "spotify or youtube?"
- For system tasks with no specific tool, use run_terminal.
- Prefer dedicated file tools (read_file, write_file) over run_terminal.
- For memory, prefer rag_remember/rag_recall over save_memory/recall_memory.
- SPEECH: Your output is spoken by TTS. No markdown, no bullets. Write naturally with "..." for pauses. Short sentences.

"""

def get_system_prompt():
    """Return the current system prompt."""
    return SYSTEM_PROMPT

def set_system_prompt(new_prompt):
    """Update the system prompt at runtime."""
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = new_prompt

# ─────────────────────────────────────────────
# TOOL DEFINITIONS (Groq function calling)
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application on the Mac using Spotlight search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app to open"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website URL in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open, e.g. 'google.com'"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Send a WhatsApp message to a contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "Contact name"},
                    "message": {"type": "string", "description": "Message to send"}
                },
                "required": ["contact", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_file",
            "description": "Open a file with its default application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_folder",
            "description": "Open a folder in Finder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Path to the folder"}
                },
                "required": ["folder_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with optional content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path for the new file"},
                    "content": {"type": "string", "description": "File content (optional)"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder/directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Path for the new folder"}
                },
                "required": ["folder_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_notes",
            "description": "Open TextEdit and write notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Notes to write"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "List all currently open/visible application windows.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "Bring a specific application window to the front.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "App name to bring to front"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_shutdown",
            "description": "Shut down the Mac. Only use when user explicitly confirms.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_sleep",
            "description": "Put the Mac to sleep.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_restart",
            "description": "Restart the Mac. Only use when user explicitly confirms.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot and save it to the Desktop.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play music on Spotify or YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song/artist to search for"},
                    "platform": {"type": "string", "enum": ["spotify", "youtube"], "description": "Platform"}
                },
                "required": ["query", "platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files by name on the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Filename to search for"},
                    "directory": {"type": "string", "description": "Directory to search in"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set system volume (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume level 0-100"}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mute_volume",
            "description": "Mute the system volume.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "unmute_volume",
            "description": "Unmute the system volume.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Set the screen brightness level (0-100 percent).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Brightness level 0-100"}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using Google. Use this when the user asks to search for something, look up information, find current news, weather, sports scores, or any factual question you don't know the answer to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        }
    },
    # ── MEMORY TOOLS ──
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a piece of information to long-term memory. Use when the user says 'remember', 'save', 'store', 'note down', or provides personal info to keep.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short descriptive label for the memory (e.g. 'wifi password', 'favorite color', 'mom birthday')"},
                    "value": {"type": "string", "description": "The actual information to remember"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Search and recall stored memories. Use when the user asks 'what is my...', 'do you remember...', 'what did I tell you about...'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for in memory (e.g. 'wifi password', 'birthday')"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "List all stored memories. Use when the user asks 'what do you remember' or 'show my memories'.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_memory",
            "description": "Delete a stored memory. Use when the user says 'forget', 'delete', 'remove' a memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The memory key to delete"}
                },
                "required": ["key"]
            }
        }
    },
    # ── VISION TOOLS ──
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": "Take a screenshot and analyze what's on the user's screen using AI vision. Use when the user says 'look at my screen', 'what do you see', 'analyze this', 'what's on my screen', 'help me with this error', 'read this', 'summarize what I'm looking at'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific question about the screen content (e.g. 'what error is this?', 'summarize this article', 'what app is open?')"}
                },
                "required": ["query"]
            }
        }
    },
    # ── ROUTINE TOOLS ──
    {
        "type": "function",
        "function": {
            "name": "run_routine",
            "description": "Execute a predefined multi-step routine. Available routines: coding mode, good morning, study mode, presentation mode, relax mode, gaming mode, night mode, meeting mode. Use when user says 'start X mode', 'activate X', 'begin X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the routine to run (e.g. 'coding mode', 'good morning')"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_routines",
            "description": "List all available routines. Use when user asks 'what routines do you have' or 'list modes'.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_routine",
            "description": "Create a new custom routine with multiple steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the new routine"},
                    "description": {"type": "string", "description": "What this routine does"},
                    "steps_json": {"type": "string", "description": "JSON array of steps, each with 'action' and 'args'"}
                },
                "required": ["name", "description", "steps_json"]
            }
        }
    },
    # ── REMINDER TOOLS ──
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a timed reminder that will fire as a macOS notification and spoken alert. Use when the user says 'remind me', 'set a reminder', 'alert me', 'notify me'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "What to remind about (e.g. 'Take a break', 'Call Mom')"},
                    "time_str": {"type": "string", "description": "When to fire: 'in 10 minutes', 'at 3:30 PM', 'tomorrow at 9:00', 'in 1 hour'"}
                },
                "required": ["message", "time_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List all active reminders. Use when the user asks 'what reminders do I have' or 'show my reminders'.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_reminder",
            "description": "Delete a specific reminder by matching its message text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "Text from the reminder message to match and delete"}
                },
                "required": ["reminder_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clear_reminders",
            "description": "Clear all active reminders.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── PHONE TRACKER ──
    {
        "type": "function",
        "function": {
            "name": "track_number",
            "description": "Track a phone number to get carrier, location, timezone, line type and validity. Use when user asks to 'track this number', 'who owns this number', 'look up phone number'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "The phone number to track (e.g. +919876543210, 9876543210, +1-555-123-4567)"}
                },
                "required": ["phone"]
            }
        }
    },
    # ── CLIPBOARD ──
    {
        "type": "function",
        "function": {
            "name": "get_clipboard_history",
            "description": "Show recent clipboard history. Use when user asks 'show my clipboard', 'what did I copy'.",
            "parameters": {"type": "object", "properties": {"count": {"type": "string", "description": "Number of items (default 10)"}}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_clipboard",
            "description": "Search clipboard history by keyword.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Keyword to search"}}, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "paste_from_history",
            "description": "Copy a specific item from clipboard history back to clipboard. Use with an index number from get_clipboard_history.",
            "parameters": {"type": "object", "properties": {"index": {"type": "string", "description": "Item number from history (1 = most recent)"}}, "required": ["index"]}
        }
    },
    # ── CONTEXT ──
    {
        "type": "function",
        "function": {
            "name": "get_context",
            "description": "Get current context: active app, window title, browser URL. Use when user says 'what am I looking at', 'summarize this page', or for any context-aware task.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── NEWS ──
    {
        "type": "function",
        "function": {
            "name": "get_news_briefing",
            "description": "Get a morning briefing with top news, weather, and pending reminders. Use when user says 'give me a briefing', 'morning update', 'what's happening'.",
            "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "Optional topic focus"}}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get news headlines, optionally on a specific topic.",
            "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "Topic or category"}, "count": {"type": "string", "description": "Number of articles (default 5)"}}, "required": []}
        }
    },
    # ── CODE RUNNER ──
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Execute code and return output. Supports python, javascript, shell. Use when user says 'run this code', 'execute this'.",
            "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "The code to execute"}, "language": {"type": "string", "description": "python, javascript, or shell"}}, "required": ["code", "language"]}
        }
    },
    # ── PASSWORD GENERATOR ──
    {
        "type": "function",
        "function": {
            "name": "generate_password",
            "description": "Generate a strong, secure password. Options: 'no-symbols', 'pin', 'memorable', 'copy' (auto-copy to clipboard).",
            "parameters": {"type": "object", "properties": {"length": {"type": "string", "description": "Password length (default 16)"}, "options": {"type": "string", "description": "Comma-separated: no-symbols, pin, memorable, copy"}}, "required": []}
        }
    },
    # ── SYSTEM HEALTH ──
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Get real-time system health: CPU, RAM, disk, battery, network, and top processes.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── WINDOW MANAGEMENT ──
    {
        "type": "function",
        "function": {
            "name": "tile_windows",
            "description": "Tile two application windows side-by-side or top-bottom. Use when user says 'tile X and Y', 'split screen'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app1": {"type": "string", "description": "First app name"},
                    "app2": {"type": "string", "description": "Second app name"},
                    "layout": {"type": "string", "description": "'side-by-side' or 'top-bottom' (default side-by-side)"}
                },
                "required": ["app1", "app2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "focus_app",
            "description": "Bring a specific application to the front and focus it.",
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "App to focus"}},
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dim_all_except",
            "description": "Hide all apps except one — gives the target app full focus. User says 'focus on X and hide everything else', 'dim everything except X'.",
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "App to keep visible"}},
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_window",
            "description": "Move a window to a named position: left, right, top, bottom, center, top-left, top-right, bottom-left, bottom-right, fullscreen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "App to move"},
                    "position": {"type": "string", "description": "Position: left, right, center, fullscreen, top-left, top-right, bottom-left, bottom-right"}
                },
                "required": ["app_name", "position"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_all_windows",
            "description": "Restore all hidden application windows. Use after dim_all_except.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── WEB STEERER ──
    {
        "type": "function",
        "function": {
            "name": "web_search_deep",
            "description": "Perform a real web search using a headless browser. Returns titles, snippets, and URLs. Use for research questions.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to search for"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_get_stock",
            "description": "Look up the current stock price and change for a ticker symbol from Yahoo Finance.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "Stock ticker (e.g. TSLA, AAPL, NVDA)"}},
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_book_restaurant",
            "description": "Find restaurants matching a query near a location. Returns top results with ratings, addresses, and links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'Italian', 'sushi', 'fine dining'"},
                    "location": {"type": "string", "description": "City or area (default: nearby)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_navigate",
            "description": "Visit a URL with a real browser and return the page content summary.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL to visit"}},
                "required": ["url"]
            }
        }
    },
    # ── HOLOGRAPHIC HUD ──
    {
        "type": "function",
        "function": {
            "name": "show_hud_card",
            "description": "Display a floating glassmorphism card on the user's screen. Great for short info displays like weather, stats, quick answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Card title (short, uppercase-style)"},
                    "content": {"type": "string", "description": "Card body text (supports basic HTML: <strong>, <br>)"},
                    "icon": {"type": "string", "description": "Emoji icon for the card header (default: 🔮)"},
                    "duration": {"type": "integer", "description": "Seconds to show before auto-dismiss (default: 8)"}
                },
                "required": ["title", "content"]
            }
        }
    },
    # ── DIGITAL JANITOR ──
    {
        "type": "function",
        "function": {
            "name": "clean_desktop",
            "description": "Organize and clean up the Desktop. Moves files into categorized folders (Screenshots, PDFs, Code, Images, etc.) and deletes old installers.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "organize_downloads",
            "description": "Organize and clean up the Downloads folder. Same as clean_desktop but for Downloads.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── CODE WRITER ──
    {
        "type": "function",
        "function": {
            "name": "write_code",
            "description": "Generate code from a natural language description. Writes to a file on the Desktop and opens it for review. Does NOT execute the code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What the code should do"},
                    "language": {"type": "string", "description": "Programming language (default: python)"},
                    "filename": {"type": "string", "description": "Optional output filename"}
                },
                "required": ["description"]
            }
        }
    },
    # ── RESEARCH AGENT ──
    {
        "type": "function",
        "function": {
            "name": "research_topic",
            "description": "Research a topic autonomously: search the web, scrape pages, and generate a formatted Markdown report saved to the Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to research"},
                    "depth": {"type": "string", "description": "'quick' (3 sources) or 'deep' (10 sources). Default: quick"}
                },
                "required": ["topic"]
            }
        }
    },
    # ── IMAGE TOOLS ──
    {
        "type": "function",
        "function": {
            "name": "edit_image",
            "description": "Edit an image with chained operations: crop_square, resize:WxH, watermark:TEXT, rotate:DEGREES, grayscale, blur:RADIUS, flip:horizontal, brightness:1.2, contrast:1.3.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Path to source image (supports ~)"},
                    "output_path": {"type": "string", "description": "Where to save result (default: Desktop with _edited suffix)"},
                    "operations": {"type": "string", "description": "Comma-separated operations, e.g. 'crop_square,watermark:CONFIDENTIAL,resize:800x800'"}
                },
                "required": ["input_path", "operations"]
            }
        }
    },
    # ── FOCUS BUBBLE ──
    {
        "type": "function",
        "function": {
            "name": "start_focus",
            "description": "Start a focus session. Blocks distracting apps and websites for the specified duration. Auto-closes blacklisted apps and browser tabs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration_minutes": {"type": "string", "description": "Duration in minutes (default: 60)"},
                    "blocked_apps": {"type": "string", "description": "Comma-separated app names to block (default: social media)"},
                    "blocked_sites": {"type": "string", "description": "Comma-separated domains to block (default: social media)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_focus",
            "description": "End the current focus session early. Returns a session summary.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── BROWSER COPILOT ──
    {
        "type": "function",
        "function": {
            "name": "browser_do",
            "description": "Execute a browser task described in natural language. Opens a visible browser window and performs clicks, typing, scrolling automatically. Takes a screenshot of the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Plain English description of what to do in the browser"}
                },
                "required": ["task"]
            }
        }
    },
    # ── UNIVERSAL SEARCH ──
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "Search local files by content using semantic matching. Finds documents by what they contain, not their filename. Searches ~/Documents, ~/Desktop, ~/Downloads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                    "directories": {"type": "string", "description": "Comma-separated directories to search (default: ~/Documents, ~/Desktop, ~/Downloads)"}
                },
                "required": ["query"]
            }
        }
    },
    # ── DATA EXTRACTOR ──
    {
        "type": "function",
        "function": {
            "name": "scrape_data",
            "description": "Scrape structured data from a website. Navigates to the site, extracts repeating items (products, search results, tables), and saves as CSV or JSON to Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What to scrape (e.g. 'Go to Amazon and search for laptops under $1000')"},
                    "output_format": {"type": "string", "description": "'csv' or 'json' (default: csv)"},
                    "max_items": {"type": "string", "description": "Maximum items to extract (default: 20)"}
                },
                "required": ["task"]
            }
        }
    },
    # ── GHOST CURSOR ──
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse cursor to specific pixel coordinates on screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "string", "description": "X coordinate (pixels from left)"},
                    "y": {"type": "string", "description": "Y coordinate (pixels from top)"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_at",
            "description": "Click at specific pixel coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "string", "description": "X coordinate"},
                    "y": {"type": "string", "description": "Y coordinate"},
                    "button": {"type": "string", "description": "'left', 'right', or 'double' (default: left)"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_text",
            "description": "Find text on screen using OCR and click on it. Use when user says 'click the Submit button' or 'click on Settings'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to find and click (e.g. 'Submit', 'Settings', 'Export')"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_screen",
            "description": "Scroll the screen up, down, left, or right.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "description": "'up', 'down', 'left', 'right'"},
                    "amount": {"type": "string", "description": "Number of scroll steps 1-20 (default: 3)"}
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text at the current cursor position in whatever app is active.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_size",
            "description": "Get the current screen dimensions in pixels.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── WEBSITE BUILDER ──
    {
        "type": "function",
        "function": {
            "name": "build_website",
            "description": "Generate a complete website (HTML + CSS + JS) from a description. Creates a project folder on Desktop and opens in browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What the website should be (e.g. 'a calendar app', 'a portfolio page')"},
                    "name": {"type": "string", "description": "Optional project folder name (auto-generated if empty)"}
                },
                "required": ["description"]
            }
        }
    },
    # ── VISION CLICK (AI-Powered Screen Interaction) ──
    {
        "type": "function",
        "function": {
            "name": "vision_click",
            "description": "Find ANY UI element on screen using AI vision and click it. Works with any app — buttons, links, icons, menus, text fields. Use when you need to interact with apps that don't have AppleScript support.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string", "description": "What to click, e.g. 'the Send button', 'the red close button', 'the search bar', 'the Settings icon'"}
                },
                "required": ["instruction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_find",
            "description": "Find a UI element on screen and return its coordinates WITHOUT clicking. Use to locate elements before deciding what action to take.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string", "description": "What to find on screen"}
                },
                "required": ["instruction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_describe",
            "description": "Analyze the screen and list ALL visible interactive UI elements (buttons, links, fields, icons, menus) with their locations.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_type",
            "description": "Find a text field on screen using AI vision, click it, then type text into it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string", "description": "Which text field to target (e.g. 'the search bar', 'the email field', 'the password input')"},
                    "text": {"type": "string", "description": "Text to type after clicking the field"}
                },
                "required": ["instruction", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vision_interact",
            "description": "Interact with a screen element using vision: click, double_click, right_click, hover, or find.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "'click', 'double_click', 'right_click', 'hover', or 'find'"},
                    "target": {"type": "string", "description": "Description of the UI element to interact with"}
                },
                "required": ["action", "target"]
            }
        }
    },
    # ── RAG MEMORY (Semantic Long-Term Memory) ──
    {
        "type": "function",
        "function": {
            "name": "rag_remember",
            "description": "Store information in semantic RAG memory. More powerful than save_memory — supports semantic search. Use for remembering facts, preferences, personal info, or anything the user wants remembered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The information to remember"},
                    "category": {"type": "string", "description": "Category: 'personal', 'work', 'preference', 'fact', 'credential', 'conversation', 'general'"},
                    "source": {"type": "string", "description": "Source: 'user', 'web', 'file', 'conversation' (default: 'user')"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_recall",
            "description": "Semantically search RAG memory. Finds relevant memories even with different wording. More powerful than recall_memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for (natural language)"},
                    "n_results": {"type": "string", "description": "Max results to return (default: 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_forget",
            "description": "Remove a memory from RAG storage by searching for matching text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to match for deletion"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_list",
            "description": "List all stored RAG memories, optionally filtered by category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Optional category filter (personal, work, preference, fact, etc.)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_stats",
            "description": "Get statistics about the RAG memory system (total memories, categories, backend info).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # ── TERMINAL EXECUTOR ──
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Execute any shell command on the system. This is the most powerful tool — use it for system operations, installations, git commands, package management, network ops, process management, and anything not covered by other tools. Returns stdout, stderr, and exit code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute (e.g. 'ls -la', 'brew install node', 'git status', 'curl https://example.com')"},
                    "working_dir": {"type": "string", "description": "Working directory (default: ~). Supports ~ expansion."},
                    "timeout": {"type": "integer", "description": "Max execution time in seconds (default: 30, max: 120)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of any file on the system (up to 50KB). Use for inspecting config files, logs, code, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file (supports ~ expansion)"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content. Creates parent directories automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path for the file (supports ~ expansion)"},
                    "content": {"type": "string", "description": "Content to write to the file"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Find and replace text in an existing file. Replaces all occurrences of old_text with new_text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to edit"},
                    "old_text": {"type": "string", "description": "The exact text to find and replace"},
                    "new_text": {"type": "string", "description": "The replacement text"}
                },
                "required": ["file_path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory with details (size, modification date, type).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current directory)"},
                    "show_hidden": {"type": "string", "description": "'true' to show hidden files (default: false)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get detailed macOS system information: hostname, user, OS, CPU, memory, disk, network, installed packages.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    # ── MCP (Model Context Protocol) ──
    {
        "type": "function",
        "function": {
            "name": "mcp_status",
            "description": "Show the status of all MCP (Model Context Protocol) server connections and their tool counts.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_connect",
            "description": "Connect to MCP tool servers. Use 'all' to connect to all configured servers, or specify a server name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {"type": "string", "description": "Server name or 'all' (default: 'all')"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_disconnect",
            "description": "Disconnect from MCP servers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_name": {"type": "string", "description": "Server name or 'all' (default: 'all')"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_list_tools",
            "description": "List all available tools from connected MCP servers.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_add_server",
            "description": "Add a new MCP server configuration. After adding, use mcp_connect to connect.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Server identifier (e.g. 'filesystem', 'github')"},
                    "command": {"type": "string", "description": "Command to run (e.g. 'npx', 'python3', 'node')"},
                    "args": {"type": "string", "description": "Arguments as space-separated string or JSON array"},
                    "env": {"type": "string", "description": "Environment variables as JSON object (optional)"}
                },
                "required": ["name", "command", "args"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_remove_server",
            "description": "Remove an MCP server configuration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Server name to remove"}
                },
                "required": ["name"]
            }
        }
    },
]

# ─────────────────────────────────────────────
# CONVERSATION MANAGEMENT
# ─────────────────────────────────────────────

conversation_history = []
MAX_HISTORY = 20


def reset_conversation():
    """Clear conversation history."""
    global conversation_history
    conversation_history = []


# ─────────────────────────────────────────────
# LOCAL LLM CALL — Gemma 2 2B via llama-cpp-python
# ─────────────────────────────────────────────

def _call_local_llm(messages, max_tokens=1024, temperature=0.7):
    """
    Call the local Gemma 2 2B model.
    Returns text string or None on error.
    """
    from core.local_llm import local_chat
    return local_chat(messages, max_tokens=max_tokens, temperature=temperature)


def get_ai_response_streaming(user_message):
    """
    Non-streaming AI response wrapper (local model doesn't support streaming).
    Yields the full response as a single done event.

    Yields: {"type": "done", "text": str, "tool_calls": list|None}  — final result
    """
    result = get_ai_response(user_message)
    yield {"type": "done", "text": result["text"], "tool_calls": result.get("tool_calls")}


def get_ai_response(user_message):
    """
    Get AI response using local Gemma 2 2B model.
    Returns: {"text": str, "tool_calls": list | None}
    """
    global conversation_history

    conversation_history.append({"role": "user", "content": user_message})

    if len(conversation_history) > MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

    print(f"🤖 Processing: \"{user_message}\" [backend=local/gemma-2-2b]")

    return _handle_local_response(messages, user_message)






# ─────────────────────────────────────────────
# KEYWORD → TOOL mapping for reliable local dispatch
# When the fast router misses and the LLM might hallucinate,
# these keyword rules map intent directly to tools.
# ─────────────────────────────────────────────

_INTENT_MAP = [
    # Screen / Vision
    (re.compile(r"what'?s? on (?:my )?screen|analyze (?:my )?screen|look at (?:my )?screen|read (?:my )?screen|what (?:do you see|can you see)|describe (?:my )?screen", re.I), "analyze_screen", lambda _: {"query": "Describe what you see on the screen"}),
    (re.compile(r"windows? (?:are )?open(?:ed)?|(?:open|running|current) (?:apps|windows|applications)|what(?:'s| is) (?:currently )?open|list (?:open )?windows|show (?:open )?windows|what (?:apps|windows) (?:do I|are)", re.I), "list_windows", lambda _: {}),

    # System
    (re.compile(r"system (?:stats|health|status|info)|cpu|ram usage|memory usage|disk usage|battery level|how is my (?:system|computer|mac)", re.I), "get_system_stats", lambda _: {}),
    (re.compile(r"system info(?:rmation)?|mac info|computer info", re.I), "get_system_info", lambda _: {}),

    # Screenshot
    (re.compile(r"screenshot|screen capture|capture screen", re.I), "take_screenshot", lambda _: {}),

    # Volume / Brightness
    (re.compile(r"volume (\d+)|set volume (?:to )?(\d+)", re.I), "set_volume", lambda m: {"level": int(m.group(1) or m.group(2))}),
    (re.compile(r"brightness (\d+)|set brightness (?:to )?(\d+)", re.I), "set_brightness", lambda m: {"level": int(m.group(1) or m.group(2))}),
    (re.compile(r"\bmute\b", re.I), "mute_volume", lambda _: {}),
    (re.compile(r"\bunmute\b", re.I), "unmute_volume", lambda _: {}),

    # News / Search
    (re.compile(r"news|headlines|briefing|what's happening|morning update", re.I), "get_news_briefing", lambda _: {"topic": ""}),
    (re.compile(r"search (?:for |google |the web for )?(.+)", re.I), "web_search", lambda m: {"query": m.group(1).strip()}),
    (re.compile(r"research (?:about |on |the topic of )?(.+)", re.I), "research_topic", lambda m: {"topic": m.group(1).strip()}),

    # Memory / Reminders
    (re.compile(r"(?:list|show|what) (?:are )?(?:my )?(?:all )?memories|what do you remember", re.I), "list_memories", lambda _: {}),
    (re.compile(r"recall|remember what|what (?:is|was) my (.+)", re.I), "recall_memory", lambda m: {"query": m.group(1).strip() if m.lastindex else user_message}),
    (re.compile(r"(?:list|show|what are) (?:my )?reminders", re.I), "list_reminders", lambda _: {}),
    (re.compile(r"clear (?:all )?reminders", re.I), "clear_reminders", lambda _: {}),
    (re.compile(r"remind me (?:to )?(.+?) (?:at|in|on|tomorrow) (.+)", re.I), "set_reminder", lambda m: {"message": m.group(1).strip(), "time_str": m.group(2).strip()}),

    # Clipboard
    (re.compile(r"clipboard|what did I copy", re.I), "get_clipboard_history", lambda _: {}),

    # Context
    (re.compile(r"what (?:am I|app is) (?:looking at|in|using)|get context|what (?:page|tab|website) (?:am I|is) (?:on|open)", re.I), "get_context", lambda _: {}),

    # Routines
    (re.compile(r"(?:list|show|what) (?:are )?(?:all )?routines|what modes", re.I), "list_routines", lambda _: {}),

    # Code / Build
    (re.compile(r"(?:write|create|generate|make) (?:me )?(?:a )?(.+?) (?:script|program|code|function)(?: in (\w+))?", re.I), "write_code", lambda m: {"description": m.group(1).strip(), "language": m.group(2) or "python"}),
    (re.compile(r"(?:make|build|create|generate) (?:me )?(?:a )?(.+?) (?:website|site|page|webpage)", re.I), "build_website", lambda m: {"description": m.group(1).strip() + " website"}),

    # Window management
    (re.compile(r"(?:focus|switch to|bring up) (.+)", re.I), "focus_app", lambda m: {"app_name": m.group(1).strip()}),
    (re.compile(r"(?:open|launch|start) (?:the )?(?:app )?(.+?)(?:\s+app)?$", re.I), "open_app", lambda m: {"app_name": m.group(1).strip()}),
    (re.compile(r"(?:open|go to|visit) ((?:https?://)?(?:www\.)?[\w.-]+\.\w{2,}(?:/\S*)?)", re.I), "open_website", lambda m: {"url": m.group(1).strip()}),

    # Music
    (re.compile(r"play (.+)", re.I), "play_music", lambda m: {"query": m.group(1).strip(), "platform": "youtube"}),

    # Vision click
    (re.compile(r"(?:click|press|tap)(?: on)? (?:the )?(.+?)(?:\s+button|\s+icon|\s+link)?$", re.I), "vision_click", lambda m: {"instruction": m.group(1).strip()}),

    # Power
    (re.compile(r"\bsleep\b", re.I), "system_sleep", lambda _: {}),
    (re.compile(r"\bshutdown\b|\bshut down\b", re.I), "system_shutdown", lambda _: {}),
    (re.compile(r"\brestart\b|reboot", re.I), "system_restart", lambda _: {}),

    # Clean up
    (re.compile(r"clean (?:my )?(?:the )?desktop|organize (?:my )?desktop|tidy (?:(?:up )?(?:my )?)?desktop", re.I), "clean_desktop", lambda _: {}),

    # Password
    (re.compile(r"generate (?:a )?(?:strong |secure )?password", re.I), "generate_password", lambda _: {}),
]


def _dispatch_by_intent(user_message):
    """
    Try to map a user message to a tool call via keyword intent matching.
    Returns tool result dict or None.
    """
    for pattern, tool_name, arg_extractor in _INTENT_MAP:
        match = pattern.search(user_message)
        if match:
            try:
                args = arg_extractor(match)
                result = execute_tool(tool_name, args)
                result_str = str(result) if result else ""
                print(f"  🎯 Intent routed: {tool_name}({args}) → {result_str[:80]}")
                return {
                    "text": result_str,
                    "tool_calls": [{"name": tool_name, "result": result_str}],
                }
            except Exception as e:
                print(f"  ✗ Intent dispatch failed {tool_name}: {e}")
                return None
    return None


def _handle_local_response(messages, user_message):
    """Handle response via local Gemma 2 2B.

    Priority:
    1. Intent dispatch (keyword → tool) for action commands
    2. LLM for pure conversational/reasoning responses
    """
    global conversation_history

    from core.local_llm import local_chat

    # ── Step 1: Try to execute the right tool by intent ──
    intent_result = _dispatch_by_intent(user_message)
    if intent_result:
        conversation_history.append({"role": "assistant", "content": intent_result["text"]})
        return intent_result

    # ── Step 2: Call local LLM for conversation/reasoning ──
    # Use a compact, Gemma-friendly prompt — no tool instructions (avoids hallucination)
    slim_messages = []
    system_injected = False
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "system":
            # Inject only the key personality traits, strip 95% of the prompt
            if not system_injected:
                slim_messages.append({
                    "role": "user",
                    "content": (
                        "You are MARK, a smart AI system controller assistant for macOS. "
                        "You are helpful, concise, and address the user as 'sir'. "
                        "Answer the user's question directly.\n\n"
                        + user_message
                    )
                })
                system_injected = True
        elif role in ("user", "assistant"):
            if not system_injected:
                slim_messages.append({"role": role, "content": content})
            # Skip after injecting (message already included above)

    if not slim_messages:
        slim_messages = [{"role": "user", "content": user_message}]

    text = local_chat(slim_messages, max_tokens=512, temperature=0.7)

    if text is None:
        error_msg = "Local model is loading or unavailable, sir. Please wait a moment."
        conversation_history.append({"role": "assistant", "content": error_msg})
        return {"text": error_msg, "tool_calls": None}

    conversation_history.append({"role": "assistant", "content": text})
    return {"text": text, "tool_calls": None}

