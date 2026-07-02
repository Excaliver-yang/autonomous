#!/usr/bin/env bash
# =============================================================================
# continuity-hook.sh v3.6 — Claude Code postToolUse Hook
# Autonomous Continuity Engine — Stall Pattern Monitor
#
# Usage: Configure in project .claude/settings.json as a postToolUse hook:
#   {
#     "hooks": {
#       "postToolUse": "bash .claude/skills/autonomous-continuity/hooks/continuity-hook.sh"
#     }
#   }
#
# This script monitors tool output for stall patterns that would force
# the user to type "继续". It is a MONITORING tool only — it cannot
# inject tool calls or modify the generation loop. Real enforcement
# comes from the autonomous-continuity skill rules (SKILL.md).
#
# Input: Receives JSON on stdin with tool invocation context.
# Output: Writes stall detection results to .continuity_hook.log
# =============================================================================

set -euo pipefail

LOG_FILE="${LOG_FILE:-.continuity_hook.log}"
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Stall Pattern Definitions (mirrors SKILL.md A-H categories) ---

# Category C: Colon trap patterns (highest frequency — 52.0% of all interruptions)
COLON_TRAPS=(
  "Step [0-9].*:$"
  "完成.*Step.*:$"
  "done.*Step.*:$"
  "现在.*:$"
  "let me.*:$"
  "让我.*:$"
  "我来.*:$"
  "现在来.*:$"
  "let me try.*instead:$"
  "改用.*:$"
)

# Categories A-E: Intent-without-execution patterns
INTENT_TRAPS=(
  "now generating"
  "let me retry"
  "let me fix"
  "let me rename"
  "let me search"
  "I should"
  "I will now"
  "let me analyze"
  "now explore"
  "further analyze"
  "let me try.*instead"
  "maybe.*should switch"
)

# Category G: Exploration chain break patterns
EXPLORATION_TRAPS=(
  "现在来分析"
  "深入分析"
  "进一步探索"
  "let me explore further"
  "now let me analyze"
  "进一步分析"
  "更深.*分析"
  "下一层"
)

# Category H: Ratchet continuity indicators
RATCHET_INDICATORS=(
  "继续"
  "好的"
  "不要停"
  "go on"
  "don.t stop"
)

# --- Utility Functions ---

log_stall() {
  local level="$1"
  local pattern="$2"
  local context="$3"
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')

  echo "[${timestamp}] ${level} | Pattern: ${pattern} | Context: ${context}" >> "${LOG_FILE}"

  # High-severity stalls also go to stderr for visibility
  if [[ "${level}" == "CRITICAL" || "${level}" == "HIGH" ]]; then
    echo "[continuity-hook] ${level}: ${pattern} — ${context}" >&2
  fi
}

# --- Main Logic ---

# Read tool invocation data from stdin (if available)
INPUT=""
if [ -t 0 ]; then
  # No stdin (interactive shell) — skip
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] No stdin data. Hook ran in check-only mode." >> "${LOG_FILE}"
  exit 0
else
  INPUT=$(cat)
fi

# Attempt to extract tool name and output from JSON
TOOL_NAME=""
TOOL_OUTPUT=""

if command -v jq &> /dev/null; then
  TOOL_NAME=$(echo "${INPUT}" | jq -r '.tool_name // .name // ""' 2>/dev/null || echo "")
  TOOL_OUTPUT=$(echo "${INPUT}" | jq -r '.output // .result // .text // ""' 2>/dev/null || echo "")
else
  # Fallback: try python for JSON parsing
  if command -v python3 &> /dev/null; then
    TOOL_NAME=$(echo "${INPUT}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name', d.get('name', '')))" 2>/dev/null || echo "")
    TOOL_OUTPUT=$(echo "${INPUT}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('output', d.get('result', d.get('text', ''))))" 2>/dev/null || echo "")
  else
    # No JSON parser available — log raw input and exit
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] jq and python3 not found. Cannot parse JSON input." >> "${LOG_FILE}"
    exit 0
  fi
fi

# Combine tool name + output for pattern scanning
SCAN_TEXT="${TOOL_NAME} ${TOOL_OUTPUT}"

# --- Pattern Scanning ---

STALL_COUNT=0

# Check colon traps (Category C)
for pattern in "${COLON_TRAPS[@]}"; do
  if echo "${SCAN_TEXT}" | grep -qE "${pattern}"; then
    log_stall "HIGH" "colon_trap:${pattern}" "$(echo "${SCAN_TEXT}" | grep -oE '.{0,60}'"${pattern}" | head -1)"
    ((STALL_COUNT++))
  fi
done

# Check intent traps (Categories A-E)
for pattern in "${INTENT_TRAPS[@]}"; do
  if echo "${SCAN_TEXT}" | grep -qiE "${pattern}"; then
    log_stall "HIGH" "intent_trap:${pattern}" "$(echo "${SCAN_TEXT}" | grep -oiE '.{0,60}'"${pattern}"'.{0,60}' | head -1)"
    ((STALL_COUNT++))
  fi
done

# Check exploration traps (Category G)
for pattern in "${EXPLORATION_TRAPS[@]}"; do
  if echo "${SCAN_TEXT}" | grep -qE "${pattern}"; then
    log_stall "CRITICAL" "exploration_trap:${pattern}" "$(echo "${SCAN_TEXT}" | grep -oE '.{0,60}'"${pattern}"'.{0,60}' | head -1)"
    ((STALL_COUNT++))
  fi
done

# Check ratchet indicators (Category H)
for pattern in "${RATCHET_INDICATORS[@]}"; do
  if echo "${SCAN_TEXT}" | grep -qE "${pattern}"; then
    log_stall "CRITICAL" "ratchet_indicator:${pattern}" "User push command detected — track frequency. If 3+ in session, escalate to Category H."
    ((STALL_COUNT++))
  fi
done

# Summary
if [ "${STALL_COUNT}" -gt 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ALERT] ${STALL_COUNT} stall pattern(s) detected for tool: ${TOOL_NAME}" >> "${LOG_FILE}"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [OK] No stall patterns detected for tool: ${TOOL_NAME}" >> "${LOG_FILE}"
fi

# Rotate log if it exceeds 1000 lines
if [ -f "${LOG_FILE}" ] && [ "$(wc -l < "${LOG_FILE}")" -gt 1000 ]; then
  tail -n 500 "${LOG_FILE}" > "${LOG_FILE}.tmp"
  mv "${LOG_FILE}.tmp" "${LOG_FILE}"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Log rotated (kept last 500 lines)." >> "${LOG_FILE}"
fi

exit 0
