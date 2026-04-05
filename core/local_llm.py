"""
MARK — Local LLM Engine
Run Gemma 2 2B-IT locally with llama-cpp-python + Metal GPU.
No cloud APIs, no Ollama, full privacy.
"""

import os
import json
import time
import threading
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

MODEL_REPO  = "bartowski/gemma-2-2b-it-GGUF"
MODEL_FILE  = "gemma-2-2b-it-Q4_K_M.gguf"
MODELS_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

# Runtime state
_model = None
_model_lock = threading.Lock()
_model_status = "unloaded"  # unloaded, downloading, loading, ready, error
_status_message = ""


def get_model_status():
    """Get current model status for UI."""
    return {"status": _model_status, "message": _status_message}


def _get_model_path():
    """Get expected path of the GGUF model file."""
    return os.path.join(MODELS_DIR, MODEL_FILE)


def _download_model():
    """Download the GGUF model from Hugging Face if not already cached."""
    global _model_status, _status_message

    model_path = _get_model_path()
    if os.path.exists(model_path):
        print(f"  ✓ Model already cached: {model_path}")
        return model_path

    _model_status = "downloading"
    _status_message = f"Downloading {MODEL_FILE} (~1.5 GB)..."
    print(f"  ↓ {_status_message}")

    os.makedirs(MODELS_DIR, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir=MODELS_DIR,
        )
        print(f"  ✓ Model downloaded: {path}")
        return path
    except Exception as e:
        _model_status = "error"
        _status_message = f"Download failed: {e}"
        print(f"  ✗ {_status_message}")
        return None


def load_model():
    """Load the model into memory. Thread-safe, singleton pattern."""
    global _model, _model_status, _status_message

    with _model_lock:
        if _model is not None:
            return _model

        model_path = _download_model()
        if not model_path:
            return None

        _model_status = "loading"
        _status_message = "Loading Gemma 2 2B into GPU memory..."
        print(f"  ⏳ {_status_message}")

        try:
            from llama_cpp import Llama

            start = time.time()
            _model = Llama(
                model_path=model_path,
                n_ctx=4096,          # Context window
                n_gpu_layers=-1,     # ALL layers on Metal GPU
                n_threads=6,         # M4 performance cores
                n_batch=512,         # Batch size for prompt processing
                verbose=False,       # Quiet — no llama.cpp spam
                use_mlock=True,      # Lock model in RAM to prevent swap
            )
            elapsed = time.time() - start

            _model_status = "ready"
            _status_message = f"Gemma 2 2B ready ({elapsed:.1f}s load)"
            print(f"  ✓ {_status_message}")
            return _model

        except Exception as e:
            _model_status = "error"
            _status_message = f"Load failed: {e}"
            print(f"  ✗ {_status_message}")
            return None


def unload_model():
    """Unload model from memory."""
    global _model, _model_status, _status_message
    with _model_lock:
        _model = None
        _model_status = "unloaded"
        _status_message = "Model unloaded"
        print("  🔻 Model unloaded from memory")


def _format_messages_for_gemma(messages):
    """
    Convert OpenAI-style messages to Gemma 2 chat format.
    Gemma 2 does NOT support the 'system' role — we fold any system
    message into the first user turn as a context prefix.
    """
    formatted = []
    system_text = ""

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue

        if role == "system":
            # Collect system content to prepend to first user message
            system_text = content
        elif role == "user":
            if system_text:
                # Prepend system context to the first user message
                content = f"{system_text}\n\n{content}"
                system_text = ""  # Only prepend once
            formatted.append({"role": "user", "content": content})
        elif role == "assistant":
            formatted.append({"role": "assistant", "content": content})
        # Skip 'tool' roles — local model doesn't handle them natively

    # Edge case: only a system message with no user messages
    if system_text and not formatted:
        formatted.append({"role": "user", "content": system_text})

    return formatted


def local_chat(messages, max_tokens=1024, temperature=0.7):
    """
    Run inference on local Gemma 2 2B-IT.

    Args:
        messages: OpenAI-style message list
        max_tokens: Max response tokens
        temperature: Sampling temperature

    Returns:
        str: Model response text, or None on error
    """
    model = load_model()
    if model is None:
        return None

    try:
        formatted = _format_messages_for_gemma(messages)

        start = time.time()
        response = model.create_chat_completion(
            messages=formatted,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            repeat_penalty=1.1,
        )
        elapsed = time.time() - start

        text = response["choices"][0]["message"]["content"]
        tokens = response.get("usage", {})
        comp_tokens = tokens.get("completion_tokens", 0)
        speed = comp_tokens / elapsed if elapsed > 0 else 0

        print(f"  ⚡ Local LLM: {comp_tokens} tokens in {elapsed:.2f}s ({speed:.0f} tok/s)")
        return text

    except Exception as e:
        print(f"  ✗ Local LLM error: {e}")
        return None
