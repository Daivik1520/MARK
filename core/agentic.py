"""
MARK — Agent Loop (Plan → Act → Verify → Reflect)

Multi-step autonomous execution for requests that a single tool call cannot
satisfy ("download the report, summarise it, and save the summary to my desk").

Two things make this different from the previous implementation:

  * It speaks the same constrained-decoding protocol as the chat path. There
    used to be two incompatible tool syntaxes — free-text `TOOL_CALL: name({})`
    here and JSON over there — so fixing one never fixed the other.

  * Each step observes the actual tool output before choosing the next one,
    and the loop ends when the model says it is finished rather than when a
    regex stops matching.
"""

import re
import time
import json
import hashlib

from core.tool_schemas import TOOLS_BY_NAME
from core.tool_router import select_tools
from core.tool_executor import run_tool

DONE = "task_complete"

# Requests with several dependent actions. Deliberately narrower than the old
# trigger list, which fired on bare words like "next" and "first".
_MULTI_STEP = re.compile(
    r"\b(?:and then|after that|once (?:that|you)|followed by|"
    r"step by step|for each|one by one|"
    r"then (?:save|send|open|write|move|delete|summar|upload|run|copy)\w*)\b",
    re.I,
)
_PROJECT_SCALE = re.compile(
    r"\b(?:set up (?:a|an|my)|create a (?:project|repo|repository)|"
    r"build me (?:a|an)|scaffold|bootstrap (?:a|an)|"
    r"download and|research .{0,40} and (?:write|save|summar))\b",
    re.I,
)


def should_use_agent(text):
    """Heuristic gate: is this a genuine multi-step task?"""
    if not text:
        return False
    if _MULTI_STEP.search(text) or _PROJECT_SCALE.search(text):
        return True
    # Three or more imperative clauses chained with commas/and.
    clauses = [c for c in re.split(r",|\band\b", text, flags=re.I) if c.strip()]
    if len(clauses) >= 3:
        verbs = sum(
            1 for c in clauses
            if re.match(r"\s*(?:open|create|write|save|send|move|delete|run|search|"
                        r"download|install|summar|copy|make|build|find)\w*\b", c.strip(), re.I)
        )
        return verbs >= 2
    return False


# ─────────────────────────────────────────────
# PLANNING
# ─────────────────────────────────────────────

def get_agentic_plan(task):
    """Produce a numbered plan without executing anything."""
    from core.local_llm import local_chat

    candidates = select_tools(task, max_tools=18)
    names = ", ".join(t["function"]["name"] for t in candidates)

    prompt = (
        "You plan tasks for a Mac assistant.\n"
        f"Tools you may use: {names}\n\n"
        f"Task: {task}\n\n"
        "Write a short numbered plan. One line per step, naming the tool and "
        "what it does. Maximum six steps. Do not execute anything."
    )
    result = local_chat([{"role": "user", "content": prompt}],
                        max_tokens=400, temperature=0.3)
    return result or "Could not generate a plan."


# ─────────────────────────────────────────────
# THE LOOP
# ─────────────────────────────────────────────

def _choose_step(task, transcript, used_tools):
    """Pick the next tool (or DONE), constrained to real tool names."""
    from core.local_llm import local_chat_choice

    query = task + " " + " ".join(used_tools)
    candidates = select_tools(query, max_tools=16, extra=used_tools)
    options = [t["function"]["name"] for t in candidates] + [DONE]

    lines = []
    for tool in candidates:
        fn = tool["function"]
        lines.append(f"- {fn['name']}: {fn.get('description', '').split('. ')[0]}")

    history = "\n".join(transcript[-8:]) if transcript else "(nothing yet)"

    prompt = (
        "You are executing a multi-step task on a Mac, one tool at a time.\n\n"
        "Tools:\n" + "\n".join(lines) + "\n\n"
        f"Choose \"{DONE}\" when the task is fully accomplished, or when the "
        "remaining work cannot be done with these tools.\n"
        "Reply with one tool name only.\n\n"
        f"TASK: {task}\n\n"
        f"WHAT HAS HAPPENED SO FAR:\n{history}\n\n"
        "Next tool:"
    )

    choice = local_chat_choice([{"role": "user", "content": prompt}], options)
    return choice or DONE


