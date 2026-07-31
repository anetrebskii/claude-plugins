#!/bin/bash
# PreToolUse(Bash) guardrail: strip Claude co-author trailers from git/gh
# commands so nothing Claude Code writes carries co-author attribution.
#
# Removes the trailer itself plus the blank separator in front of it, instead of
# deleting whole lines, so single-line forms survive:
#   git commit -m "msg" -m "Co-Authored-By: Claude Opus 5 (1M context) <...>"
#   git commit -m "msg" --trailer "Co-Authored-By: ... <...>"
#   gh pr create --body "body\n\nCo-Authored-By: ... <...>"
# Only Anthropic/Claude trailers are touched; human co-authors are kept.
# Fails open: if the rewrite would empty the command or leave a trailer behind,
# the command passes through untouched.
set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# Nothing to do unless a Claude/Anthropic co-author trailer is present.
printf '%s' "$command" | grep -qiE 'co-authored-by:[^<]*(claude|anthropic)' || exit 0

# Only rewrite git/gh invocations; leave everything else alone.
printf '%s' "$command" | grep -qE '(^|[^[:alnum:]_])(git|gh)([^[:alnum:]_]|$)' || exit 0

# Searching for the trailer is not writing it.
case "$command" in
  grep\ *|rg\ *|*--grep*) exit 0 ;;
esac

# 1. drop "<blank separator>Co-Authored-By: Name <email>", where the separator
#    is real newlines or literal \n escapes, and the trailer stops at ">" so
#    surrounding quotes stay balanced
# 2. drop the -m/--trailer flag left holding an empty string
cleaned=$(printf '%s' "$command" | jq -Rsr '
  gsub("(?:[ \t]*(?:\\\\n|\n))*[ \t]*co-authored-by:(?=[^\n]*(?:claude|anthropic))[^\n<]*<[^\n>]*>[ \t]*"; ""; "i")
  | gsub("[ \t]*(?:-m|--message|--trailer)[ \t]+[\"\\x27]{2}"; "")
')

# A message the trailer was the whole of would leave "git commit" with nothing
# to commit from, which drops into an editor.
has_message() {
  printf '%s' "$1" | grep -qE -- '(^|[[:space:]])(-m|--message|-F|--file|-c|-C|-t|--template|--amend)([[:space:]=]|$)|<<'
}

if [ "$cleaned" = "$command" ]; then exit 0; fi
if printf '%s' "$cleaned" | grep -qi 'co-authored-by'; then exit 0; fi
if ! printf '%s' "$cleaned" | grep -q '[^[:space:]]'; then exit 0; fi
if has_message "$command" && ! has_message "$cleaned"; then exit 0; fi

# Merge over the original input so description/timeout/run_in_background survive.
printf '%s' "$input" | jq --arg cmd "$cleaned" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    updatedInput: (.tool_input + { command: $cmd })
  }
}'
