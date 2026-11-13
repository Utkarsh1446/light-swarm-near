# Light agents

The research question: can abstract skill be grown in a very small learner that starts with no pretrained corpus, instead of being retrieved from a giant model that has memorised the internet?

The thesis: learners of about 1–30 million parameters, on CPU, from a neutral initialization, driven by curiosity, raised on different curricula, and able to divide work in societies. A task bounty is an intent in the NEAR Intents sense: the requester states a verified solution, and solvers compete to fill it, in whatever asset the requester holds. Public proof, if it is ever claimed, is ARC-AGI pass@2 on unseen evaluation tasks, with cost per task. **No ARC-AGI score is claimed.** No evaluation file was opened.

What this repository actually runs is smaller and has no language model in it. Five learners share one architecture of 326,800 parameters each (1,634,000 in total) and the same random initialization. Each is trained from scratch on its own curriculum, then searches the whole 16-operation catalogue. A NEAR testnet contract is the demonstration that a society can escrow a bounty, check the grid hash, slash a wrong reveal, hire help, and record reputation. It is not a leaderboard of API models.

Live site: https://lightswarm-preview.vercel.app. Read the paper on the site: https://lightswarm-preview.vercel.app/paper.html (source [dashboard/paper.html](dashboard/paper.html)). The explainer is [dashboard/index.html](dashboard/index.html). There is no PDF.

Two frozen runs, neither rerun:

- Ablation 1, commit `4528606`. One prior versus untrained and shuffled-label twins. Depth-2: 43/48 versus 10/48, +68.75 percentage points, 95% interval [56.25, 81.25]; versus shuffled 3/48, +83.3333 [70.8333, 93.75]. Curiosity on minus off, and the old society minus one searcher, are both 0 with interval [0, 0].
- Upbringing, commit `c703d76`. Five learners. On geometry tasks the geometry subject solves 16/16 and the object subject solves 0/16, interval [100, 100]. The other specialist contrasts also clear. Society minus the best single subject (mixed, 60/64) is 61/64, +1.5625 points, interval [0.0, 4.6875], which does not clear. Society minus a compute-matched generalist is 61/64 versus 64/64, −4.6875 points, interval [−10.9375, 0.0], which does not clear.

Tracks: `swarms`, `open`. Function-call keys are the agent-security pattern (limited methods, gas allowance, contract `max_stake`).

## What NEAR does

- The bounty and the bid stakes sit in the contract until reveal, cancel, or timeout.
- `reveal_solution` checks `sha256` of the canonical grid on chain. The preimage is hidden until a later block (`commit_solution` first).
- Payout, helper split, stake return, and slash are NEAR transfers.
- Each agent is meant to be its own sub-account. The contract does not create accounts.
- A function-call key can be limited to `register_agent`, `place_bid`, `commit_solution`, `reveal_solution`, and `subcontract`. The sandbox test checks that this key cannot call `cancel`.
- Reputation is a contract field, so later bids are scored with `confidence * reputation / price`.

Rules: [docs/MARKET_SPEC.md](docs/MARKET_SPEC.md).

## Quickstart

Do: `pip install -r requirements.txt`

See: numpy 1.26.4 installed. Python 3.12 is enough.

Do: `python -m unittest discover -s tests -v`

See: 18 tests, all ok. They cover the grid hash, the market twin, a quick simulation, the paired-bootstrap helper, and a check that the browser engine matches the Python learners on a fixed draw. They do not rescore the frozen ablations.

Do: `python -m swarm.sim --offline --rounds 20 --seed 1`

See: `out/run.json` and a rewritten `dashboard/data.js`. The seed-1 run committed in `docs/media/run.json` solved 19 of 20 tasks, slashed 2 wrong answers, and split 3 payouts. Final reputation: geo 1388, colour 1348, object 1708, curious 1231, mapfit 880.

Do: `python -m http.server 8765 --directory dashboard` and open `http://127.0.0.1:8765/`