def _build_step_args(tool_name, task, transcript):
    """Constrained argument generation for one step."""
    from core.local_llm import local_chat_json

    tool = TOOLS_BY_NAME.get(tool_name)
    if not tool:
        return {}
    params = tool["function"].get("parameters", {}) or {}
    props = params.get("properties", {}) or {}
    if not props:
        return {}

    schema = {
        "type": "object",
        "properties": {k: {"type": v.get("type", "string")} for k, v in props.items()},
        "required": list(params.get("required", [])),
        "additionalProperties": False,
    }
    param_help = "\n".join(f"  {k}: {v.get('description','')}" for k, v in props.items())
    history = "\n".join(transcript[-6:]) if transcript else "(nothing yet)"

    prompt = (
        f"TASK: {task}\n\n"
        f"PROGRESS SO FAR:\n{history}\n\n"
        f"You are now calling: {tool_name}\n"
        f"{tool['function'].get('description','')}\n\n"
        f"Parameters:\n{param_help}\n\n"
        "Give the parameter values for this step. Use real values from the task "
        "and from what previous steps returned.\n"
        "This is a Mac. Paths look like ~/Desktop/notes.txt or ~/Documents/work "
        "— never C:\\ and never a placeholder username.\n"
        "Reply with JSON only."
    )
    args = local_chat_json([{"role": "user", "content": prompt}], schema, max_tokens=320)
    if not isinstance(args, dict):
        return {}
    return {k: v for k, v in args.items() if v not in ("", None)}


def run_agentic_task(task, max_steps=10, on_step=None, allow_sensitive=False):
    """
    Execute a multi-step task.

    allow_sensitive — when False (the default), sensitive tools still require
    the user's confirmation, and the loop stops to ask rather than pushing on.

    Returns a dict with text, steps, tool_calls, completed, total_time,
    step_count.
    """
    start = time.time()
    transcript = []
    steps = []
    all_calls = []
    used_tools = []
    seen = []
    completed = False
    final_text = ""

    for step_num in range(1, max_steps + 1):
        tool_name = _choose_step(task, transcript, used_tools)

        if tool_name == DONE:
            completed = True
            break

        args = _build_step_args(tool_name, task, transcript)

        # Loop guard — identical call three times means we are stuck.
        sig = (tool_name, hashlib.md5(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest())
        if seen.count(sig) >= 2:
            transcript.append(f"Step {step_num}: {tool_name} repeated with identical arguments — stopping.")
            break
        seen.append(sig)

        print(f"  🔧 Step {step_num}: {tool_name}({json.dumps(args, default=str)[:100]})")
        result = run_tool(tool_name, args, allow_sensitive=allow_sensitive)
        result_str = str(result)
        print(f"     → {result_str[:100]}")

        if tool_name not in used_tools:
            used_tools.append(tool_name)

        transcript.append(f"Step {step_num}: {tool_name}({json.dumps(args, default=str)[:120]}) → {result_str[:300]}")

        record = {
            "step": step_num,
            "tool_calls": [{"name": tool_name, "args": args, "result": result_str}],
            "ai_text": f"{tool_name} → {result_str[:120]}",
            "timestamp": time.time(),
        }
        steps.append(record)
        all_calls.append({"name": tool_name, "args": args, "result": result_str})

        if on_step:
            try:
                on_step(step_num, record)
            except Exception:
                pass

        # A sensitive tool parked itself waiting for approval — stop and ask.
        if "needs your go-ahead" in result_str:
            final_text = result_str
            break

    if not final_text:
        final_text = _summarise(task, transcript, completed)

    return {
        "text": final_text,
        "steps": steps,
        "tool_calls": all_calls,
        "completed": completed,
        "total_time": round(time.time() - start, 2),
        "step_count": len(steps),
    }


def _summarise(task, transcript, completed):
    """Turn the transcript into one or two spoken sentences."""
    from core.local_llm import local_chat
    from core.ai_engine import get_system_prompt, _clean_response

    if not transcript:
        return "I couldn't find a way to start that one, sir."

    history = "\n".join(transcript[-10:])
    prompt = (
        f"{get_system_prompt()}\n\n"
        f"He asked you to: {task}\n\n"
        f"Here is what you actually did:\n{history}\n\n"
        + ("Tell him it's done and what the outcome was, in one or two short "
           "spoken sentences." if completed else
           "Tell him how far you got and what stopped you, in one or two short "
           "spoken sentences.")
        + " No markdown, no tool names, no step numbers."
    )
    text = local_chat([{"role": "user", "content": prompt}], max_tokens=180, temperature=0.5)
    return _clean_response(text) if text else "That's done, sir."
