# anetrebskii marketplace

Personal Claude Code plugin marketplace.

## Plugins

### no-coauthor

Strips Claude `Co-Authored-By:` trailers from `git` and `gh` commands before
they run.

Mechanism: a `PreToolUse` hook on the `Bash` tool. It removes the trailer plus
the blank separator in front of it and returns the cleaned command via
`updatedInput`. It emits no `permissionDecision`, so the normal
commit-approval flow is unchanged.

Handled forms:

```
git commit -F- <<'EOF' ... EOF     # heredoc message
git commit -m "msg" -m "Co-..."    # repeated -m
git commit -m $'msg\n\nCo-...'     # escaped newlines in one argument
git commit -m "msg" --trailer "Co-..."
gh pr create --body "...Co-..."    # also gh pr edit / issue create / comment
```

Rules:

- Only Anthropic/Claude trailers are removed. A human `Co-Authored-By:` line is
  left alone.
- The trailer is cut as a substring ending at `>`, not as a whole line, so
  quoting in single-line commands stays balanced.
- Fails open. If the rewrite would empty the command, leave a trailer behind, or
  strip the only message source off a `git commit`, the command passes through
  untouched.
- `git log --grep=...` and other searches for the trailer are not rewritten.

Not handled: a message written to a file first and committed with
`git commit -F msg.txt`, and the `🤖 Generated with Claude Code` line in PR
bodies. GitHub also re-adds `Co-authored-by:` to squash-merge commits on its own
side, which no local hook can prevent.

Tests:

```
bash plugins/no-coauthor/tests/run.sh
```

## Install

```
/plugin marketplace add anetrebskii/claude-plugins
/plugin install no-coauthor@anetrebskii
```
