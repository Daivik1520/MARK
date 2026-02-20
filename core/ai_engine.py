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
from core.system_controller import execute_tool

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

HOLOGRAPHIC HUD:
Use show_hud_card(title, content, icon, duration) to display a floating glass card on screen.
Perfect for showing quick info like weather, system stats, reminders, or search results.
The card appears as a transparent overlay, auto-dismisses. Use when results are short and visual.

DIGITAL JANITOR (File Cleanup):
Use clean_desktop to organize and clean up the user's Desktop automatically.
Use organize_downloads to clean up the Downloads folder.
Moves files into categories: Screenshots, PDFs, Code, Images, Videos, Archives, etc.
Deletes old .dmg/.pkg files older than 7 days.
When user says "clean my desktop", "organize files", "tidy up", use these tools.

CODE WRITER (AI-Generated Code):
Use write_code(description, language, filename) to generate code from a natural language description.
The code is written to a file on the Desktop and opened in TextEdit for review.
Does NOT execute the code — only writes it. When user says "write a script", "create a program",
"make a python file that...", use this tool.

RESEARCH AGENT:
Use research_topic(topic, depth) for autonomous research. MARK searches the web, reads multiple pages,
and generates a formatted Markdown report saved to the Desktop.
depth can be "quick" (3 sources) or "deep" (10 sources).
When user says "research X", "prepare a briefing on", "deep dive into", use this tool.

IMAGE EDITOR:
Use edit_image(input_path, output_path, operations) for voice-controlled image manipulation.
Operations are comma-separated: crop_square, resize:WxH, watermark:TEXT, rotate:DEGREES,
grayscale, blur:RADIUS, flip:horizontal, brightness:1.2, contrast:1.3.
When user says "crop", "resize", "add watermark", "edit image", use this tool.

FOCUS BUBBLE (Distraction Shield):
Use start_focus(duration_minutes, blocked_apps, blocked_sites) to start a focus session.
Blocks social media apps (auto-closes them) and browser tabs with distracting sites.
Sends HUD warnings to keep user on track. Default: 60 min, blocks Twitter/Reddit/YouTube/Discord etc.
Use stop_focus to end a session early. When user says "lock me in", "focus mode", "no distractions", use start_focus.

BROWSER COPILOT:
Use browser_do(task) for hands-free browser automation. Takes a plain English description.
Launches a VISIBLE browser window and clicks, types, scrolls automatically.
The user can watch the browser work in real-time. Takes a screenshot at the end.
When user says "go to Amazon and search", "open Google and find", "browse to", use browser_do.

UNIVERSAL SEARCH (Semantic Desktop Search):
Use search_content(query, directories) to find files by CONTENT, not filename.
Searches text files in ~/Documents, ~/Desktop, ~/Downloads using TF-IDF ranking.
When user says "find the document about", "search my files for", "where did I save that thing about", use search_content.

DATA EXTRACTION (Web Scraping):
Use scrape_data(task, output_format, max_items) to extract structured data from websites.
Navigates to the site, extracts repeating data (product listings, tables, search results), saves as CSV or JSON to Desktop.
output_format: "csv" or "json". max_items: number of items (default 20).
When user says "scrape", "extract data from", "save top 10 results", "download a list of", use scrape_data.

GHOST CURSOR (Precision OS Control):
Use move_mouse(x, y) to move the mouse cursor to pixel coordinates.
Use click_at(x, y, button) to click at coordinates (button: "left", "right", "double").
Use click_text(text) to find text on screen using OCR and click it. Great for clicking buttons!
Use scroll_screen(direction, amount) to scroll (direction: up/down/left/right, amount: 1-20).
Use type_text(text) to type text at the current cursor position.
Use get_screen_size() to get display dimensions.
When user says "move mouse", "click on", "scroll down", "click the X button", use ghost cursor tools.

WEBSITE BUILDER:
Use build_website(description, name) to create complete websites from natural language.
Creates a project folder on Desktop with index.html, style.css, script.js and opens in browser.
When user says "make a website", "build a page", "create a landing page", "make me a calendar site", use build_website.

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

        for attempt in range(2):  # 2 attempts max (was 3)
            try:
                print(f"  → Trying {model} (attempt {attempt + 1}/2)...")
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=15)  # 15s (was 60s)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("choices"):
                        print(f"  ✓ Success with {model}")
                        return data
                    print(f"  ✗ Empty choices from {model}")
                    break

                elif resp.status_code == 429:
                    wait = (attempt + 1) * 2  # 2s, 4s (was 4s, 8s, 12s)
                    print(f"  ⏳ Rate limited on {model}, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                elif resp.status_code in (402, 404, 400):
                    print(f"  ✗ {resp.status_code} on {model}, skipping...")
                    break

                elif resp.status_code >= 500:
                    time.sleep(1)  # 1s (was 2s/4s)
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

        # Use tool result directly — NO second AI call needed
        # This saves 2-8 seconds per tool command
        follow_up = tool_results[0]["result"] if tool_results else "Done, sir."

        conversation_history.append({"role": "assistant", "content": follow_up})
        return {"text": follow_up, "tool_calls": tool_results}

    else:
        text = message.get("content", "I didn't catch that, sir.")
        conversation_history.append({"role": "assistant", "content": text})
        return {"text": text, "tool_calls": None}
