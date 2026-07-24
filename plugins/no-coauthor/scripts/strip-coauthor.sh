#!/bin/bash
# PreToolUse(Bash) guardrail: strip any "Co-Authored-By:" trailer line from
# git commit commands so Claude Code commits do not add co-author attribution.
# Returns updatedInput with the cleaned command; no permissionDecision, so the
# normal commit-approval flow is untouched.
set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# Only touch git commits that actually carry the trailer.
printf '%s' "$command" | grep -qi 'git commit' || exit 0
printf '%s' "$command" | grep -qi 'Co-Authored-By' || exit 0

# Drop every line that contains a Co-Authored-By trailer.
cleaned=$(printf '%s' "$command" | grep -vi 'Co-Authored-By' || true)

jq -n --arg cmd "$cleaned" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    updatedInput: { command: $cmd }
  }
}'
