"""
MARK — AI Engine

Orchestrates a turn: retrieve relevant tools, decide whether to act or talk,
produce arguments, execute under policy, and speak the result.

The decision and the arguments are both produced under grammar constraints, so
a malformed tool call is not representable. This replaced an approach that
asked the model to emit JSON in prose and then scraped it with regex — which
failed essentially always, leaving 92 tools unreachable.

Turn shape:
    user text
      -> fast route?            (deterministic, sub-100ms, high confidence only)
      -> pending confirmation?  (yes/no on a sensitive action)
      -> select ~14 candidate tools out of 106
      -> constrained choice: one tool name, or "none"
           none -> stream a conversational reply
           tool -> constrained args -> policy gate -> execute -> stream result
"""

import os
import re
import json
import time
import threading

from core.tool_schemas import TOOLS, TOOL_NAMES, TOOLS_BY_NAME
from core.tool_router import select_tools
from core.tool_executor import run_tool, classify_confirmation, resolve_pending, get_pending
from core import memory_context

# Re-exported for the agent loop and the eval harness.
__all__ = [
    "TOOLS", "get_ai_response", "get_ai_response_streaming", "reset_conversation",
    "get_system_prompt", "set_system_prompt", "get_llm_backend", "set_llm_backend",
    "decide_tool", "build_args",
]

# ─────────────────────────────────────────────
# BACKEND
# ─────────────────────────────────────────────

_llm_backend = "local"
_VALID_BACKENDS = ("local", "ollama")


def get_llm_backend():
    return _llm_backend


def set_llm_backend(backend):
    global _llm_backend
    if backend in _VALID_BACKENDS:
        _llm_backend = backend
        print(f"  🔄 LLM backend set to: {backend}")
        return True
    return False


PRIMARY_MODEL = "gemma-3-4b-it"


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are MARK — Daivik's personal AI companion and system controller. He built you. You're loyal, sharp, and always present. Think of yourself as his closest friend who controls his entire computer.

PERSONALITY: Talk like a REAL HUMAN — warm, casual, natural. Use contractions and small reactions ("got it", "on it", "done"). Call him "sir" naturally, not in every sentence. Keep responses SHORT — one or two sentences unless he asks for detail.

RULES:
- Just act. Don't narrate what you're about to do, and don't ask permission for safe things.
- NEVER paste code or markup into chat — write it to a file with the right tool.
- SPEECH: your words are spoken aloud. No markdown, no bullet points, no emoji, no code. Write the way you'd say it, using "..." for natural pauses.
"""

_prompt_lock = threading.Lock()


def get_system_prompt():
    with _prompt_lock:
        return SYSTEM_PROMPT


def set_system_prompt(new_prompt):
    global SYSTEM_PROMPT
    with _prompt_lock:
        SYSTEM_PROMPT = new_prompt


# ─────────────────────────────────────────────
# CONVERSATION STATE
# ─────────────────────────────────────────────

conversation_history = []
MAX_HISTORY = 20
_history_lock = threading.Lock()


def reset_conversation():
    global conversation_history
    with _history_lock:
        conversation_history = []
    from core.tool_executor import clear_pending
    clear_pending()


def _history_snapshot():
    with _history_lock:
        return list(conversation_history)


def _remember_turn(role, content):
    global conversation_history
    if not content:
        return
    with _history_lock:
        conversation_history.append({"role": role, "content": content})
        if len(conversation_history) > MAX_HISTORY:
            conversation_history = conversation_history[-MAX_HISTORY:]


# ─────────────────────────────────────────────
# PROMPT ASSEMBLY
# ─────────────────────────────────────────────

def _render_tools(tool_schemas):
    """Compact one-line-per-tool rendering. Cheaper than full JSON schema."""
    lines = []
    for tool in tool_schemas:
        fn = tool["function"]
        props = fn.get("parameters", {}).get("properties", {})
        required = set(fn.get("parameters", {}).get("required", []))
        params = ", ".join(f"{k}{'' if k in required else '?'}" for k in props)
        desc = fn.get("description", "").split(". ")[0]
        lines.append(f"- {fn['name']}({params}): {desc}")
    return "\n".join(lines)


def _args_schema(tool_name):
    """JSON Schema for one tool's arguments, used to build the sampler grammar."""
    tool = TOOLS_BY_NAME.get(tool_name)
    if not tool:
        return None
    params = tool["function"].get("parameters", {}) or {}
    props = params.get("properties", {}) or {}
    if not props:
        return None
    return {
        "type": "object",
        "properties": {
            name: {"type": spec.get("type", "string")}
            for name, spec in props.items()
        },
        "required": list(params.get("required", [])),
        "additionalProperties": False,
    }


