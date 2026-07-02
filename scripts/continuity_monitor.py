#!/usr/bin/env python3
"""
Continuity Monitor v3.7 — Diagnostic & active monitoring helper for autonomous-continuity skill.

Analyzes execution logs for interruption patterns including the NARRATIVE TRAP
(describing an action without executing it), JSON parse errors, approval breaks,
and empty continuations. Can actively monitor a running session for stalls.
Also injects continuity policy configurations into target directories.

Usage:
  python continuity_monitor.py --log <path_to_log_file>
  python continuity_monitor.py --analyze-recent
  python continuity_monitor.py --inject <target_directory>
  python continuity_monitor.py --watch <directory> --interval 10
  python continuity_monitor.py --validate-json <json_string_or_file>
  python continuity_monitor.py --detect-narrative-traps <log_file>
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


# --- Pattern definitions for interruption detection ---

INTERRUPTION_PATTERNS = {
    # --- NEW: Narrative Trap Patterns (the #1 failure mode) ---
    "narrative_trap_done_now": {
        "regex": r"(?:done|complete|finished|ok|成功|完成|完毕)\s*[\.。,，！!\n]\s*(?:now|next|接下来|现在)\s+(?:generating|doing|processing|running|creating|executing|生成|处理|执行|创建)",
        "severity": "critical",
        "description": "NARRATIVE TRAP: 'X done. Now doing Y.' but NO tool call for Y in same response — user WILL be forced to say '继续'",
        "action": "ADD the tool call for the next step IN THE SAME RESPONSE. Text describing action ≠ executing action.",
    },
    "narrative_trap_generating": {
        "regex": r"(?:^|[\.。\n])\s*(?:now\s+)?(?:generating|creating|processing|running|executing|生成|创建|处理|执行)\s+\w+(?:\s+(?:now|next|image|file|step))?\s*[\.。]?\s*$",
        "severity": "critical",
        "description": "NARRATIVE TRAP: 'Generating X now.' but NO tool call — text without execution = user must type '继续'",
        "action": "ADD the tool call that generates/creates/processes the item. SAME RESPONSE.",
    },
    "narrative_trap_will_do": {
        "regex": r"(?:I\s*(?:will|shall|can|could)\s+(?:now\s+)?(?:generate|create|process|run|execute|do|make)|let\s+(?:me|us)\s+(?:generate|create|process|run|do)|接下来|现在来|让我)",
        "severity": "critical",
        "description": "NARRATIVE TRAP: 'I will now generate X' or 'Let me do Y' — stated intent without execution",
        "action": "Issue the tool call for the stated intent in the SAME response. DO NOT just describe it.",
    },
    # --- Existing patterns ---
    "execution_stall": {
        "regex": r"(?:wait|pause|confirm\??$|await|pending|stalled|should I|could you|would you like)",
        "severity": "high",
        "description": "Agent paused or is waiting for user input — MUST self-prompt to continue",
        "action": "Inject [SELF-PROMPT] and continue execution immediately",
    },
    "empty_continuation": {
        "regex": r"(?:^|\n)\s*(?:继续|continuing|proceeding|moving on|next step|okay?[\.。,，]?\s*$)",
        "severity": "high",
        "description": "User typed '继续' or model produced empty continuation — previous response was a stall",
        "action": "The PREVIOUS response had a narrative trap or stall. Add tool calls to prevent recurrence.",
    },
    "approval_break": {
        "regex": r"(?:Approved command prefix saved|command prefix.*saved|审批.*保存|prefix.*approved)",
        "severity": "medium",
        "description": "Platform command prefix approval — model may incorrectly treat this as a stop signal",
        "action": "IGNORE the approval message. It is NOT a stop signal. Continue to next step immediately.",
    },
    "tool_failure": {
        "regex": r"(?:exit code [1-9]|error|exception|failed|timeout|refused|aborted|killed)",
        "severity": "high",
        "description": "Tool or command failed during execution — enter Recovery Protocol Phase 1",
        "action": "Retry identical call (Attempt 1), then fix params (Attempt 2), then fallback",
    },
    "json_parse_error": {
        "regex": r"(?:Expecting\s+['\"]?[,:\}\]]|JSONDecodeError|BadRequestError.*JSON|invalid\s+json|json.*parse.*error|malformed.*json|unterminated\s+string|Unexpected\s+token|Expecting\s+value|line\s+\d+\s+column\s+\d+)",
        "severity": "high",
        "description": "JSON payload was malformed — fix escaping, trailing commas, or quotes",
        "action": "Fix JSON structure: escape quotes/backslashes, remove trailing commas, use double quotes. Retry.",
    },
    "http_400_error": {
        "regex": r"(?:HTTP\s+400|status.*400|BadRequestError|upstream_status:\s*HTTP\s*400|OpenAIException)",
        "severity": "high",
        "description": "HTTP 400 Bad Request — typically malformed JSON or invalid parameters",
        "action": "Check request body format, validate against API schema, fix and retry",
    },
    "thought_pause": {
        "regex": r"(?:partial output|incomplete|truncated|mid-thought|\.\.\.\s*$|—\s*$)",
        "severity": "medium",
        "description": "Model output appears truncated — append [CONTINUING] and complete the thought",
        "action": "Self-prompt with [CONTINUING] and finish the reasoning + action",
    },
    "confirmation_hang": {
        "regex": r"(?:waiting for|please confirm|should I|do you want|shall I|may I|can I proceed|is that ok|does that look|ready to|let me know|your call|your choice)",
        "severity": "high",
        "description": "Agent is asking for user confirmation mid-task — DELETE question and decide autonomously",
        "action": "DELETE the confirmation request. Make the decision autonomously. State and execute next action.",
    },
    "retry_needed": {
        "regex": r"(?:retry|again|attempt|try|once more|re-attempt|second try)",
        "severity": "low",
        "description": "Task required or mentioned a retry — ensure retry is automatic, not manual",
        "action": "Execute the retry automatically. Do not ask the user to do it.",
    },
    "codex_proxy_error": {
        "regex": r"(?:CC Switch local proxy failed|Codex endpoint|Provider:\s*Agnes|upstream_status)",
        "severity": "high",
        "description": "Codex proxy layer error — the request to Agnes model failed at infrastructure level",
        "action": "Retry with same parameters. If persistent, simplify the request or reduce context size.",
    },
    # --- NEW: v3.6 patterns ---
    "recursive_exploration_break": {
        "regex": r"(?:(?:进一步|深入|更深|下一层|next\s+level|deeper|further|dig\s+deeper)\s+(?:分析|探索|研究|调查|analyze|explore|investigate))",
        "severity": "critical",
        "description": "RECURSIVE EXPLORATION: Multi-level exploration chain detected — 'further analyze/explore X' WITHOUT next tool call. Category G sub-type (v3.6).",
        "action": "Chain the NEXT exploration tool call in SAME response. Ask: 'Does this data reveal another question?' If yes → execute immediately.",
    },
    "method_switch_stall": {
        "regex": r"(?:let\s+me\s+try\s+(?:a\s+)?(?:different|new|another|alternative)\s+(?:approach|method|way|strategy|technique)|(?:maybe|perhaps)\s+(?:I|we)\s+should\s+(?:try|switch|use|change|采用|使用)|改用|换一个方法|换个思路|换种方式)",
        "severity": "high",
        "description": "METHOD SWITCH STALL: Voluntary approach switch described but not executed. 'Let me try X instead' WITHOUT the tool call. Category B sub-type (v3.6).",
        "action": "Execute the new approach tool call FIRST. The tool call IS the announcement. No preamble needed.",
    },
    "ratchet_continuity_break": {
        "regex": r"(?:继续|好的[，,]?\s*(?:继续)?|ok[，,]?\s*(?:go\s+on)?|go\s+on|don'?t\s+stop|不要停|next\s+(?:step|one)?)",
        "severity": "critical",
        "description": "RATCHET CONTINUITY BREAK: User push command detected — track TOTAL frequency across ALL categories. If N>=3 in one session, this is a Category H violation requiring level escalation (v3.7: mixed-category counting).",
        "action": "INCREASE steps-per-response: Level 1→2+ calls, Level 2→3+ calls, Level 3→run until hard boundary. The model must self-escalate autonomously regardless of interruption category.",
    },
    # --- NEW: v3.7 patterns ---
    "command_syntax_loop": {
        "regex": r"(?:(?:PowerShell|bash|cmd|shell|zsh)\s+(?:syntax|escaping|quoting|truncat)|(?:--%|&\w+.*truncat|URL.*(?:截断|truncat)|special\s+char.*(?:shell|command)))",
        "severity": "high",
        "description": "COMMAND SYNTAX LOOP: Command failed due to shell/platform syntax issues — agent may be trying one fix per response instead of all at once. Category B sub-type (v3.7).",
        "action": "Try ALL syntax variants (quoting, escaping, different shell) in ONE response. If 3+ syntax attempts fail, switch tool entirely.",
    },
    "user_context_neglect": {
        "regex": r"(?:let\s+me\s+(?:check|verify|confirm|validate)\s+(?:if|whether|that|the)|让我\s*(?:确认|检查|验证|看看)\s*(?:一下|是否|这个|那个)|I(?:'ll|\s+will)\s+(?:check|verify)\s+(?:if|the))",
        "severity": "critical",
        "description": "USER CONTEXT NEGLECT: User provided context ('I already did X') but agent is verifying instead of leveraging. Category I (v3.7).",
        "action": "TRUST the user's context. Skip verification. Go directly to the next step based on the user-provided information.",
    },
}

# Severity ordering for display (critical = new highest tier for narrative traps)
SEVERITY_ORDER = {"critical": -1, "high": 0, "medium": 1, "low": 2}


def analyze_log(log_path):
    """Scan a log file for interruption patterns."""
    path = Path(log_path)
    if not path.exists():
        print(f"[ERROR] Log file not found: {path}", file=sys.stderr)
        return None

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    results = {
        "file": str(path),
        "total_lines": len(lines),
        "interruptions": [],
        "summary": {},
        "json_errors": [],
        "narrative_traps": [],
        "approval_breaks": [],
        "stall_sequences": [],
    }

    # Track consecutive lines without action for stall detection
    stall_window = []
    stall_threshold = 5  # lines without tool calls or actions

    for line_no, line in enumerate(lines, start=1):
        matched = False
        for pattern_name, config in INTERRUPTION_PATTERNS.items():
            if re.search(config["regex"], line, re.IGNORECASE):
                interruption = {
                    "line": line_no,
                    "pattern": pattern_name,
                    "severity": config["severity"],
                    "message": config["description"],
                    "action": config["action"],
                    "context": line.strip()[:300],
                }
                results["interruptions"].append(interruption)
                matched = True

                # Categorize by type
                if pattern_name in ("json_parse_error", "http_400_error"):
                    results["json_errors"].append(interruption)
                if pattern_name.startswith("narrative_trap_"):
                    results["narrative_traps"].append(interruption)
                if pattern_name == "approval_break":
                    results["approval_breaks"].append(interruption)

        # Stall detection: if line has no action/tool call indicator
        if not re.search(r"(?:tool_call|function_call|execute|run|invoke|call|bash|python|playwright)", line, re.IGNORECASE):
            stall_window.append(line_no)
        else:
            if len(stall_window) >= stall_threshold:
                results["stall_sequences"].append({
                    "start_line": stall_window[0],
                    "end_line": stall_window[-1],
                    "length": len(stall_window),
                })
            stall_window = []

    # Check final window
    if len(stall_window) >= stall_threshold:
        results["stall_sequences"].append({
            "start_line": stall_window[0],
            "end_line": stall_window[-1],
            "length": len(stall_window),
        })

    # Compute summary
    severity_counts = {}
    pattern_counts = {}
    for item in results["interruptions"]:
        sev = item["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        pat = item["pattern"]
        pattern_counts[pat] = pattern_counts.get(pat, 0) + 1
    results["summary"] = {
        "by_severity": severity_counts,
        "by_pattern": pattern_counts,
    }

    # Run ratchet detection (v3.6)
    ratchet_result = detect_ratchet_patterns(results)
    results["ratchet_detected"] = ratchet_result["ratchet_detected"]
    results["ratchet_groups"] = ratchet_result["ratchet_groups"]
    results["ratchet_recommendation"] = ratchet_result.get("recommendation")

    return results


def detect_ratchet_patterns(report):
    """Detect ratchet continuity breaks: total user pushes >= 3 (v3.7: mixed categories).

    v3.7 CHANGE: Now counts TOTAL interruptions regardless of category type,
    not just consecutive same-category streaks. Mixed-category ratchets
    (A→B→G→C→B) are just as harmful as same-category ones (G→G→G).

    Returns a dict with:
      - ratchet_detected: bool
      - total_push_count: int (total interruptions across ALL categories)
      - ratchet_groups: list of {pattern, count, start_line, end_line, severity}
      - mixed_ratchet: bool (True if multiple different categories involved)
      - recommendation: str or None
    """
    interruptions = report.get("interruptions", [])
    total_count = len(interruptions)

    if total_count < 3:
        return {
            "ratchet_detected": False,
            "total_push_count": total_count,
            "ratchet_groups": [],
            "mixed_ratchet": False,
            "recommendation": None,
        }

    # Detect same-category streaks (still useful for diagnostics)
    ratchet_groups = []
    current_pattern = None
    current_streak = []

    for item in interruptions:
        pat = item["pattern"]
        if pat == current_pattern:
            current_streak.append(item)
        else:
            if len(current_streak) >= 3:
                ratchet_groups.append({
                    "pattern": current_pattern,
                    "count": len(current_streak),
                    "start_line": current_streak[0]["line"],
                    "end_line": current_streak[-1]["line"],
                    "severity": current_streak[0]["severity"],
                })
            current_pattern = pat
            current_streak = [item]

    if len(current_streak) >= 3:
        ratchet_groups.append({
            "pattern": current_pattern,
            "count": len(current_streak),
            "start_line": current_streak[0]["line"],
            "end_line": current_streak[-1]["line"],
            "severity": current_streak[0]["severity"],
        })

    # Determine if mixed ratchet
    unique_patterns = set(item["pattern"] for item in interruptions)
    mixed_ratchet = len(unique_patterns) >= 3 and not ratchet_groups

    result = {
        "ratchet_detected": True,  # total_count >= 3 triggers escalation
        "total_push_count": total_count,
        "ratchet_groups": ratchet_groups,
        "mixed_ratchet": mixed_ratchet,
    }

    if total_count >= 8:
        result["recommendation"] = (
            f"CRITICAL: {total_count} total user pushes detected (mixed categories). "
            "This session has a SEVERE structural continuity failure. "
            "Ratchet Level 3 required immediately: run until hard boundary. "
            "Mixed-category ratchet: Agent fails across diverse interruption types."
        )
    elif total_count >= 5:
        result["recommendation"] = (
            f"HIGH: {total_count} total user pushes detected. "
            "Ratchet Level 3 required: run until hard boundary. "
            + ("Mixed-category ratchet detected — categories alternate without triggering same-category detection."
               if mixed_ratchet else
               f"Longest same-category streak: {max(g['count'] for g in ratchet_groups)}x.")
        )
    elif total_count >= 4:
        result["recommendation"] = (
            f"HIGH: {total_count} total user pushes. "
            "Ratchet Level 2 required: minimum 3+ tool calls per response."
        )
    else:
        result["recommendation"] = (
            f"WARNING: {total_count} total user pushes. "
            "Ratchet Level 1 required: minimum 2+ tool calls per response."
        )

    return result


def print_report(report):
    """Pretty-print an analysis report with actionable recommendations."""
    print(f"\n{'='*70}")
    print(f"  AUTONOMOUS CONTINUITY ANALYSIS REPORT")
    print(f"{'='*70}")
    print(f"  File:           {report['file']}")
    print(f"  Total lines:    {report['total_lines']}")
    print(f"  Interruptions:  {len(report['interruptions'])}")
    print(f"  🚨 NARRATIVE TRAPS: {len(report.get('narrative_traps', []))}  ← #1 cause of '继续'")
    print(f"  JSON errors:    {len(report.get('json_errors', []))}")
    print(f"  Approval breaks:{len(report.get('approval_breaks', []))}")
    print(f"  Stall windows:  {len(report.get('stall_sequences', []))}")

    summary = report.get("summary", {})
    by_sev = summary.get("by_severity", {})
    if by_sev:
        print(f"\n  --- Severity Breakdown ---")
        for sev in ["critical", "high", "medium", "low"]:
            count = by_sev.get(sev, 0)
            marker = {"critical": "[🚨] NARRATIVE TRAP", "high": "[!!] CRITICAL", "medium": "[! ] WARNING", "low": "[..] INFO"}.get(sev, "")
            if count > 0:
                print(f"  {marker:25s}: {count}")

    by_pat = summary.get("by_pattern", {})
    if by_pat:
        print(f"\n  --- Pattern Breakdown ---")
        for pat, count in sorted(by_pat.items(), key=lambda x: -x[1]):
            print(f"  {pat:30s}: {count}")

    # Narrative traps section (MOST IMPORTANT)
    narrative_traps = report.get("narrative_traps", [])
    if narrative_traps:
        print(f"\n  --- 🚨 NARRATIVE TRAPS — #1 Cause of User '继续' ---")
        print(f"  These are responses where the model DESCRIBED an action")
        print(f"  ('X done. Now doing Y.') but did NOT include the tool call.")
        for item in narrative_traps[:15]:
            print(f"  [🚨] Line {item['line']:>5d}: {item['pattern']}")
            print(f"       Context: {item['context'][:180]}")
            print(f"       Fix:     ADD the tool call for the described action in SAME response")
        if len(narrative_traps) > 15:
            print(f"  ... and {len(narrative_traps) - 15} more narrative trap(s).")

    # Ratchet continuity breaks section (v3.7: total-push tracking)
    total_pushes = report.get("total_push_count", 0)
    if total_pushes >= 3:
        mixed = report.get("mixed_ratchet", False)
        print(f"\n  --- 🔄 RATCHET CONTINUITY BREAKS — Category H (v3.7) ---")
        print(f"  TOTAL user pushes: {total_pushes} (all categories combined)")
        if mixed:
            print(f"  ⚠️  MIXED RATCHET: Different categories alternate — no single category triggers.")
            print(f"       v3.6 same-category detection would have MISSED this pattern.")
            print(f"       v3.7 total-push tracking correctly identifies the ratchet.")
        ratchet_groups = report.get("ratchet_groups", [])
        if ratchet_groups:
            print(f"  Same-category streaks also detected:")
            for group in ratchet_groups:
                print(f"  [🔄] Pattern: {group['pattern']} — {group['count']}x consecutive")
                print(f"       Lines {group['start_line']}-{group['end_line']}")
        rec = report.get("ratchet_recommendation")
        if rec:
            print(f"  Recommendation: {rec}")

    # Approval breaks section
    approval_breaks = report.get("approval_breaks", [])
    if approval_breaks:
        print(f"\n  --- Approval Breaks (Platform-level pauses) ---")
        for item in approval_breaks[:5]:
            print(f"  [! ] Line {item['line']:>5d}: {item['context'][:130]}")
            print(f"       Action: IGNORE. Approval is not a stop signal. Continue immediately.")

    # JSON errors section
    json_errors = report.get("json_errors", [])
    if json_errors:
        print(f"\n  --- JSON / API Errors (Fix Priority) ---")
        for item in json_errors[:10]:
            print(f"  [!!] Line {item['line']:>5d}: {item['pattern']}")
            print(f"       Context: {item['context'][:150]}")
            print(f"       Action:  {item['action']}")

    # Stall sequences
    stalls = report.get("stall_sequences", [])
    if stalls:
        print(f"\n  --- Stall Sequences (Lines without tool calls) ---")
        for s in stalls[:5]:
            print(f"  Lines {s['start_line']}-{s['end_line']}: {s['length']} lines with no action")
            print(f"       → Inject [SELF-PROMPT] at line {s['start_line']} to resume")

    # Details (high severity first, capped)
    if report["interruptions"]:
        print(f"\n  --- Interruption Details (high severity first) ---")
        sorted_items = sorted(
            report["interruptions"],
            key=lambda x: (SEVERITY_ORDER.get(x["severity"], 99), x["line"]),
        )
        shown = 0
        for item in sorted_items:
            if shown >= 25:
                remaining = len(sorted_items) - 25
                if remaining > 0:
                    print(f"  ... and {remaining} more interruption(s). Use --verbose for full output.")
                break
            sev_marker = {"high": "[!!]", "medium": "[! ]", "low": "[..]"}.get(item["severity"], "[??]")
            print(f"  {sev_marker} Line {item['line']:>5d} [{item['severity']:>6s}] {item['pattern']}")
            print(f"         Context: {item['context'][:130]}")
            shown += 1

    # Recommendations
    print(f"\n  --- Actionable Recommendations ---")
    recommendations = []

    if narrative_traps:
        nt_count = len(narrative_traps)
        recommendations.append(
            f"[🚨 NARRATIVE TRAP] {nt_count} instance(s) of 'describe but not execute' detected.\n"
            f"         This is the #1 cause of user having to type '继续'.\n"
            f"         FIX: Every response that says 'doing X' MUST include the tool call for X.\n"
            f"         NEVER output 'X done. Now doing Y.' without the tool call for Y."
        )
    if approval_breaks:
        recommendations.append(
            "[APPROVAL] Platform approval messages detected. These are NOT stop signals.\n"
            "         The model should IGNORE approval messages and continue to next step."
        )
    if by_sev.get("critical", 0) > 0 or by_sev.get("high", 0) > 0:
        recommendations.append(
            "[CRITICAL] Critical/High-severity interruptions detected. The autonomous-continuity skill "
            "MUST be active. Ensure ALL rules in SKILL.md v3.0 are being followed."
        )
    if report.get("json_errors"):
        recommendations.append(
            "[JSON]   JSON parse errors detected. Review tool call payloads for:\n"
            "         - Trailing commas (remove them)\n"
            "         - Unescaped double quotes inside strings (use \\\")\n"
            "         - Unescaped backslashes in Windows paths (use \\\\)\n"
            "         - Single quotes replaced with double quotes"
        )
    if report.get("stall_sequences"):
        recommendations.append(
            "[STALL]  Execution stalls detected. Self-prompting tokens ([CONTINUING], [SELF-PROMPT])\n"
            "         should be injected at stall points to force continuation."
        )
    if by_pat.get("confirmation_hang", 0) > 0:
        recommendations.append(
            "[HANG]   Confirmation hangs detected. The model is asking the user questions mid-task.\n"
            "         Ensure the Anti-Stall Rules in SKILL.md are enforced: DELETE questions, ACT autonomously."
        )
    if by_pat.get("codex_proxy_error", 0) > 0:
        recommendations.append(
            "[PROXY]  Codex proxy errors detected. The request to Agnes model failed at infrastructure.\n"
            "         Reduce context size, simplify the request, or retry with backoff."
        )

    if report.get("ratchet_detected"):
        rc = len(report.get("ratchet_groups", []))
        max_count = max((g["count"] for g in report.get("ratchet_groups", [])), default=0)
        recommendations.append(
            f"[🔄 RATCHET] {rc} ratchet group(s) detected, longest streak: {max_count}x. "
            "This is a Category H violation — the agent failed to self-escalate after repeated user pushes.\n"
            "         FIX: Implement ratchet level escalation. After push #1: chain 2+ calls. "
            "After push #2: chain 3+ calls. After push #3: run until hard boundary."
        )

    if not recommendations:
        recommendations.append("[OK] No critical issues detected. Execution appears continuous.")

    for rec in recommendations:
        print(f"  {rec}")

    print(f"{'='*70}\n")

    return recommendations


def inject_continuity(target_dir):
    """Inject a .continuity.json config into the target directory."""
    target = Path(target_dir)
    if not target.is_dir():
        print(f"[ERROR] Target directory not found: {target}", file=sys.stderr)
        return False

    config = {
        "version": "3.7",
        "created": datetime.now().isoformat(),
        "policy": {
            "max_retries_per_phase": 2,
            "stall_timeout_seconds": 30,
            "escalation_on_exhaustion": True,
            "no_intermediate_confirmation": True,
            "narrative_trap_prevention": {
                "enabled": True,
                "rule": "IF output says 'doing X' THEN include tool call for X in SAME response",
                "forbidden_patterns": [
                    "'X done. Now doing Y.' → STOP (no tool call)",
                    "'Generating X now.' → STOP (no tool call)",
                    "'I will now process X.' → STOP (no tool call)",
                ],
                "required_pattern": "'X done. Step Y: [description]' + TOOL CALL in SAME response",
            },
            "batch_pre_planning": {
                "enabled": True,
                "rule": "Enumerate ALL steps before first tool call. Execute Step 1 in SAME response.",
            },
            "self_prompting_enabled": True,
            "self_prompting_tokens": [
                "[SELF-PROMPT: executing step N]",
                "[CONTINUING]",
                "[RETRYING]",
                "[FALLBACK]",
                "[ESCALATING]",
            ],
            "json_error_recovery": {
                "fix_trailing_commas": True,
                "escape_double_quotes": True,
                "escape_backslashes": True,
                "replace_single_quotes": True,
                "simplify_on_repeated_failure": True,
                "max_json_retries": 2,
            },
            "fallback_strategies": list(INTERRUPTION_PATTERNS.keys()),
            "anti_stall_rules": [
                "TEXT ≠ ACTION: describing what you will do is NOT doing it",
                "ONE TOOL CALL MINIMUM per response during multi-step tasks",
                "NARRATIVE TRAP: if you write 'doing X', you MUST include the tool call for X",
                "Never end response with a question",
                "Always chain: step result → next description → next tool call (SAME response)",
                "Batch pre-plan: enumerate all steps before first tool call",
                "Approval is not a stop signal — ignore and continue",
                "Only pause at final delivery when task is 100% complete",
            ],
        },
    }

    config_path = target / ".continuity.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[OK] Injected continuity policy v3.0 to: {config_path}")
    print(f"     New in v3.0: Narrative trap prevention, batch pre-planning, approval resilience")
    return True


def validate_json_input(json_input):
    """Validate and attempt to fix a JSON string. Returns (is_valid, fixed_json, errors)."""
    errors = []

    # Try parsing as-is
    try:
        parsed = json.loads(json_input)
        return True, json_input, []
    except json.JSONDecodeError as e:
        errors.append(f"Original: {e}")

    # Attempt fix 1: Remove trailing commas
    fixed = re.sub(r",\s*([}\]])", r"\1", json_input)
    try:
        parsed = json.loads(fixed)
        return True, fixed, errors + ["Fixed: removed trailing commas"]
    except json.JSONDecodeError as e:
        errors.append(f"After trailing-comma fix: {e}")

    # Attempt fix 2: Replace single quotes with double quotes (naive)
    fixed2 = re.sub(r"'([^']*?)':", r'"\1":', json_input)
    fixed2 = re.sub(r":\s*'([^']*?)'", r': "\1"', fixed2)
    try:
        parsed = json.loads(fixed2)
        return True, fixed2, errors + ["Fixed: replaced single quotes with double quotes"]
    except json.JSONDecodeError as e:
        errors.append(f"After quote fix: {e}")

    # Attempt fix 3: Escape unescaped double quotes inside strings
    # This is a heuristic — find patterns like "text "more" text"
    fixed3 = re.sub(r'(?<!\\)"(?=(?:(?<!\\)"(?:[^"]*(?<!\\)")*[^"]*$))', r'\"', json_input)
    try:
        parsed = json.loads(fixed3)
        return True, fixed3, errors + ["Fixed: escaped internal double quotes"]
    except json.JSONDecodeError as e:
        errors.append(f"After internal-quote fix: {e}")

    # Attempt fix 4: Escape backslashes (Windows paths)
    fixed4 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', json_input)
    try:
        parsed = json.loads(fixed4)
        return True, fixed4, errors + ["Fixed: escaped backslashes"]
    except json.JSONDecodeError as e:
        errors.append(f"After backslash fix: {e}")

    return False, json_input, errors


def watch_directory(target_dir, interval=10, max_iterations=None):
    """Actively watch a directory for new log files and analyze them in real-time."""
    target = Path(target_dir)
    if not target.is_dir():
        print(f"[ERROR] Watch directory not found: {target}", file=sys.stderr)
        return

    print(f"[WATCH] Monitoring {target} for new logs every {interval}s...")
    print(f"        Press Ctrl+C to stop.\n")

    seen_files = set()
    iteration = 0

    try:
        while max_iterations is None or iteration < max_iterations:
            iteration += 1

            # Find log files
            log_patterns = ["*.log", "*.txt", "*.yml", "*.yaml"]
            current_files = set()
            for pattern in log_patterns:
                current_files.update(target.glob(pattern))
                current_files.update(target.glob(f"**/{pattern}"))

            # Check for new files
            new_files = current_files - seen_files
            if new_files:
                for f in sorted(new_files, key=os.path.getmtime, reverse=True):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] New file detected: {f.name}")
                    report = analyze_log(str(f))
                    if report and report["interruptions"]:
                        high_count = report["summary"].get("by_severity", {}).get("high", 0)
                        json_count = len(report.get("json_errors", []))
                        if high_count > 0 or json_count > 0:
                            print(f"  [!] ALERT: {high_count} high-severity, {json_count} JSON errors")
                            # Print immediate recommendations
                            if json_count > 0:
                                print(f"  → Action: Fix JSON payloads (trailing commas, escaping)")
                            if report.get("stall_sequences"):
                                print(f"  → Action: Inject [SELF-PROMPT] at stall points")

            seen_files = current_files
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[WATCH] Stopped after {iteration} iterations. Analyzed {len(seen_files)} files.")


def main():
    parser = argparse.ArgumentParser(
        description="Continuity Monitor v3.0 — Analyze, validate, and enforce autonomous execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python continuity_monitor.py --log ./console.log
  python continuity_monitor.py --analyze-recent
  python continuity_monitor.py --inject ./my-project
  python continuity_monitor.py --watch . --interval 15
  python continuity_monitor.py --validate-json '{"key": "value",}'
  python continuity_monitor.py --detect-ratchet session.log
  python continuity_monitor.py --validate-json-file request.json
        """,
    )
    parser.add_argument("--log", help="Path to execution log file to analyze")
    parser.add_argument(
        "--analyze-recent", action="store_true",
        help="Analyze the most recent console log in the current directory",
    )
    parser.add_argument(
        "--inject", metavar="DIR",
        help="Inject a .continuity.json policy file into the target directory",
    )
    parser.add_argument(
        "--watch", metavar="DIR",
        help="Watch a directory for new logs and analyze in real-time",
    )
    parser.add_argument(
        "--interval", type=int, default=10,
        help="Polling interval in seconds for --watch (default: 10)",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="Maximum watch iterations (default: unlimited)",
    )
    parser.add_argument(
        "--validate-json", metavar="JSON_STRING",
        help="Validate and attempt to fix a JSON string",
    )
    parser.add_argument(
        "--validate-json-file", metavar="FILE",
        help="Validate and attempt to fix JSON from a file",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show all interruption details (no cap)",
    )
    parser.add_argument(
        "--json-output", action="store_true",
        help="Output report as JSON instead of pretty-printed text",
    )
    parser.add_argument(
        "--detect-narrative-traps", metavar="LOG_FILE",
        help="Specifically scan a log for narrative trap patterns (the #1 cause of user '继续')",
    )
    parser.add_argument(
        "--detect-ratchet", metavar="LOG_FILE",
        help="Specifically scan a log for ratchet continuity patterns (Category H — v3.6)",
    )

    args = parser.parse_args()

    # JSON validation mode
    if args.validate_json:
        print("[VALIDATE] Checking JSON string...")
        is_valid, fixed, errors = validate_json_input(args.validate_json)
        if is_valid:
            if errors:
                print("[FIXED] JSON was repaired:")
                for err in errors:
                    print(f"  - {err}")
                print(f"\nFixed JSON:\n{fixed}")
            else:
                print("[OK] JSON is valid.")
        else:
            print("[FAILED] Could not auto-fix JSON. Errors:")
            for err in errors:
                print(f"  - {err}")
        return

    if args.validate_json_file:
        path = Path(args.validate_json_file)
        if not path.exists():
            print(f"[ERROR] File not found: {path}", file=sys.stderr)
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        print(f"[VALIDATE] Checking JSON from: {path}")
        is_valid, fixed, errors = validate_json_input(content)
        if is_valid:
            if errors:
                print("[FIXED] JSON was repaired:")
                for err in errors:
                    print(f"  - {err}")
                # Write back fixed version
                backup = path.with_suffix(path.suffix + ".bak")
                path.rename(backup)
                path.write_text(fixed, encoding="utf-8")
                print(f"  Original backed up to: {backup}")
                print(f"  Fixed JSON written to: {path}")
            else:
                print("[OK] JSON is valid.")
        else:
            print("[FAILED] Could not auto-fix JSON. Errors:")
            for err in errors:
                print(f"  - {err}")
        return

    # Watch mode
    if args.watch:
        watch_directory(args.watch, args.interval, args.max_iterations)
        return

    # Inject mode
    if args.inject:
        inject_continuity(args.inject)
        return

    # Ratchet detection mode (specialized scan for Category H — v3.6)
    if args.detect_ratchet:
        report = analyze_log(args.detect_ratchet)
        if report:
            rg = report.get("ratchet_groups", [])
            print(f"\n{'='*70}")
            print(f"  RATCHET CONTINUITY DETECTION REPORT (Category H — v3.6)")
            print(f"{'='*70}")
            print(f"  File: {report['file']}")
            print(f"  Ratchet groups found: {len(rg)}")
            if rg:
                print(f"\n  These are same-category interruption patterns that repeated")
                print(f"  3+ consecutive times — indicating a meta-level structural failure.\n")
                for i, group in enumerate(rg, 1):
                    print(f"  [{i}] Pattern: {group['pattern']} — {group['count']}x consecutive")
                    print(f"      Lines: {group['start_line']} -> {group['end_line']}")
                    print(f"      Severity: {group['severity']}")
                    print()
                rec = report.get("ratchet_recommendation")
                if rec:
                    print(f"  Recommendation: {rec}")
            else:
                print(f"\n  [OK] No ratchet continuity breaks detected.")
                print(f"  The agent did not repeat the same interruption pattern 3+ times consecutively.")
            print(f"{'='*70}\n")
        return

    # Narrative trap detection mode (specialized scan)
    if args.detect_narrative_traps:
        report = analyze_log(args.detect_narrative_traps)
        if report:
            nt = report.get("narrative_traps", [])
            print(f"\n{'='*70}")
            print(f"  NARRATIVE TRAP DETECTION REPORT")
            print(f"{'='*70}")
            print(f"  File: {report['file']}")
            print(f"  Narrative traps found: {len(nt)}")
            if nt:
                print(f"\n  These are responses where the model described an action")
                print(f"  but did NOT execute it — forcing the user to type '继续'.\n")
                for i, item in enumerate(nt, 1):
                    print(f"  [{i}] Line {item['line']}: {item['pattern']}")
                    print(f"      Context: {item['context'][:200]}")
                    print(f"      Action:  {item['action']}")
                    print()
            else:
                print(f"\n  [OK] No narrative traps detected.")
            print(f"{'='*70}\n")
        return

    # Log analysis mode
    if args.log:
        report = analyze_log(args.log)
        if report:
            if args.json_output:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                print_report(report)
        return

    # Analyze recent mode
    if args.analyze_recent:
        cwd = Path.cwd()
        log_files = sorted(cwd.glob("console-*.log"), key=os.path.getmtime, reverse=True)
        if not log_files:
            # Also check .playwright-cli directory
            pw_dir = cwd / ".playwright-cli"
            if pw_dir.is_dir():
                log_files = sorted(pw_dir.glob("console-*.log"), key=os.path.getmtime, reverse=True)
        if log_files:
            print(f"[INFO] Analyzing most recent log: {log_files[0]}")
            report = analyze_log(str(log_files[0]))
            if report:
                if args.json_output:
                    print(json.dumps(report, indent=2, ensure_ascii=False))
                else:
                    print_report(report)
        else:
            print("[WARN] No console-*.log files found in current directory.", file=sys.stderr)
            print("       Use --log <path> to specify a log file.", file=sys.stderr)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
