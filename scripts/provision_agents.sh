#!/usr/bin/env bash
# Create agent sub-accounts and function-call keys on testnet.
# near-cli-rs 0.31. The parent account must already be in the keychain.
# Allowance limits gas. The contract's max_stake limits the attached bid.
set -euo pipefail

if [[ -z "${NEAR_ACCOUNT:-}" ]]; then
  echo "Set NEAR_ACCOUNT to the funded parent testnet account." >&2
  exit 1
fi
CONTRACT="${NEAR_CONTRACT_ID:-$NEAR_ACCOUNT}"

for name in geo colour object curious mapfit; do
  echo "Creating ${name}.${NEAR_ACCOUNT}"
  near account create-account fund-myself "${name}.${NEAR_ACCOUNT}" '3 NEAR' \
    autogenerate-new-keypair save-to-keychain \
    sign-as "$NEAR_ACCOUNT" \
    network-config testnet \
    sign-with-keychain \
    send

  near account add-key "${name}.${NEAR_ACCOUNT}" \
    grant-function-call-access \
    --allowance '0.5 NEAR' \
    --contract-account-id "$CONTRACT" \
    --function-names 'register_agent,place_bid,commit_solution,reveal_solution,subcontract' \
    autogenerate-new-keypair save-to-keychain \
    network-config testnet \
    sign-with-keychain \
    send
done

echo "Each agent key may call register_agent, place_bid, commit_solution, reveal_solution, subcontract on $CONTRACT."
echo "It may not call cancel, post_task, or assign_best."
