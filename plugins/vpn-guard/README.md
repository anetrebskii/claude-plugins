# VPN Guard

VPN Guard permits supported model-processing steps only when the public IPv4 address matches the allowlist. A failed lookup, missing settings or unexpected IP blocks the step.

## Settings

Edit `allowed-ips.txt` in this plugin directory. It contains one allowed IP per line:

```text
163.123.141.18
207.90.237.248
```

To keep settings outside the installed plugin cache, create your own allowlist and set `VPN_GUARD_ALLOWED_IPS_FILE` before starting the agent:

```sh
mkdir -p ~/.config/vpn-guard
printf '163.123.141.18\n207.90.237.248\n' > ~/.config/vpn-guard/allowed-ips.txt
export VPN_GUARD_ALLOWED_IPS_FILE="$HOME/.config/vpn-guard/allowed-ips.txt"
```

Both Claude Code and Codex use the same checker and settings. Desktop applications must inherit this environment variable; otherwise they use the bundled allowlist. Plugin updates can replace bundled settings.

The checker requires `curl`. Every hook invocation performs a fresh IPv4 lookup over HTTPS and compares it exactly against the allowlist. An unapproved IP blocks immediately. Failed or malformed lookups get up to three attempts: ipify, [Amazon's IP endpoint](https://docs.aws.amazon.com/batch/latest/userguide/create-a-base-security-group.html), then ipify again. Each attempt has a three-second limit, with a ten-second deadline for verification. The lookup itself is an outbound request; connection status and earlier successful checks cannot bypass it.

## Diagnostics

Failures, recovery and IP mismatches are logged to `${XDG_STATE_HOME:-$HOME/.local/state}/vpn-guard/checks.log`. The log records the endpoint, attempt, elapsed seconds, curl exit code and error. Successful first attempts stay silent. Logs contain no prompts or tool output.

Set `VPN_GUARD_LOG_FILE` before starting Claude to use another log path. Logging failure does not change the IP-check result. Final lookup errors show the diagnostics path; restore connectivity and resubmit after a blocked check.

Recovery states and limits are documented in [the UX document](../../doc/ux/vpn-guard-recovery.md).

Run deterministic checks without network access:

```sh
python3 plugins/vpn-guard/tests/test_check_vpn.py
VPN_TEST_SHELL=/bin/bash python3 plugins/vpn-guard/tests/test_check_vpn.py
```

## Claude Code

The Claude plugin checks `UserPromptSubmit` and `PostToolBatch`. The latter runs after tool results and before Claude Code sends the next model request, so the check repeats during tool-driven continuations.

Install from the published marketplace:

```sh
claude plugin marketplace add anetrebskii/claude-plugins
claude plugin install vpn-guard@anetrebskii --scope user
```

Restart Claude Code after installation so it loads the hooks.

To install unpublished local changes, register the source checkout and update the existing plugin:

```sh
claude plugin marketplace add /absolute/path/to/claude-plugins
claude plugin update vpn-guard@anetrebskii --scope user
```

This declares the checkout in `extraKnownMarketplaces` in `~/.claude/settings.json`. To restore published updates, remove that new `anetrebskii` entry, then run `claude plugin marketplace add anetrebskii/claude-plugins`. Keep other marketplace declarations. The installed version remains until another update.

## Codex

The Codex plugin checks `UserPromptSubmit`, before Codex processes a submitted prompt. Current Codex plugin hooks do not expose a pre-model hook for every internal continuation, so they cannot provide the same per-request gate as Claude Code. Use an OS-level network rule or VPN kill switch if every model request must be restricted to the VPN.

Add the published repository as a marketplace:

```sh
codex plugin marketplace add anetrebskii/claude-plugins
codex plugin marketplace upgrade anetrebskii
codex plugin add vpn-guard@anetrebskii
```

Start a fresh Codex CLI session and enter `/hooks`. Under `UserPromptSubmit`, review and trust the VPN Guard hook. The plugin also appears under **Alex's Personal Plugins** in the Codex desktop Plugins Directory. Installing the plugin alone does not trust its hooks. Start a new conversation after installation.

For local development, use `codex plugin marketplace add /absolute/path/to/claude-plugins` instead.
