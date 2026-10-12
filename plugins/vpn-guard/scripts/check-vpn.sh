#!/bin/sh
set -eu

plugin_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
allowed_ips_file=${VPN_GUARD_ALLOWED_IPS_FILE:-"$plugin_root/allowed-ips.txt"}
if [ ! -r "$allowed_ips_file" ]; then
  printf 'VPN Guard: cannot read settings: %s; request blocked.\n' "$allowed_ips_file" >&2
  exit 2
fi

if ! public_ip=$(curl --ipv4 --proto '=https' --fail --silent --show-error --connect-timeout 3 --max-time 8 https://api.ipify.org); then
  printf 'VPN Guard: public IP lookup failed; request blocked.\n' >&2
  exit 2
fi

if [ -n "$public_ip" ] && grep -Fxq -- "$public_ip" "$allowed_ips_file"; then
  exit 0
fi

printf 'VPN Guard: public IP %s is not allowed; request blocked. Settings: %s\n' "$public_ip" "$allowed_ips_file" >&2
exit 2
