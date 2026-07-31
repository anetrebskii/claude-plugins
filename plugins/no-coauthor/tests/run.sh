#!/bin/bash
# Feeds PreToolUse payloads to the hook and checks the rewritten command.
# Usage: plugins/no-coauthor/tests/run.sh
set -uo pipefail

hook="$(cd "$(dirname "$0")/.." && pwd)/scripts/strip-coauthor.sh"
T='Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>'
fails=0

# expect: rewritten command, or the literal PASSTHROUGH when the hook must not fire
check() {
  local name=$1 cmd=$2 expect=$3 out got
  out=$(printf '%s' "$cmd" | jq -Rs '{tool_name:"Bash",tool_input:{command:.,description:"d"}}' | bash "$hook")
  if [ -z "$out" ]; then
    got=PASSTHROUGH
  else
    got=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.command')
    if [ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.description // ""')" != "d" ]; then
      echo "FAIL $name: updatedInput dropped sibling fields"
      fails=$((fails + 1))
    fi
  fi
  if [ "$got" = "$expect" ]; then
    echo "ok   $name"
  else
    echo "FAIL $name"
    printf '  expected: %q\n  got:      %q\n' "$expect" "$got"
    fails=$((fails + 1))
  fi
}

check "heredoc" \
  "git commit -F- <<'EOF'
fix: thing

$T
EOF" \
  "git commit -F- <<'EOF'
fix: thing
EOF"

check "heredoc with trailing command" \
  "git commit -q -F - <<'EOF' && git log --oneline -1
fix: thing

$T
EOF" \
  "git commit -q -F - <<'EOF' && git log --oneline -1
fix: thing
EOF"

check "repeated -m" \
  "git commit -m \"fix: thing\" -m \"$T\"" \
  'git commit -m "fix: thing"'

check "escaped newlines in one -m" \
  "git commit -m \$'fix: thing\\n\\n$T'" \
  "git commit -m \$'fix: thing'"

check "--trailer" \
  "git commit -m \"fix\" --trailer \"$T\"" \
  'git commit -m "fix"'

check "gh pr create body" \
  "gh pr create --title x --body \"body text\\n\\n$T\"" \
  'gh pr create --title x --body "body text"'

check "lowercase spelling" \
  "git commit -m \"fix\" -m \"co-authored-by: Claude <noreply@anthropic.com>\"" \
  'git commit -m "fix"'

check "human co-author kept" \
  'git commit -m "fix" -m "Co-Authored-By: Dev <dev@example.com>"' \
  PASSTHROUGH

check "trailer-only message is not emptied" \
  "git commit -m \"$T\"" \
  PASSTHROUGH

check "searching for the trailer" \
  "git log --grep=\"$T\"" \
  PASSTHROUGH

check "non-git command" \
  "echo \"$T\" >> notes.txt" \
  PASSTHROUGH

echo
if [ "$fails" -eq 0 ]; then echo "all passed"; else echo "$fails failed"; exit 1; fi
