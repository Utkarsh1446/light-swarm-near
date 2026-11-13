# Market rules

The Python ledger in `swarm/market.py` and the Rust contract in `contract/src/lib.rs` implement this spec. Amounts are integers. On chain they are yoctoNEAR. Offline they are the same integers at a smaller scale (`1_000_000` bounty, `100_000` stake).

## Constants

| Name | Value |
| --- | --- |
| Initial reputation | 1000 |
| Solve bonus | `40 + confidence_bps / 200` |
| Helper bonus | 20 |
| Failed reveal or timeout | reputation decreases by 60, floored at 0 |
| Max bids per task | 8 |
| Max helper share | 5000 bps (half the price) |
| Grid | digits 0-9, rows joined by `;`, at most 30 by 30 |
| Answer hash | lowercase hex sha256 of the canonical grid |
| Commitment | lowercase hex sha256 of `canonical + "\|" + salt` |
| Salt | 1 to 64 ASCII letters or digits |

Known vector: `sha256("12;30")` = `dc0be30dfb22566bbd5cdb3cc68c0617305d13377a3107320d87e3d86384c9a6`. Commitment of that grid with salt `abc` = `32001f14d790be3047995d91e37743245991f57c932807fcbbb73ecff0bfd690`.

## Calls

`register_agent` creates reputation 1000 if missing. `place_bid` registers on first use.

`post_task` escrows the attached deposit as the bounty. The requester stores demos, the visible test input, and the answer hash. Stake required must be positive and at most `max_stake`.

`place_bid` attaches the stake. Price must be positive and at most the bounty. Confidence is 1 to 10000. One bid per account. The requester cannot bid.

`assign_best` is requester-only, and only while the task is open. Score is `confidence_bps * reputation / price`, integer division. The winner is the highest score, then the lower price, then the lexicographically smaller account. The deadline becomes the current block plus the task window.

`subcontract` is assignee-only, one helper, helper already registered, helper is not the assignee or the requester, share 1 to 5000 bps.

`commit_solution` stores a 64-char lowercase hex commitment and the current block. `reveal_solution` must be in a later block. A commitment mismatch or an answer-hash mismatch slashes the stake to the requester, drops reputation, and reopens the task. A match pays `price` to the assignee after the helper cut, refunds `bounty - price` to the requester, and returns every non-slashed stake.

`cancel` is requester-only and only while the task is open. It returns the bounty and every non-slashed stake.

`slash_timeout` anyone can call once the block is past the deadline of an assigned task. It slashes like a wrong answer.

## What the contract does not do

It does not create sub-accounts or access keys. Those are account-layer actions. A function-call key for an agent should allow `register_agent`, `place_bid`, `commit_solution`, `reveal_solution`, and `subcontract` only. Allowance limits gas. `max_stake` limits how much NEAR one bid can escrow.
