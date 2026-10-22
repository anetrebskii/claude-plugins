#!/bin/sh
set -eu

plugin_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
allowed_ips_file=${VPN_GUARD_ALLOWED_IPS_FILE:-"$plugin_root/allowed-ips.txt"}
log_file=${VPN_GUARD_LOG_FILE:-"${XDG_STATE_HOME:-$HOME/.local/state}/vpn-guard/checks.log"}

log() {
  (mkdir -p -- "$(dirname -- "$log_file")" && printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$log_file") 2>/dev/null || :
}

if [ ! -r "$allowed_ips_file" ]; then
  log "blocked: cannot read settings: $allowed_ips_file"
  printf 'VPN Guard: cannot read settings: %s; request blocked.\n' "$allowed_ips_file" >&2
  exit 2
fi

if ! errors_file=$(mktemp "${TMPDIR:-/tmp}/vpn-guard.XXXXXX"); then
  printf 'VPN Guard: cannot create lookup diagnostics; request blocked.\n' >&2
  exit 2
fi
trap 'rm -f -- "$errors_file"' EXIT
trap 'exit 2' HUP INT TERM

started=$(date +%s)
deadline=$((started + 10))
attempt=0
for endpoint in https://api.ipify.org https://checkip.amazonaws.com https://api.ipify.org; do
  remaining=$((deadline - $(date +%s)))
  if [ "$remaining" -le 0 ]; then break; fi
  timeout=3
  if [ "$remaining" -lt "$timeout" ]; then timeout=$remaining; fi
  attempt=$((attempt + 1))
  curl_exit=0
  public_ip=$(curl --ipv4 --proto '=https' --fail --silent --show-error --connect-timeout 2 --max-time "$timeout" "$endpoint" 2> "$errors_file") || curl_exit=$?
  elapsed=$(($(date +%s) - started))
  if [ "$elapsed" -ge 10 ]; then
    log "attempt=$attempt endpoint=$endpoint elapsed_s=$elapsed curl_exit=$curl_exit deadline exceeded"
    break
  fi
  if [ "$curl_exit" -ne 0 ]; then
    details=$(tr '\r\n' '  ' < "$errors_file" | cut -c 1-400)
    log "attempt=$attempt endpoint=$endpoint elapsed_s=$elapsed curl_exit=$curl_exit $details"
    continue
  fi
  if ! printf '%s\n' "$public_ip" | awk -F. 'NF != 4 { exit 1 } { for (i = 1; i <= 4; i++) if ($i !~ /^(0|[1-9][0-9]*)$/ || length($i) > 3 || $i > 255) exit 1; count++ } END { if (count != 1) exit 1 }'; then
    log "attempt=$attempt endpoint=$endpoint elapsed_s=$elapsed curl_exit=0 invalid IPv4 response"
    continue
  fi
  if grep -Fxq -- "$public_ip" "$allowed_ips_file"; then
    if [ "$attempt" -gt 1 ]; then log "recovered attempt=$attempt endpoint=$endpoint elapsed_s=$elapsed ip=$public_ip"; fi
    exit 0
  fi
  log "blocked attempt=$attempt endpoint=$endpoint elapsed_s=$elapsed ip=$public_ip not allowed"
  printf 'VPN Guard: public IP %s is not allowed; request blocked. Settings: %s\n' "$public_ip" "$allowed_ips_file" >&2
  exit 2
done

log "blocked: public IP lookup failed after $attempt attempts"
printf 'VPN Guard: public IP lookup failed after %s attempts; request blocked. Diagnostics: %s\n' "$attempt" "$log_file" >&2
exit 2