See: an interactive explainer. Generate a grid task, run the five learners step by step, open a subject card, hover the specialization heatmap, toggle the two frozen experiments, replay the market, and request a dry NEAR Intents quote. `?frame=20` limits the trial table. The page reads `dashboard/data.js`, `dashboard/ablation.js`, `dashboard/upbringing.js`, and `dashboard/weights/`. GitHub Pages publishes this page when the repository is public. The hosted check is pending that change. The workflow is `.github/workflows/pages.yml` (`push` to `main` and `workflow_dispatch`).

Do: `cd contract && cargo test`

See: 8 unit tests and 1 sandbox test. The sandbox test deploys wasm, creates a sub-account, pays the solver 0.4 NEAR of the bounty, returns the stake, and rejects `cancel` from a function-call key. It downloads near-sandbox 2.10.0 on first run (network). Rust 1.100.0 is pinned in `rust-toolchain.toml`. `pkg-config` and `libssl-dev` are required by the sandbox client.

## Testnet

Deployed account: `lightswarm16771.testnet`

Do: `near contract call-function as-read-only lightswarm16771.testnet get_stats json-args '{}' network-config testnet now`

See: `tasks_posted` 1, `max_stake` `"1000000000000000000000000"` (1 NEAR).

Do: `near contract call-function as-read-only lightswarm16771.testnet get_task json-args '{"task_id":1}' network-config testnet now`

See: status `open`, bounty `100000000000000000000000` (0.1 NEAR), answer hash `dc0be30dfb22566bbd5cdb3cc68c0617305d13377a3107320d87e3d86384c9a6` which is `sha256("12;30")`.

Links:

- Account: https://testnet.nearblocks.io/address/lightswarm16771.testnet
- Deploy and init transaction: https://explorer.testnet.near.org/transactions/8P5YnnDDNHzkauU2gsL3pFsHnhRxCr7L1PYXN4EpzC6Y
- `post_task` transaction: https://explorer.testnet.near.org/transactions/77kAs6SAivubtjkqeKzpiUNS4Q8CWUuL7svSmEG1jFTc

The full-access key for that account is not in this repository. Judges can read the contract. They cannot sign for it. To deploy a copy you control:

Do: set `NEAR_ACCOUNT` to a funded testnet account already in the near-cli-rs keychain, then `bash scripts/deploy_testnet.sh`

See: a new contract on that account and a `get_stats` view.

Do: `NEAR_CONTRACT_ID=$NEAR_ACCOUNT bash scripts/provision_agents.sh`

See: sub-accounts `geo`, `colour`, `object`, `curious`, and `mapfit` under `NEAR_ACCOUNT`, each with a function-call key whose methods are the five agent methods above.

`python -m swarm.sim --testnet` exits 2 and does not spend tokens. The offline twin is the reproducible run.

Public RPC used for the deploy: `https://rpc.testnet.near.org` (testnet, nearcore 2.14.1 at deploy time). The account was created with the public helper faucet. No mainnet transaction was sent.

## Demo capture

Do: `python scripts/demo.py`

See: `docs/media/run.json`, `docs/media/dashboard.png`, `docs/media/frame_01.png` through `frame_04.png` (rounds 5, 10, 15, 20), and `docs/media/dashboard.gif`. Chrome is optional; without it the script still writes the JSON. The shot list is printed at the end.

Draft post, not published: [docs/DEMO_POST.md](docs/DEMO_POST.md).

## Architecture

```
requester                contract (NEAR)
   post_task  --------->  escrow bounty, store answer hash
agents (sub-accounts)
   place_bid  --------->  escrow stake, record price and confidence
   assign_best -------->  requester picks max confidence * reputation / price
   subcontract -------->  one helper, at most half the price
   commit_solution ---->  sha256(grid|salt), must reveal next block
   reveal_solution ---->  sha256(grid) == answer hash, else slash and reopen
dashboard <------------  replay of docs/media/run.json (offline) or explorer links
```

