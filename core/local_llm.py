"""
MARK — Local LLM Engine

Gemma 3 4B-IT on Metal GPU via llama-cpp-python. No cloud, no Ollama required.

What this module guarantees for the layers above it:
  * a large context window (32k by default, the model trains at 131k)
  * prompt-prefix KV caching, so the system prompt is not re-evaluated every turn
  * true token streaming
  * grammar-constrained generation, so structured output cannot be malformed
  * optional real multimodal vision when the projector file is present
"""

import os
import json
import time
import logging
import threading
import contextlib


def _quiet_llama_cpp():
    """
    Silence llama.cpp's own stderr chatter.

    `verbose=False` on the Llama constructor covers most of it, but backend
    initialisation logs through ggml's global callback before any model exists,
    so those lines have to be gated at the logger. Errors still come through.
    """
    try:
        import llama_cpp._logger  # installs the callback as a side effect
        logging.getLogger("llama-cpp-python").setLevel(logging.ERROR)
    except Exception:
        pass


_quiet_llama_cpp()


@contextlib.contextmanager
def _silenced_stderr():
    """Temporarily route file descriptor 2 to /dev/null."""
    try:
        saved = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
    except Exception:
        yield
        return
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        try:
            os.dup2(saved, 2)
        finally:
            os.close(devnull)
            os.close(saved)


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

MODEL_REPO = "bartowski/google_gemma-3-4b-it-GGUF"
MODEL_FILE = "google_gemma-3-4b-it-Q4_K_M.gguf"
MMPROJ_FILE = "mmproj-google_gemma-3-4b-it-f16.gguf"
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

# The model trains at 131k, but the KV cache is what actually costs memory, and
# MARK's prompts are small by construction: the tool router keeps a turn near
# ~600 tokens, and even a long agent transcript stays a few thousand. 16k is
# four times what the workload needs while leaving plenty of headroom on a
# machine that is also running everything else the user has open.
#
# This matters in practice: at 32k, a second process loading the model on a
# busy machine pushed allocation over the edge and llama_decode started
# returning -3 mid-conversation.
N_CTX = int(os.getenv("MARK_N_CTX", "16384"))
N_THREADS = int(os.getenv("MARK_N_THREADS", "6"))

_model = None
_vision_model = None
_model_lock = threading.RLock()
_vision_lock = threading.RLock()
_model_status = "unloaded"      # unloaded | downloading | loading | ready | error
_status_message = ""
_vision_status = "unloaded"

# Generation must be serialised — one llama.cpp context cannot decode two
# requests concurrently, and the server calls this from a thread pool.
_gen_lock = threading.RLock()


def get_model_status():
    return {"status": _model_status, "message": _status_message, "vision": _vision_status}


def _model_path(filename=MODEL_FILE):
    return os.path.join(MODELS_DIR, filename)


