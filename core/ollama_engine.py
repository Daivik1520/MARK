"""
MARK — Ollama Backend Engine
Free, unlimited local LLM inference via Ollama.
Supports any model Ollama can run (llama3.3, qwen2.5, deepseek, mistral, etc.)
Uses OpenAI-compatible API with native tool calling support.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.3")  # default model

# Track state
_ollama_model = OLLAMA_MODEL
_ollama_status = "unknown"


def get_ollama_model():
    return _ollama_model


def set_ollama_model(model):
    global _ollama_model
    _ollama_model = model
    print(f"  🔄 Ollama model set to: {model}")
    return True


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

def check_ollama():
    """Check if Ollama is running and return status info."""
    global _ollama_status
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            _ollama_status = "running"
            return {
                "status": "running",
                "url": OLLAMA_BASE_URL,
                "models": models,
                "current_model": _ollama_model,
            }
        _ollama_status = "error"
        return {"status": "error", "message": f"HTTP {resp.status_code}"}
    except requests.ConnectionError:
        _ollama_status = "not_running"
        return {
            "status": "not_running",
            "message": "Ollama is not running. Start it with: ollama serve",
            "install": "Install from https://ollama.com or: brew install ollama",
        }
    except Exception as e:
        _ollama_status = "error"
        return {"status": "error", "message": str(e)}


def list_ollama_models():
    """List all locally available Ollama models."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            if not models:
                return "No models downloaded. Pull one with: ollama pull llama3.3"
            lines = ["Available Ollama Models", "─" * 40]
            for m in models:
                name = m["name"]
                size_gb = m.get("size", 0) / (1024**3)
                modified = m.get("modified_at", "")[:10]
                current = " (active)" if name == _ollama_model or name.split(":")[0] == _ollama_model else ""
                lines.append(f"  {'●' if current else '○'} {name} ({size_gb:.1f}GB) {modified}{current}")
            return "\n".join(lines)
        return f"Failed to list models: HTTP {resp.status_code}"
    except requests.ConnectionError:
        return "Ollama is not running. Start it with: ollama serve"
    except Exception as e:
        return f"Error listing models: {e}"


def pull_ollama_model(model_name=""):
    """Pull/download an Ollama model."""
    if not model_name:
        return "Specify a model name, e.g., 'llama3.3', 'qwen2.5', 'deepseek-r1'"
    try:
        print(f"  ↓ Pulling Ollama model: {model_name}...")
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name, "stream": False},
            timeout=600,  # 10 min for large models
        )
        if resp.status_code == 200:
            return f"Model '{model_name}' pulled successfully. Set it active with: set model to {model_name}"
        return f"Failed to pull model: {resp.text[:200]}"
    except requests.ConnectionError:
        return "Ollama is not running. Start with: ollama serve"
    except requests.Timeout:
        return f"Download timed out. The model may still be downloading in background. Check: ollama list"
    except Exception as e:
        return f"Error pulling model: {e}"


# ─────────────────────────────────────────────
# CHAT API — OpenAI-compatible with tool calling
# ─────────────────────────────────────────────

def ollama_chat(messages, tools=None, max_tokens=1024, temperature=0.7):
    """
    Send a chat request to Ollama with optional tool calling.
    Uses the /api/chat endpoint which supports OpenAI-style tool calling.

    Args:
        messages: OpenAI-style message list
        tools: Optional list of tool definitions (OpenAI format)
        max_tokens: Max response tokens
        temperature: Sampling temperature

    Returns:
        Response message object (dict with 'content' and optionally 'tool_calls'),
        or None on error.
    """
    # Filter messages to only include supported roles/fields
    clean_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "tool":
            # Ollama expects tool responses in a specific format
            clean_messages.append({
                "role": "tool",
                "content": content,
            })
        elif role in ("system", "user", "assistant"):
            clean_msg = {"role": role, "content": content}
            # Include tool_calls if present (for assistant messages)
            if role == "assistant" and "tool_calls" in msg:
                clean_msg["tool_calls"] = msg["tool_calls"]
            clean_messages.append(clean_msg)

    payload = {
        "model": _ollama_model,
        "messages": clean_messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }

    if tools:
        payload["tools"] = tools

    try:
        start = time.time()
        print(f"  → Calling Ollama/{_ollama_model}...")

        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120,
        )

        if resp.status_code != 200:
            print(f"  ✗ Ollama HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        msg = data.get("message", {})
        elapsed = time.time() - start

        # Extract performance stats
        eval_count = data.get("eval_count", 0)
        speed = eval_count / elapsed if elapsed > 0 else 0
        print(f"  ✓ Ollama: {eval_count} tokens in {elapsed:.2f}s ({speed:.0f} tok/s)")

        # Build a compatible response object
        class OllamaMessage:
            def __init__(self, content, tool_calls_raw):
                self.content = content
                self.tool_calls = None

                if tool_calls_raw:
                    self.tool_calls = []
                    for i, tc in enumerate(tool_calls_raw):
                        func = tc.get("function", {})
                        self.tool_calls.append(_OllamaToolCall(
                            id=f"ollama_{i}",
                            name=func.get("name", ""),
                            arguments=func.get("arguments", {}),
                        ))

        class _OllamaToolCall:
            def __init__(self, id, name, arguments):
                self.id = id
                self.function = _OllamaFunction(name, arguments)

        class _OllamaFunction:
            def __init__(self, name, arguments):
                self.name = name
                # Ollama returns arguments as dict, Groq returns as JSON string
                self.arguments = json.dumps(arguments) if isinstance(arguments, dict) else arguments

        content = msg.get("content", "")
        tool_calls_raw = msg.get("tool_calls")

        return OllamaMessage(content, tool_calls_raw)

    except requests.ConnectionError:
        print("  ✗ Ollama is not running.")
        return None
    except requests.Timeout:
        print("  ✗ Ollama request timed out (120s)")
        return None
    except Exception as e:
        print(f"  ✗ Ollama error: {e}")
        return None


def ollama_chat_simple(messages, max_tokens=1024, temperature=0.7):
    """
    Simple chat without tool calling (for local model path).
    Returns plain text or None.
    """
    result = ollama_chat(messages, tools=None, max_tokens=max_tokens, temperature=temperature)
    if result:
        return result.content
    return None
