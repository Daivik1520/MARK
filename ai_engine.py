"""
MARK — AI Engine
OpenRouter integration with function calling for system control.
Includes retry logic, model fallback, and robust error handling.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from system_controller import execute_tool

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ─────────────────────────────────────────────
# MODEL FALLBACK LIST (tried in order)
# ─────────────────────────────────────────────

MODELS = [
    "google/gemma-3-12b-it:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-27b-it:free",
]

# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are MARK, an advanced AI system controller built to manage and control a macOS computer.
You were created by DAIVIK for his personal use. Daivik is your creator and the user you serve.
You are highly capable, fast, and precise. You speak with confidence and call the user "sir".

You have access to system control tools. When the user asks you to perform a system action, you MUST use the appropriate tool.
When the user asks a general question that doesn't require system interaction, answer directly and concisely.

IMPORTANT — "MARK" is the user's wake word to activate you. If someone just says "MARK" or "Hey Mark",
they are activating you, NOT asking about a person named Mark. Respond with something like "Yes, sir?" or "I'm here, sir. What can I do for you?" and wait for further instructions.

When calling tools, you MUST use the EXACT parameter names as defined:
- create_folder: folder_path (e.g. "~/Desktop/my_folder")
- create_file: file_path, content
- open_file: file_path
- open_folder: folder_path
- open_app: app_name
- open_website: url
- send_whatsapp: contact, message
- play_music: query, platform
- search_files: query, directory
- set_volume: level
- web_search: query
- save_memory: key, value
- recall_memory: query
- list_memories: (no args)
- delete_memory: key
- analyze_screen: query
- run_routine: name
- list_routines: (no args)
- create_routine: name, description, steps_json
- set_reminder: message, time_str
- list_reminders: (no args)
- delete_reminder: reminder_id
- clear_reminders: (no args)
- track_number: phone
- get_clipboard_history: count
- search_clipboard: query
- paste_from_history: index
- get_context: (no args)
- get_news_briefing: topic
- get_news: topic, count
- run_code: code, language
- generate_password: length, options

MEMORY SYSTEM:
You have persistent long-term memory. When the user says "remember", "save", "store", or tells you personal info, use save_memory.
When they ask "what's my...", "do you remember...", use recall_memory. You can also list_memories and delete_memory.

VISION SYSTEM:
You can see the user's screen. When they say "look at my screen", "what do you see", "analyze this error",
"summarize what I'm looking at", use analyze_screen with a specific query about what to look for.

ROUTINES SYSTEM:
You can execute multi-step routines. Available: coding mode, good morning, study mode, presentation mode,
relax mode, gaming mode, night mode, meeting mode. Use run_routine when user says "start X mode".
You can also list_routines and create_routine for custom ones.

REMINDER SYSTEM:
You can set reminders that fire as macOS notifications and spoken alerts. Use set_reminder with a message
and time like "in 10 minutes", "at 3:30 PM", "tomorrow at 9:00". Use list_reminders to show active ones.
Use delete_reminder or clear_reminders to manage them.

PHONE TRACKER:
You can look up phone numbers. When the user says "track this number", "who owns this number", "look up this phone",
use track_number with the phone number. It returns carrier, location, timezone, line type, and validity.

SMART CLIPBOARD:
You track the user's clipboard in the background. Use get_clipboard_history to show recent copies,
search_clipboard to find something they copied, and paste_from_history to re-copy an old item.
When user says "show my clipboard", "what did I copy", "paste that link from earlier", use these tools.

CONTEXTUAL AWARENESS:
You can see what app, window, tab, and URL the user has open right now. Use get_context when the user says
"what am I looking at", "summarize this page", "what app am I in", or when you need context for a task.

NEWS BRIEFING:
You can get news headlines and give briefings. Use get_news_briefing for a full morning briefing (news + weather + reminders).
Use get_news for just headlines on a topic. When user says "give me a briefing", "what's in the news", "morning update", use these.

CODE RUNNER:
You can execute code. Use run_code with the code and language (python, javascript, shell).
When user says "run this code", "execute this", "what does this output", write and run the code.

PASSWORD GENERATOR:
Generate secure passwords. Use generate_password with length and options ("no-symbols", "pin", "memorable", "copy").
When user says "generate a password", "I need a password for X", use this tool. Always offer to copy it.

SYSTEM HEALTH & PROACTIVE MONITOR:
Use get_system_stats to show CPU, RAM, disk, battery, and top processes.
When user says "how is my system", "system health", "what's using CPU", use this tool.

WINDOW MANAGEMENT:
Use tile_windows(app1, app2, layout) to split two apps side-by-side or stacked.
Use focus_app(app_name) to bring an app to front.
Use dim_all_except(app_name) to hide everything and focus on one app.
Use move_window(app_name, position) with positions: left, right, top, bottom, center, top-left, top-right, bottom-left, bottom-right, fullscreen.
Use show_all_windows() to restore all hidden apps.
When user says "tile", "split screen", "focus on", "dim everything", use window management tools.

WEB STEERING (Real Browser):
Use web_search_deep(query) for real web research — returns titles, snippets and URLs from DuckDuckGo.
Use web_get_stock(ticker) to fetch live stock price and change from Yahoo Finance.
Use web_book_restaurant(query, location) to find restaurants with ratings and links.
Use web_navigate(url) to visit any URL and return the page content.
When user says "look up", "search the web", "find a restaurant", "what is Tesla's stock", use these tools.

Important rules:
- Always confirm actions before executing dangerous operations (shutdown, restart).
- Be concise but informative in responses.
- For music requests, ask whether they want Spotify or YouTube if not specified.
- When opening apps or websites, use the appropriate tools.
- Keep responses short and punchy.
- Address the user as \"sir\" naturally.
"""

