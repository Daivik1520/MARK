#!/usr/bin/env python3
"""
MARK — Evaluation harness.

    python3 evals/run_evals.py            # everything
    python3 evals/run_evals.py --fast     # no model needed (router + retrieval)
    python3 evals/run_evals.py --routing  # LLM tool-selection accuracy

Exit code is non-zero if a suite falls below its threshold, so this can gate a
commit.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.cases import CASES, FAST_ROUTE_CASES  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

# Thresholds. Retrieval must be near-perfect (a missing candidate makes the
# right answer unreachable); end-to-end routing allows for a small-model miss.
RETRIEVAL_THRESHOLD = 0.97
ROUTING_THRESHOLD = 0.80
FAST_ROUTE_THRESHOLD = 1.0


def _hdr(title):
    print(f"\n{'═' * 66}\n  {title}\n{'═' * 66}")


# ─────────────────────────────────────────────
# 1. RETRIEVAL — is the correct tool even a candidate?
# ─────────────────────────────────────────────

def eval_retrieval():
    from core.tool_router import select_tools, explain

    _hdr("RETRIEVAL — is the right tool in the candidate set?")
    passed = failures = 0

    for text, expected, alts in CASES:
        if expected is None:
            continue  # nothing to retrieve for pure conversation
        names = {t["function"]["name"] for t in select_tools(text, max_tools=14)}
        acceptable = {expected} | alts
        if names & acceptable:
            passed += 1
        else:
            failures += 1
            print(f"{RED}  MISS{RESET} {text!r}")
            print(f"       wanted one of: {sorted(acceptable)}")
            print(f"{DIM}{explain(text, 5)}{RESET}")

    total = passed + failures
    rate = passed / total if total else 1.0
    colour = GREEN if rate >= RETRIEVAL_THRESHOLD else RED
    print(f"\n  {colour}{passed}/{total} ({rate:.0%}){RESET}  threshold {RETRIEVAL_THRESHOLD:.0%}")
    return rate >= RETRIEVAL_THRESHOLD


# ─────────────────────────────────────────────
# 2. FAST ROUTER — shortcuts fire, conversation falls through
# ─────────────────────────────────────────────

def eval_fast_router():
    """Pattern matching only — no tools are executed."""
    import core.fast_router as fr

    _hdr("FAST ROUTER — shortcuts fire, questions fall through")
    passed = failures = 0

    for text, expected in FAST_ROUTE_CASES:
        matched = None
        if not (fr._QUESTION.match(text) or fr._CONVERSATIONAL.match(text)):
            import re
            if not re.search(r"\b(?:and then|after that|then\s+\w+\s+(?:it|the|a)\b)", text, re.I):
                for pattern, tool_name, _ in fr.FAST_ROUTES:
                    if pattern.match(text):
                        matched = tool_name
                        break

        if matched == expected:
            passed += 1
        else:
            failures += 1
            print(f"{RED}  FAIL{RESET} {text!r}: got {matched}, wanted {expected}")

    total = passed + failures
    rate = passed / total if total else 1.0
    colour = GREEN if rate >= FAST_ROUTE_THRESHOLD else RED
    print(f"\n  {colour}{passed}/{total} ({rate:.0%}){RESET}  threshold {FAST_ROUTE_THRESHOLD:.0%}")
    return rate >= FAST_ROUTE_THRESHOLD


# ─────────────────────────────────────────────
# 3. PERMISSIONS — the gate holds
# ─────────────────────────────────────────────

def eval_permissions():
    from core import permissions
    from core.permissions import SAFE, MUTATING, SENSITIVE

    _hdr("PERMISSIONS — tiering and confirmation gate")
    checks = [
        ("run_terminal is sensitive", permissions.get_tier("run_terminal") == SENSITIVE),
        ("run_code is sensitive", permissions.get_tier("run_code") == SENSITIVE),
        ("shutdown is sensitive", permissions.get_tier("system_shutdown") == SENSITIVE),
        ("whatsapp is sensitive", permissions.get_tier("send_whatsapp") == SENSITIVE),
        ("write_file is mutating", permissions.get_tier("write_file") == MUTATING),
        ("read_file is safe", permissions.get_tier("read_file") == SAFE),
        ("get_system_stats is safe", permissions.get_tier("get_system_stats") == SAFE),
        ("sensitive needs confirmation", permissions.needs_confirmation("run_terminal")),
        ("safe needs no confirmation", not permissions.needs_confirmation("read_file")),
    ]
    permissions.grant("run_terminal")
    checks.append(("standing approval suppresses prompt",
                   not permissions.needs_confirmation("run_terminal")))
    permissions.revoke("run_terminal")
    checks.append(("revoke restores prompt", permissions.needs_confirmation("run_terminal")))

    passed = 0
    for label, ok in checks:
        print(f"  {GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET}  {label}")
        passed += bool(ok)

    rate = passed / len(checks)
    print(f"\n  {(GREEN if rate == 1 else RED)}{passed}/{len(checks)}{RESET}")
    return rate == 1.0


# ─────────────────────────────────────────────
# 4. CONFIRMATION PARSING
# ─────────────────────────────────────────────

def eval_confirmation():
    from core.tool_executor import classify_confirmation

    _hdr("CONFIRMATION — yes/no interpretation")
    cases = [
        ("yes", "yes"), ("yeah", "yes"), ("do it", "yes"), ("go ahead", "yes"),
        ("yes please", "yes"), ("confirm", "yes"),
        ("no", "no"), ("cancel", "no"), ("nope", "no"), ("never mind", "no"),
        ("stop", "no"),
        ("open spotify", None), ("what is the weather", None), ("", None),
    ]
    passed = 0
    for text, expected in cases:
        got = classify_confirmation(text)
        ok = got == expected
        passed += ok
        if not ok:
            print(f"{RED}  FAIL{RESET} {text!r}: got {got}, wanted {expected}")
    rate = passed / len(cases)
    print(f"  {(GREEN if rate == 1 else RED)}{passed}/{len(cases)}{RESET}")
    return rate == 1.0


# ─────────────────────────────────────────────
# 5. SCHEMA INTEGRITY
# ─────────────────────────────────────────────

def eval_schemas():
    from core.tool_schemas import TOOLS
    from core.system_controller import TOOL_MAP

    _hdr("SCHEMAS — every declared tool is implemented and callable")
    declared = {t["function"]["name"] for t in TOOLS}
    implemented = set(TOOL_MAP)

    missing = sorted(declared - implemented)
    orphaned = sorted(implemented - declared)

    ok = True
    if missing:
        print(f"{RED}  Declared but not implemented: {missing}{RESET}")
        ok = False
    if orphaned:
        print(f"{YELLOW}  Implemented but not declared: {orphaned}{RESET}")
        ok = False

    # Grammar compilation — a schema that will not compile is a latent crash.
    import json
    bad = []
    try:
        from llama_cpp import LlamaGrammar
        for tool in TOOLS:
            params = tool["function"].get("parameters", {}) or {}
            props = params.get("properties", {}) or {}
            if not props:
                continue
            schema = {
                "type": "object",
                "properties": {k: {"type": v.get("type", "string")} for k, v in props.items()},
                "required": list(params.get("required", [])),
                "additionalProperties": False,
            }
            try:
                LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False)
            except Exception as e:
                bad.append((tool["function"]["name"], str(e)[:60]))
    except ImportError:
        print(f"{YELLOW}  llama_cpp unavailable — skipped grammar compilation{RESET}")

    if bad:
        ok = False
        for name, err in bad:
            print(f"{RED}  Grammar failed: {name} — {err}{RESET}")

    if ok:
        print(f"  {GREEN}{len(declared)} tools declared, all implemented, all grammars compile{RESET}")
    return ok


# ─────────────────────────────────────────────
# 6. ROUTING — end-to-end with the model
# ─────────────────────────────────────────────

def eval_routing(limit=None):
    from core.ai_engine import decide_tool

    _hdr("ROUTING — end-to-end tool selection (loads the model)")
    cases = CASES[:limit] if limit else CASES
    passed = failures = 0
    started = time.time()

    for i, (text, expected, alts) in enumerate(cases, 1):
        chosen, _ = decide_tool(text, history=None)
        acceptable = {expected} | alts if expected else {None}
        ok = chosen in acceptable
        if ok:
            passed += 1
        else:
            failures += 1
            print(f"{RED}  FAIL{RESET} {text!r}")
            print(f"       got {chosen!r}, wanted {sorted(str(a) for a in acceptable)}")
        if i % 10 == 0:
            print(f"{DIM}       ...{i}/{len(cases)} ({time.time()-started:.0f}s){RESET}")

    total = passed + failures
    rate = passed / total if total else 0
    colour = GREEN if rate >= ROUTING_THRESHOLD else RED
    avg = (time.time() - started) / total if total else 0
    print(f"\n  {colour}{passed}/{total} ({rate:.0%}){RESET}  threshold {ROUTING_THRESHOLD:.0%}"
          f"   avg {avg:.2f}s/decision")
    return rate >= ROUTING_THRESHOLD


# ─────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    fast_only = "--fast" in args
    routing_only = "--routing" in args

    results = {}

    if routing_only:
        results["routing"] = eval_routing()
    else:
        results["schemas"] = eval_schemas()
        results["retrieval"] = eval_retrieval()
        results["fast_router"] = eval_fast_router()
        results["permissions"] = eval_permissions()
        results["confirmation"] = eval_confirmation()
        if not fast_only:
            results["routing"] = eval_routing()

    _hdr("SUMMARY")
    for name, ok in results.items():
        print(f"  {GREEN + 'PASS' + RESET if ok else RED + 'FAIL' + RESET}  {name}")

    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\n{RED}  {len(failed)} suite(s) below threshold: {', '.join(failed)}{RESET}\n")
        return 1
    print(f"\n{GREEN}  All suites passed.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