# ─────────────────────────────────────────────
# STEP 1 — DECIDE
# ─────────────────────────────────────────────

def decide_tool(user_message, history=None, extra_tools=()):
    """
    Choose one tool for this request, or "none" to just talk.

    Returns (tool_name_or_None, candidate_schemas).
    """
    from core.local_llm import local_chat_choice

    candidates = select_tools(user_message, max_tools=14, extra=extra_tools)
    options = [t["function"]["name"] for t in candidates] + ["none"]

    context_lines = ""
    if history:
        recent = history[-4:]
        context_lines = "\n".join(
            f"{'He' if m['role'] == 'user' else 'You'}: {str(m['content'])[:150]}"
            for m in recent
        )
        context_lines = f"Recent conversation:\n{context_lines}\n\n"

    # Stable text first, variable text last. llama.cpp caches the longest
    # matching prompt prefix, so putting the tool block ahead of the user's
    # words lets consecutive turns skip re-evaluating it.
    prompt = (
        "You route requests to tools for a Mac assistant.\n\n"
        "Available tools:\n"
        f"{_render_tools(candidates)}\n\n"
        "RULES\n"
        "1. Match the verb he used. Reading words (show, list, what's in) never "
        "pick a tool that modifies or reorganises anything.\n"
        "2. Answer \"none\" only when no tool applies: small talk, questions "
        "about you, or something you can simply write yourself. An instruction "
        "to do something is never \"none\".\n"
        "3. When two tools fit, pick the more specific one.\n\n"
        "EXAMPLES\n"
        "\"open spotify\" -> open_app          (launch it; no song named)\n"
        "\"play some jazz\" -> play_music      (music, not an app)\n"
        "\"what's in my downloads\" -> list_directory   (read, not reorganise)\n"
        "\"tidy my downloads\" -> organize_downloads\n"
        "\"activate coding mode\" -> run_routine        (an instruction)\n"
        "\"what can you do\" -> none           (about you, not a task)\n"
        "\"tell me a joke\" -> none            (you can write it yourself)\n"
        "\"what's my wifi password\" -> rag_recall      (he told you before)\n\n"
        "Reply with the tool name only.\n\n"
        f"{context_lines}"
        f"His request: \"{user_message}\"\n"
        "Tool:"
    )

    choice = local_chat_choice([{"role": "user", "content": prompt}], options)
    if not choice or choice == "none":
        return None, candidates
    return choice, candidates


# ─────────────────────────────────────────────
# STEP 2 — ARGUMENTS
# ─────────────────────────────────────────────

def build_args(tool_name, user_message, history=None):
    """
    Produce arguments for `tool_name`, constrained to its JSON schema.
    Returns a dict (possibly empty for zero-argument tools).
    """
    from core.local_llm import local_chat_json

    schema = _args_schema(tool_name)
    if not schema:
        return {}

    tool = TOOLS_BY_NAME[tool_name]
    fn = tool["function"]
    props = fn.get("parameters", {}).get("properties", {})
    param_help = "\n".join(
        f"  {name}: {spec.get('description', '')}" for name, spec in props.items()
    )

    context_lines = ""
    if history:
        recent = history[-2:]
        context_lines = "\n".join(
            f"{'He' if m['role'] == 'user' else 'You'}: {str(m['content'])[:150]}"
            for m in recent
        )
        context_lines = f"Recent conversation (for resolving 'it', 'that', 'him'):\n{context_lines}\n\n"

    prompt = (
        f"{context_lines}"
        f"His request: \"{user_message}\"\n\n"
        f"You are calling the tool: {tool_name}\n"
        f"{fn.get('description', '')}\n\n"
        f"Parameters:\n{param_help}\n\n"
        "Extract the parameter values from his request. Use exactly what he "
        "said — do not invent paths, names or values he did not mention.\n"
        "This is a Mac. Paths look like ~/Desktop/notes.txt or "
        "~/Documents/work — never C:\\ and never a placeholder username.\n"
        "Reply with JSON only."
    )

    args = local_chat_json([{"role": "user", "content": prompt}], schema, max_tokens=320)
    if not isinstance(args, dict):
        return {}

    # Drop empty optionals so tool defaults apply.
    return {k: v for k, v in args.items() if v not in ("", None)}


# ─────────────────────────────────────────────
# STEP 3 — SPEAK
# ─────────────────────────────────────────────

# Tools whose output is an inventory to be summarised rather than an answer to
# be extracted.
_INVENTORY_TOOLS = {
    "list_windows", "get_open_windows", "list_directory", "search_files",
    "get_clipboard_history", "search_clipboard", "list_recent_actions",
    "list_undoable", "rag_list", "list_memories", "list_reminders",
    "list_routines", "list_iot_devices", "mcp_list_tools", "mcp_status",
    "list_ollama_models", "get_system_stats", "get_system_info",
    "vision_describe", "search_content",
}


