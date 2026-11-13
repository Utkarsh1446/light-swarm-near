#!/usr/bin/env bash
# Deploy the market contract to an account you already control on NEAR testnet.
# near-cli-rs 0.31 command shape, checked against `near --help`.
# Does not create an account and does not print keys.
set -euo pipefail

if ! command -v near >/dev/null 2>&1; then
  echo "near-cli-rs is not on PATH. https://github.com/near/near-cli-rs" >&2
  exit 1
fi
if [[ -z "${NEAR_ACCOUNT:-}" ]]; then
  echo "Set NEAR_ACCOUNT to a funded testnet account in your near-cli keychain." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/contract"
cargo build --release --target wasm32-unknown-unknown
WASM="$ROOT/contract/target/wasm32-unknown-unknown/release/light_swarm_market.wasm"

near contract deploy "$NEAR_ACCOUNT" \
  use-file "$WASM" \
  with-init-call new json-args '{"max_stake":"1000000000000000000000000"}' \
  prepaid-gas '80 Tgas' \
  attached-deposit '0 NEAR' \
  network-config testnet \
  sign-with-keychain \
  send

echo "Deployed to $NEAR_ACCOUNT"
echo "View: near contract call-function as-read-only $NEAR_ACCOUNT get_stats json-args '{}' network-config testnet now"
echo "Explorer: https://testnet.nearblocks.io/address/$NEAR_ACCOUNT"
