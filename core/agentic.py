"""
MARK — Agentic Loop Engine
Multi-step autonomous task execution. The AI keeps calling tools
until the task is complete or the step limit is reached.
Uses local Gemma 2 2B via llama-cpp-python.
"""

import os
import json
import time
import re
import hashlib
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────
# AGENTIC SYSTEM PROMPT EXTENSION
# ─────────────────────────────────────────────

AGENTIC_PROMPT_PREFIX = """You are in AGENTIC MODE. You have the ability to call multiple tools in sequence to complete complex, multi-step tasks autonomously.

RULES FOR AGENTIC MODE:
1. After each tool result, analyze whether the task is FULLY complete. If not, call the next appropriate tool.
2. When the task is fully complete, respond with a concise final summary — do NOT call any more tools.
3. Think step-by-step. Break complex tasks into smaller operations.
4. If a tool fails, analyze the error and try an alternative approach. Do not repeat the same failing call.
5. You can call multiple tools in a single turn if they are independent of each other.
6. Use run_terminal for shell commands, read_file to inspect files, write_file to create files, and edit_file to modify them.
7. Always verify your work — after creating/modifying files, read them back to confirm. After running commands, check the output.
8. If you need information to proceed, use the appropriate tool to gather it first.
9. Keep the user informed with brief status notes between tool calls.
10. STOP when the task is done. Do not over-engineer or add unrequested features.

When you need to use a tool, output EXACTLY this format on its own line:
TOOL_CALL: tool_name({"param": "value"})

After the TOOL_CALL line, write your response to the user.
If no tool is needed, just respond normally.

"""


# ─────────────────────────────────────────────
# AGENTIC LOOP
# ─────────────────────────────────────────────

def run_agentic_task(task, max_steps=15, on_step=None):
    """
    Execute a multi-step task using an agentic loop.
    The AI calls tools repeatedly until the task is complete.

    Args:
        task: Natural language description of what to accomplish
        max_steps: Maximum number of LLM call iterations (default 15)
        on_step: Optional callback(step_num, step_info_dict) for progress

    Returns:
        {
            "text": str,           # Final response text
            "steps": list,         # List of step records
            "tool_calls": list,    # Flat list of all tool calls
            "completed": bool,     # Whether task completed naturally
            "total_time": float,   # Total execution time
            "step_count": int      # Number of steps taken
        }
    """
    from core.ai_engine import TOOLS, SYSTEM_PROMPT
    from core.local_llm import local_chat
    from core.system_controller import execute_tool

    start_time = time.time()
    steps = []
    all_tool_calls = []

    # Build enhanced system prompt with tool names
    tool_names = [t["function"]["name"] for t in TOOLS]
    tool_instruction = (
        "\n\nIMPORTANT — TOOL CALLING:\n"
        "When you need to perform a system action, output EXACTLY this format on its own line:\n"
        "TOOL_CALL: tool_name({\"param\": \"value\"})\n\n"
        "Available tools: " + ", ".join(tool_names) + "\n"
        "After the TOOL_CALL line, write your response to the user.\n"
        "If no tool is needed, just respond normally.\n"
    )

    full_system = AGENTIC_PROMPT_PREFIX + SYSTEM_PROMPT + tool_instruction

    # Build initial messages (local to this run)
    messages = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": task},
    ]

    # Duplicate call detection
    _recent_calls = []

    final_text = ""
    completed = False

    for step_num in range(1, max_steps + 1):
        step_start = time.time()
        step_record = {
            "step": step_num,
            "tool_calls": [],
            "ai_text": None,
            "timestamp": time.time(),
        }

        # Call local LLM
        text = local_chat(messages, max_tokens=1024, temperature=0.3)

        if text is None:
            step_record["ai_text"] = "ERROR: Local LLM call failed."
            steps.append(step_record)
            final_text = "I encountered an error with the local model, sir."
            break

        # Parse tool calls from response
        tool_call_match = re.search(r'TOOL_CALL:\s*(\w+)\((.*)\)', text)

        if tool_call_match:
            func_name = tool_call_match.group(1)
            args_str = tool_call_match.group(2).strip()

            try:
                func_args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                func_args = {}

            # Duplicate detection
            args_hash = hashlib.md5(json.dumps(func_args, sort_keys=True).encode()).hexdigest()
            call_sig = (func_name, args_hash)
            dup_count = sum(1 for c in _recent_calls[-6:] if c == call_sig)

            if dup_count >= 2:
                result = f"LOOP DETECTED: Tool '{func_name}' called with same arguments 3 times. Stopping."
                step_record["tool_calls"].append({"name": func_name, "args": func_args, "result": result})
                all_tool_calls.append({"name": func_name, "args": func_args, "result": result})
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "SYSTEM: Loop detected. Summarize what you've accomplished so far and stop."})
                _recent_calls.append(call_sig)
                steps.append(step_record)
                continue

            _recent_calls.append(call_sig)

            # Execute the tool
            print(f"  🔧 Step {step_num}: {func_name}({json.dumps(func_args)[:100]})")
            try:
                result = execute_tool(func_name, func_args)
            except Exception as e:
                result = f"TOOL ERROR: {type(e).__name__}: {str(e)}"

            result_str = str(result) if result else "Tool returned no output."
            print(f"  ✓ Result: {result_str[:100]}")

            step_record["tool_calls"].append({"name": func_name, "args": func_args, "result": result_str})
            all_tool_calls.append({"name": func_name, "args": func_args, "result": result_str})

            # Clean text and add to messages
            clean_text = re.sub(r'TOOL_CALL:.*\n?', '', text).strip()
            step_record["ai_text"] = clean_text

            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"Tool result from {func_name}: {result_str[:500]}\n\nContinue with the task. If done, give a final summary."})

        else:
            # No tool calls — AI is done
            final_text = text or "Task completed, sir."
            step_record["ai_text"] = final_text
            completed = True
            steps.append(step_record)

            if on_step:
                try:
                    on_step(step_num, step_record)
                except Exception:
                    pass
            break

        steps.append(step_record)

        if on_step:
            try:
                on_step(step_num, step_record)
            except Exception:
                pass

    # If we exhausted max_steps without completion
    if not completed and not final_text:
        final_text = f"Task reached the maximum of {max_steps} steps. Here's what was accomplished."
        messages.append({"role": "user", "content": "SYSTEM: Step limit reached. Give a brief summary of what was accomplished."})
        summary = local_chat(messages, max_tokens=512, temperature=0.3)
        if summary:
            final_text = summary

    total_time = round(time.time() - start_time, 2)

    return {
        "text": final_text,
        "steps": steps,
        "tool_calls": all_tool_calls,
        "completed": completed,
        "total_time": total_time,
        "step_count": len(steps),
    }


# ─────────────────────────────────────────────
# PLANNING (preview without execution)
# ─────────────────────────────────────────────

def get_agentic_plan(task):
    """
    Ask the AI to create a step-by-step plan for a task WITHOUT executing it.
    """
    from core.ai_engine import SYSTEM_PROMPT
    from core.local_llm import local_chat

    plan_prompt = (
        "Create a detailed step-by-step plan for this task. "
        "List each step with the specific tool you would call and why. "
        "Do NOT execute anything — just plan. "
        "Format as a numbered list. Be specific about parameters.\n\n"
        f"Task: {task}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": plan_prompt},
    ]

    try:
        result = local_chat(messages, max_tokens=2048, temperature=0.3)
        return result or "Could not generate a plan."
    except Exception as e:
        return f"Error generating plan: {e}"
