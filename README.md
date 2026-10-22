# anetrebskii marketplace

Personal Claude Code plugin marketplace.

## Plugins

### no-coauthor

Automatically removes Claude co-author and session trailers, plus generated/created-by footers, from Git commits and GitHub writes. Preserves human co-authors. Handles inline text, heredocs, message files and GitHub MCP tools.

For an immediate local install with default attribution disabled and RTK rewrites sequenced safely:

```sh
python3 plugins/no-coauthor/scripts/install-local.py
```

Restart Claude Code after installation. See [No Claude Attribution setup, tests and limits](plugins/no-coauthor/README.md).

### vpn-guard

Checks the public IPv4 address against a configured allowlist before submitted prompts. Claude Code also checks before tool-driven model continuations. Includes a Codex plugin manifest and marketplace entry; Codex currently checks submitted prompts only. See [VPN Guard setup and limits](plugins/vpn-guard/README.md).

## Install

```
/plugin marketplace add anetrebskii/claude-plugins
/plugin install no-coauthor@anetrebskii
/plugin install vpn-guard@anetrebskii
```