def _download(filename, required=True):
    """Fetch a GGUF from Hugging Face if it is not already on disk."""
    global _model_status, _status_message
    path = _model_path(filename)
    if os.path.exists(path):
        return path

    if required:
        _model_status = "downloading"
        _status_message = f"Downloading {filename}..."
        print(f"  ↓ {_status_message}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
        return hf_hub_download(repo_id=MODEL_REPO, filename=filename, local_dir=MODELS_DIR)
    except Exception as e:
        if required:
            _model_status = "error"
            _status_message = f"Download failed: {e}"
            print(f"  ✗ {_status_message}")
        return None


def load_model():
    """Load the text model. Thread-safe singleton."""
    global _model, _model_status, _status_message

    with _model_lock:
        if _model is not None:
            return _model

        path = _download(MODEL_FILE)
        if not path:
            return None

        _model_status = "loading"
        _status_message = "Loading Gemma 3 4B onto the GPU..."
        print(f"  ⏳ {_status_message}")

        try:
            from llama_cpp import Llama
            from llama_cpp.llama_cache import LlamaRAMCache

            start = time.time()
            # A couple of ggml notices are written straight to fd 2 during
            # context creation, below the Python logger. Redirect the fd for
            # the duration of the load so startup output stays clean.
            with _silenced_stderr():
                _model = Llama(
                    model_path=path,
                    n_ctx=N_CTX,
                    n_gpu_layers=-1,      # every layer on Metal
                    n_threads=N_THREADS,
                    n_batch=512,
                    verbose=False,
                    use_mlock=True,
                )
            # Prompt-prefix cache. The system prompt and tool block are stable
            # across turns, so this removes most of the per-turn prefill cost.
            _model.set_cache(LlamaRAMCache(capacity_bytes=(1 << 30)))

            elapsed = time.time() - start
            _model_status = "ready"
            _status_message = f"Gemma 3 4B ready — {N_CTX // 1024}k context ({elapsed:.1f}s load)"
            print(f"  ✓ {_status_message}")
            return _model

        except Exception as e:
            _model_status = "error"
            _status_message = f"Load failed: {e}"
            print(f"  ✗ {_status_message}")
            return None


def unload_model():
    global _model, _model_status, _status_message
    with _model_lock:
        _model = None
        _model_status = "unloaded"
        _status_message = "Model unloaded"


def has_vision_projector():
    return os.path.exists(_model_path(MMPROJ_FILE))


def vision_model_enabled():
    """
    Whether to load the second, image-capable context.

    Off by default, deliberately. Holding two llama.cpp contexts on the same
    Metal device trips a GGML resource-set assertion when the process exits —
    an abort on shutdown, every time. Since the native path (accessibility tree
    + Apple's Vision OCR + the text model) answers screen questions well and
    costs no extra memory, that is the default, and this stays available for
    anyone who explicitly wants image reasoning.

    Enable with:  MARK_VISION_MODEL=1
    """
    return os.getenv("MARK_VISION_MODEL", "0").lower() in ("1", "true", "yes")


def load_vision_model():
    """
    Load a second context with the multimodal projector attached.

    Returns None when disabled, when the projector is missing, or on any load
    failure — callers fall back to the native macOS path, which always works.
    """
    global _vision_model, _vision_status

    if not vision_model_enabled():
        _vision_status = "disabled"
        return None

    with _vision_lock:
        if _vision_model is not None:
            return _vision_model
        if _vision_status == "unsupported":
            return None

        mmproj = _model_path(MMPROJ_FILE)
        if not os.path.exists(mmproj):
            mmproj = _download(MMPROJ_FILE, required=False)
        if not mmproj or not os.path.exists(mmproj):
            _vision_status = "unsupported"
            return None

        path = _model_path(MODEL_FILE)
        if not os.path.exists(path):
            _vision_status = "unsupported"
            return None

        try:
            from llama_cpp import Llama
            from core.gemma_vision import Gemma3ChatHandler

            print("  ⏳ Loading Gemma 3 vision projector...")
            start = time.time()
            handler = Gemma3ChatHandler(clip_model_path=mmproj, verbose=False)
            _vision_model = Llama(
                model_path=path,
                chat_handler=handler,
                n_ctx=int(os.getenv("MARK_VISION_CTX", "8192")),
                n_gpu_layers=-1,
                n_threads=N_THREADS,
                n_batch=512,
                verbose=False,
            )
            _vision_status = "ready"
            print(f"  ✓ Vision model ready ({time.time() - start:.1f}s)")
            return _vision_model
        except Exception as e:
            print(f"  ⚠ Vision model unavailable ({e}) — using native macOS vision instead")
            _vision_status = "unsupported"
            _vision_model = None
            return None


# ─────────────────────────────────────────────
# MESSAGE FORMATTING
# ─────────────────────────────────────────────

def _format_messages_for_gemma(messages):
    """
    Convert OpenAI-style messages into something Gemma's template accepts.

    Gemma has no system role and requires strictly alternating user/assistant
    turns. So: fold the system message into the first user turn, render tool
    results as user turns, and merge any consecutive same-role turns rather
    than dropping them — dropping them is what silently destroyed multi-turn
    memory in the previous implementation.
    """
    system_text = ""
    staged = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            staged.append({"role": "user" if role != "assistant" else "assistant",
                           "content": content})
            continue
        if not content.strip():
            continue

        if role == "system":
            system_text = f"{system_text}\n\n{content}".strip() if system_text else content
        elif role == "tool":
            staged.append({"role": "user", "content": f"[tool result]\n{content}"})
        elif role == "assistant":
            staged.append({"role": "assistant", "content": content})
        else:
            staged.append({"role": "user", "content": content})

    # Merge consecutive same-role turns.
    merged = []
    for msg in staged:
        if merged and merged[-1]["role"] == msg["role"] \
                and isinstance(merged[-1]["content"], str) and isinstance(msg["content"], str):
            merged[-1]["content"] += "\n\n" + msg["content"]
        else:
            merged.append(dict(msg))

    # Gemma must open on a user turn.
    while merged and merged[0]["role"] == "assistant":
        merged.pop(0)

    if system_text:
        if merged and merged[0]["role"] == "user" and isinstance(merged[0]["content"], str):
            merged[0]["content"] = f"{system_text}\n\n{merged[0]['content']}"
        else:
            merged.insert(0, {"role": "user", "content": system_text})

    if not merged:
        merged = [{"role": "user", "content": system_text or "Hello"}]

    return merged


def _clamp_tokens(model, messages, max_tokens):
    """
    Never ask for more output tokens than the context can actually hold.

    This is what used to make code generation fail silently: agents asked for
    4096 output tokens inside a 4096-token window, leaving zero room for input.
    """
    try:
        approx_prompt = sum(len(str(m.get("content", ""))) for m in messages) // 3
        headroom = N_CTX - approx_prompt - 256
        if headroom < 128:
            headroom = 128
        return max(64, min(int(max_tokens), headroom))
    except Exception:
        return max_tokens


# ─────────────────────────────────────────────
# GENERATION
# ─────────────────────────────────────────────

def local_chat(messages, max_tokens=1024, temperature=0.7, grammar=None, stop=None):
    """
    Blocking completion. Returns the response text, or None on error.

    `grammar` may be a LlamaGrammar instance to constrain the output shape.
    """
    model = load_model()
    if model is None:
        return None

    formatted = _format_messages_for_gemma(messages)
    max_tokens = _clamp_tokens(model, formatted, max_tokens)

    try:
        with _gen_lock:
            start = time.time()
            response = model.create_chat_completion(
                messages=formatted,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                repeat_penalty=1.1,
                grammar=grammar,
                stop=stop or [],
            )
            elapsed = time.time() - start

        text = response["choices"][0]["message"]["content"]
        used = response.get("usage", {}).get("completion_tokens", 0)
        speed = used / elapsed if elapsed > 0 else 0
        print(f"  ⚡ Local LLM: {used} tok in {elapsed:.2f}s ({speed:.0f} tok/s)")
        return text

    except Exception as e:
        # -3 from llama_decode means the KV cache could not be allocated,
        # which on this platform means memory pressure rather than a bad
        # prompt. Dropping the prompt cache frees a meaningful chunk and
        # usually lets the retry through.
        if "-3" in str(e):
            print("  ⚠ Decode failed under memory pressure — clearing cache and retrying")
            try:
                with _model_lock:
                    if _model is not None:
                        _model.reset()
                        from llama_cpp.llama_cache import LlamaRAMCache
                        _model.set_cache(LlamaRAMCache(capacity_bytes=(1 << 28)))
                with _gen_lock:
                    response = model.create_chat_completion(
                        messages=formatted,
                        max_tokens=min(max_tokens, 256),
                        temperature=temperature,
                        top_p=0.9,
                        repeat_penalty=1.1,
                        grammar=grammar,
                        stop=stop or [],
                    )
                return response["choices"][0]["message"]["content"]
            except Exception as retry_error:
                print(f"  ✗ Retry also failed: {retry_error}")
                return None

        print(f"  ✗ Local LLM error: {e}")
        return None


def local_chat_stream(messages, max_tokens=1024, temperature=0.7, stop=None):
    """
    Streaming completion. Yields text deltas as the model produces them.

    This is what makes the sentence-level TTS pipeline actually fire — the
    previous implementation only pretended to stream.
    """
    model = load_model()
    if model is None:
        return

    formatted = _format_messages_for_gemma(messages)
    max_tokens = _clamp_tokens(model, formatted, max_tokens)

    try:
        with _gen_lock:
            start = time.time()
            count = 0
            stream = model.create_chat_completion(
                messages=formatted,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                repeat_penalty=1.1,
                stop=stop or [],
                stream=True,
            )
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {})
                piece = delta.get("content")
                if piece:
                    count += 1
                    yield piece
            elapsed = time.time() - start
            speed = count / elapsed if elapsed > 0 else 0
            print(f"  ⚡ Local LLM (stream): {count} tok in {elapsed:.2f}s ({speed:.0f} tok/s)")

    except Exception as e:
        print(f"  ✗ Local LLM stream error: {e}")