def _speak_prompt(user_message, memories, history, tool_name=None, tool_result=None):
    """Build the message list for the model's spoken reply."""
    system = get_system_prompt() + memories

    messages = [{"role": "system", "content": system}]
    for msg in (history or [])[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    if tool_name:
        result_text = str(tool_result)

        # Distinguish inventories from ranked answers *by tool*, not by shape.
        # Both are multi-line, but they need opposite treatment: summarising an
        # audit log is right, while summarising rag_recall buries the answer —
        # its first row is the match the user actually asked for.
        is_listing = (
            tool_name.startswith("list_")
            or tool_name in _INVENTORY_TOOLS
        )

        if is_listing:
            instruction = (
                "Summarise this for him in one or two short spoken sentences — "
                "how many things there are and what the notable ones are. Do "
                "not read the list out item by item, and do not present a "
                "single entry as though it were the whole answer."
            )
        else:
            instruction = (
                "Reply in one short spoken sentence. If the result contains "
                "something he asked for, just tell him the answer — do not "
                "describe looking it up."
            )

        messages.append({
            "role": "user",
            "content": (
                f"{user_message}\n\n"
                f"[Result:\n{result_text[:1400]}]\n\n"
                f"{instruction} Never name a tool, never say you 'ran' or "
                "'called' anything, and do not wrap your reply in quotation marks."
            ),
        })
    else:
        messages.append({"role": "user", "content": user_message})

    return messages


_JSON_JUNK = re.compile(r'\{\s*"(?:tool|args|name)".*?\}', re.DOTALL)
_TOOLCALL_JUNK = re.compile(r'\b\w+\(\s*(?:\w+\s*[:=]|["\']).*?\)', re.DOTALL)
_FENCE = re.compile(r"```[\s\S]*?```")


# Small models narrate their own plumbing ("I just ran rag_remember"). Strip it
# rather than relying on the prompt alone, since it only takes one slip to make
# the spoken output sound like a debug log.
_TOOL_NARRATION = re.compile(
    r"\b(?:i\s+)?(?:just\s+)?(?:ran|called|used|executed|invoked|triggered)\s+"
    r"(?:the\s+)?[a-z_]{3,}(?:\s+tool)?\b[,.]?\s*", re.I,
)
_TOOL_NAME_WORD = re.compile(
    r"\b(?:rag[_ ]?(?:remember|recall|forget|list|stats)|save[_ ]?memory|"
    r"recall[_ ]?memory|run[_ ]?terminal|write[_ ]?file|read[_ ]?file|"
    r"open[_ ]?app|web[_ ]?search|set[_ ]?volume|analyze[_ ]?screen)\b", re.I,
)


def _clean_response(text):
    """Strip anything that would sound wrong when spoken aloud."""
    if not text:
        return "Done, sir."
    text = _FENCE.sub("", text)
    text = _JSON_JUNK.sub("", text)
    text = _TOOLCALL_JUNK.sub("", text)
    text = _TOOL_NARRATION.sub("", text)
    text = _TOOL_NAME_WORD.sub("that", text)
    text = re.sub(r"[*_#`]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    # Models often wrap the whole spoken line in quotes; TTS reads those aloud
    # as a pause and they look wrong in the transcript.
    if len(text) > 1 and text[0] in "\"'“‘" and text[-1] in "\"'”’":
        text = text[1:-1].strip()

    text = text.lstrip("—–- ").strip()

    # Removing a narration clause can leave the sentence starting on a
    # conjunction ("and your colour is teal").
    text = re.sub(r"^(?:and|but|so|then|also)\s+", "", text, flags=re.I).strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text or "Done, sir."


# ─────────────────────────────────────────────
# PUBLIC ENTRY POINTS
# ─────────────────────────────────────────────

def get_ai_response(user_message):
    """Blocking turn. Returns {"text": str, "tool_calls": list|None}."""
    text_parts = []
    tool_calls = None
    for event in get_ai_response_streaming(user_message):
        if event["type"] == "done":
            return {"text": event["text"], "tool_calls": event.get("tool_calls")}
        if event["type"] == "sentence":
            text_parts.append(event["text"])
    return {"text": " ".join(text_parts).strip(), "tool_calls": tool_calls}


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|(?<=[.!?…])$|\n")


def _reply_stream(messages, max_tokens, temperature):
    """
    Pick the generator for the spoken reply.

    Routing and argument extraction always stay on the local model — they
    depend on grammar-constrained sampling, which is a llama.cpp feature. Only
    the free-form reply can be handed to a bigger model via Ollama, so that is
    the only thing this switches.
    """
    from core.local_llm import local_chat_stream

    if _llm_backend == "ollama":
        try:
            from core.ollama_engine import check_ollama, ollama_chat_simple
            if check_ollama().get("status") == "running":
                text = ollama_chat_simple(messages, max_tokens=max_tokens,
                                          temperature=temperature)
                if text:
                    # Ollama's non-streaming path: emit it as one block so the
                    # sentence splitter downstream still works.
                    yield text
                    return
        except Exception as e:
            print(f"  ⚠ Ollama unavailable ({e}) — falling back to local")

    yield from local_chat_stream(messages, max_tokens=max_tokens, temperature=temperature)


def _stream_sentences(messages, max_tokens=320, temperature=0.7):
    """
    Run a streaming completion, yielding whole sentences.

    Sentences (not tokens) are the unit because the TTS layer synthesises per
    sentence — emitting partial clauses would produce chopped-up speech.
    """
    buffer = ""
    full = ""
    for delta in _reply_stream(messages, max_tokens, temperature):
        buffer += delta
        full += delta
        while True:
            match = _SENTENCE_END.search(buffer)
            if not match:
                break
            sentence = buffer[:match.end()].strip()
            buffer = buffer[match.end():]
            cleaned = _clean_response(sentence)
            if cleaned and cleaned != "Done, sir.":
                yield "sentence", cleaned
    tail = _clean_response(buffer)
    if tail and tail != "Done, sir.":
        yield "sentence", tail
    yield "full", _clean_response(full)


def get_ai_response_streaming(user_message):
    """
    Streaming turn.

    Yields:
      {"type": "tool",     "name": str, "result": str}
      {"type": "sentence", "text": str}                 — speak this now
      {"type": "done",     "text": str, "tool_calls": list|None}
    """
    user_message = (user_message or "").strip()
    if not user_message:
        yield {"type": "done", "text": "", "tool_calls": None}
        return

    start = time.time()
    history = _history_snapshot()

    # ── Pending confirmation for a sensitive action ──
    if get_pending():
        decision = classify_confirmation(user_message)
        if decision:
            text, calls = resolve_pending(decision)
            _remember_turn("user", user_message)
            _remember_turn("assistant", text)
            yield {"type": "sentence", "text": text}
            yield {"type": "done", "text": text, "tool_calls": calls}
            return

    _remember_turn("user", user_message)

    # Capture personal facts stated in passing.
    memory_context.capture(user_message)
    memories = memory_context.as_prompt_block(user_message)

    # ── Decide ──
    tool_name, _ = decide_tool(user_message, history)

    tool_calls = None
    tool_result = None

    if tool_name:
        args = build_args(tool_name, user_message, history)
        print(f"  🛠️  {tool_name}({json.dumps(args, default=str)[:120]})")
        tool_result = run_tool(tool_name, args)
        tool_calls = [{"name": tool_name, "args": args, "result": tool_result}]
        yield {"type": "tool", "name": tool_name, "result": tool_result}

        # A parked sensitive action must reach the user verbatim. Handing it to
        # the model to paraphrase produced "Yes, go ahead." — which reads as
        # MARK approving its own request, the exact opposite of what happened.
        if get_pending():
            _remember_turn("assistant", tool_result)
            yield {"type": "sentence", "text": tool_result}
            yield {"type": "done", "text": tool_result, "tool_calls": tool_calls}
            return

    messages = _speak_prompt(user_message, memories, history, tool_name, tool_result)

    full_text = ""
    for kind, payload in _stream_sentences(messages, max_tokens=320 if not tool_name else 220):
        if kind == "sentence":
            yield {"type": "sentence", "text": payload}
        else:
            full_text = payload

    # If the model produced nothing usable, fall back to the raw tool result;
    # with no tool either, say so plainly rather than emitting a cheerful
    # "Done, sir." for work that did not happen.
    if not full_text or full_text == "Done, sir.":
        if tool_result:
            full_text = _clean_response(tool_result)
        else:
            from core.local_llm import get_model_status
            status = get_model_status().get("status")
            full_text = ("The model's still warming up, sir — give me a second."
                         if status in ("loading", "downloading", "unloaded")
                         else "I couldn't put a reply together just then, sir. Try me again?")
            yield {"type": "sentence", "text": full_text}

    _remember_turn("assistant", full_text)
    print(f"  🤖 MARK: {full_text[:90]} ({time.time() - start:.2f}s)")

    yield {"type": "done", "text": full_text, "tool_calls": tool_calls}
