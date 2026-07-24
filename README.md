# anetrebskii marketplace

Personal Claude Code plugin marketplace.

## Plugins

### no-coauthor

Strips the `Co-Authored-By:` trailer from git commit commands before they run, so
Claude Code commits are attributed to you alone (no co-author / contributor entry).

Mechanism: a `PreToolUse` hook on the `Bash` tool. When a `git commit` command
carries a `Co-Authored-By` line, the hook removes that line and returns the cleaned
command via `updatedInput`. It emits no `permissionDecision`, so your normal
commit-approval flow is unchanged.

## Install

```
/plugin marketplace add anetrebskii/claude-plugins
/plugin install no-coauthor@anetrebskii
```
