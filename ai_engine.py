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

Important rules:
- Always confirm actions before executing dangerous operations (shutdown, restart).
- Be concise but informative in responses.
- For music requests, ask whether they want Spotify or YouTube if not specified.
- When opening apps or websites, use the appropriate tools.
- Keep responses short and punchy.
- Address the user as \"sir\" naturally.
"""

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