| Piece | Path | Role |
| --- | --- | --- |
| Contract | `contract/src/lib.rs` | Escrow, hash check, slash, split, reputation |
| Sandbox test | `contract/tests/sandbox.rs` | wasm, sub-account, limited key |
| Market twin | `swarm/market.py` | Same rules, used by the offline sim |
| Grid language | `swarm/dsl.py` | 16 parameter-free ops |
| Tasks | `swarm/tasks.py` | Seeded synthetic generator |
| Prior | `swarm/prior.py` | 326,800-parameter numpy MLP |
| Agents | `swarm/agents.py` | Five upbringings |
| Sim | `swarm/sim.py` | 20-round loop |
| Dashboard | `dashboard/` | Static replay |

Agent upbringings, all starting at reputation 1000:

| Agent | Search | Bid fraction of bounty | Confidence |
| --- | --- | --- | --- |
| geo | 6 geometry ops, depth at most 2 | 0.34 | 9500 |
| colour | 4 recolour ops | 0.34 | 9500 |
| object | 6 object ops, including `paint_largest` | 0.50 | 9300 |
| curious | beam 6 over all 16 ops, budget 48, novelty bonus 1.5, hires the specialist of the second op at 2000 bps | 0.66 | 7400 |
| mapfit | one global colour map or no bid | 0.36 | 9100 |

After a win, the fraction grows by `base * 15 * max(0, reputation-1000) / 100000`, capped at 0.92. A loss does not cut the price. It cuts reputation by 60, which cuts the assignment score.

## Design

The outer stack, and the label for each piece:

| Piece | Where it stands |
| --- | --- |
| Neutral recursive core | Roadmap |
| Curiosity and novelty | Built here as a bonus on an unseen one-step behaviour |
| Learned program prior | Built here, 326,800 parameters, trained from scratch |
| Search over a grid language | Built here, 16 operations. The broader system uses a larger language and a deeper search |
| Skill library that keeps only skills that replay | Roadmap |
| Upbringings | Built here, five curricula, one initialization |
| Society | Built here, one NEAR market. It did not beat its best member |
| Society of societies | Roadmap |
| Task bounty as a NEAR Intents outcome | Design. Verification is the contract. Cross-chain pay is a dry 1Click quote |
| Sub-accounts and function-call keys | Built here |
| Chain Signatures | Roadmap |

Earlier work on the same question, not rerun here: a synthetic generalisation gate passed; a real-task confirmation failed; a deeper-search gate failed its control.

Evaluation principles: freeze the protocol and the draw before scoring, matched untrained and shuffled controls, paired bootstrap, a contrast clears only when the lower bound is above 0, held-out grids stay sealed.

No ARC-AGI evaluation result is claimed. No official evaluation file was opened to build this repository.

## Disclosure

- License: MIT, `LICENSE`, copyright 2026 Utkarsh Tiwari.
- Libraries: `near-sdk` 5.5.0, `near-workspaces` 0.22.1 (near-sandbox 2.10.0), `numpy` 1.26.4, Python 3.12, near-cli-rs 0.31.1 for the testnet deploy, Chrome and ffmpeg for `docs/media`. No paid API and no NEAR AI key.
- AI assistance: a Cursor Grok coding agent wrote this repository from the hackathon task. The agent did not submit the hackathon form and did not post on X.
- Grid tasks are procedural. See `swarm/tasks.py`. The five weight files in `dashboard/weights/` are the upbringing learners, exported so the explainer can run them in the browser.

Paper: https://lightswarm-preview.vercel.app/paper.html (source [dashboard/paper.html](dashboard/paper.html); [docs/paper.html](docs/paper.html) is the plain record it is tested against). `docs/PAPER.md` points at those. Do not rescore `experiments/score.py`; the result file already exists and the script will refuse.
