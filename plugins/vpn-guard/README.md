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

The checker requires `curl`. On every hook invocation it requests the public IPv4 address from `https://api.ipify.org` over HTTPS, with an eight-second timeout, and compares the response exactly against the allowlist. It does not use VPN connection status or a custom checker as a bypass. The lookup itself is an outbound request.

## Claude Code

The Claude plugin checks `UserPromptSubmit` and `PostToolBatch`. The latter runs after tool results and before Claude Code sends the next model request, so the check repeats during tool-driven continuations.

Install from the published marketplace:

```sh
claude plugin marketplace add anetrebskii/claude-plugins
claude plugin install vpn-guard@anetrebskii --scope user
```

Restart Claude Code after installation so it loads the hooks.

## Codex

The Codex plugin checks `UserPromptSubmit`, before Codex processes a submitted prompt. Current Codex plugin hooks do not expose a pre-model hook for every internal continuation, so they cannot provide the same per-request gate as Claude Code. Use an OS-level network rule or VPN kill switch if every model request must be restricted to the VPN.

Add the published repository as a marketplace:

```sh
codex plugin marketplace add anetrebskii/claude-plugins
```

Then open the Codex desktop Plugins Directory, select **Alex's Personal Plugins**, install **vpn-guard**, and review and trust its hook definition. Installing the plugin alone does not trust its hooks. Start a new conversation after installation.

For local development, use `codex plugin marketplace add /absolute/path/to/claude-plugins` instead.