def get_system_prompt():
    """Return the current system prompt."""
    return SYSTEM_PROMPT

def set_system_prompt(new_prompt):
    """Update the system prompt at runtime."""
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = new_prompt

# ─────────────────────────────────────────────
# TOOL DEFINITIONS (OpenRouter function calling)
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
    }
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
# ROBUST API CALL WITH RETRY + MODEL FALLBACK
# ─────────────────────────────────────────────

def _call_openrouter(messages, use_tools=True):
    """
    Robust API call: tries each model in MODELS list.
    On 429 (rate limit), waits and retries. On 402/404, skips to next model.
    Returns parsed JSON response dict or None on total failure.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "MARK AI System Controller"
    }

    for model in MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7
        }
        if use_tools:
            payload["tools"] = TOOLS
            payload["tool_choice"] = "auto"

        for attempt in range(3):
            try:
                print(f"  → Trying {model} (attempt {attempt + 1}/3)...")
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("choices"):
                        print(f"  ✓ Success with {model}")
                        return data
                    print(f"  ✗ Empty choices from {model}")
                    break

                elif resp.status_code == 429:
                    wait = (attempt + 1) * 4
                    print(f"  ⏳ Rate limited on {model}, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                elif resp.status_code in (402, 404, 400):
                    print(f"  ✗ {resp.status_code} on {model}, skipping...")
                    break

                elif resp.status_code >= 500:
                    time.sleep((attempt + 1) * 2)
                    continue

                else:
                    print(f"  ✗ {resp.status_code} on {model}")
                    break

            except requests.exceptions.Timeout:
                print(f"  ✗ Timeout on {model}")
                continue
            except requests.exceptions.ConnectionError:
                print(f"  ✗ Connection error")
                time.sleep(2)
                continue
            except Exception as e:
                print(f"  ✗ Error: {e}")
                break

    return None


def get_ai_response(user_message):
    """
    Get AI response from OpenRouter with function calling.
    Returns: {"text": str, "tool_calls": list | None}
    """
    global conversation_history

    conversation_history.append({"role": "user", "content": user_message})

    if len(conversation_history) > MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

    print(f"🤖 Processing: \"{user_message}\"")

    data = _call_openrouter(messages, use_tools=True)

    if not data:
        error_msg = "I'm having trouble connecting right now, sir. Please try again in a moment."
        conversation_history.append({"role": "assistant", "content": error_msg})
        return {"text": error_msg, "tool_calls": None}

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    tool_calls = message.get("tool_calls")

    if tool_calls:
        conversation_history.append({
            "role": "assistant",
            "content": message.get("content", ""),
            "tool_calls": tool_calls
        })

        tool_results = []
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                args_str = tc["function"].get("arguments", "{}")
                func_args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except (json.JSONDecodeError, TypeError):
                func_args = {}

            print(f"  ⚡ Executing: {func_name}({func_args})")
            result = execute_tool(func_name, func_args)
            print(f"  ✓ Result: {result[:100]}")

            tc_id = tc.get("id", f"call_{func_name}")
            tool_results.append({"tool_call_id": tc_id, "name": func_name, "result": result})
            conversation_history.append({"role": "tool", "tool_call_id": tc_id, "content": result})

        # Follow-up response after tool execution
        msgs2 = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history
        data2 = _call_openrouter(msgs2, use_tools=False)

        if data2:
            follow_up = data2["choices"][0]["message"].get("content", "")
        else:
            follow_up = tool_results[0]["result"] if tool_results else "Action completed, sir."

        if not follow_up:
            follow_up = tool_results[0]["result"] if tool_results else "Done, sir."

        conversation_history.append({"role": "assistant", "content": follow_up})
        return {"text": follow_up, "tool_calls": tool_results}

    else:
        text = message.get("content", "I didn't catch that, sir.")
        conversation_history.append({"role": "assistant", "content": text})
        return {"text": text, "tool_calls": None}