def local_chat_json(messages, schema, max_tokens=384, temperature=0.2):
    """
    Generate output constrained to a JSON Schema.

    llama.cpp compiles the schema into a GBNF grammar and masks the sampler, so
    the result is guaranteed to parse. This is the mechanism that replaced
    regex-scraping the model's prose for tool calls.

    Returns a parsed Python object, or None.
    """
    model = load_model()
    if model is None:
        return None

    try:
        from llama_cpp import LlamaGrammar
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False)
    except Exception as e:
        print(f"  ✗ Grammar compile error: {e}")
        return None

    text = local_chat(messages, max_tokens=max_tokens, temperature=temperature, grammar=grammar)
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # The grammar makes this near-impossible, but a truncated generation
        # (hitting max_tokens mid-object) can still land here.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        print(f"  ✗ Constrained output did not parse: {text[:120]}")
        return None


def local_chat_choice(messages, options, max_tokens=24):
    """
    Force the model to pick exactly one string from `options`.

    Used for tool routing: rather than hoping the model emits parseable JSON in
    free text, the sampler is restricted so that no other answer is
    representable. Returns the chosen option, or None.
    """
    model = load_model()
    if model is None or not options:
        return None

    try:
        from llama_cpp import LlamaGrammar
        alts = " | ".join(json.dumps(o) for o in options)
        grammar = LlamaGrammar.from_string(f"root ::= {alts}", verbose=False)
    except Exception as e:
        print(f"  ✗ Choice grammar error: {e}")
        return None

    text = local_chat(messages, max_tokens=max_tokens, temperature=0.0, grammar=grammar)
    if not text:
        return None

    text = text.strip().strip('"').strip()
    if text in options:
        return text
    for o in options:
        if o in text:
            return o
    return None


def vision_chat(image_path, prompt, max_tokens=512, temperature=0.3):
    """
    Ask the multimodal model about an image. Returns text, or None if the
    vision path is unavailable (callers then use the native macOS fallback).
    """
    model = load_vision_model()
    if model is None:
        return None

    import base64
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        with _vision_lock:
            resp = model.create_chat_completion(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ✗ Vision chat error: {e}")
        return None
