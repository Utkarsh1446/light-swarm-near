# Frozen ablation protocol

Authority for the numbers is `experiments/freeze.json`. This page is the human reading. `tests/test_stats.py` checks that the seeds and sample sizes below match the JSON. Scoring reads the JSON, not this page.

Status: frozen before the scored run. One run. If a contrast's 95% interval includes 0 or is negative, that is the result. Do not change seeds, widths, budgets, or the task files and run again.

## Question

On fresh synthetic grids from this repository's 16-operation language, does a prior trained from scratch beat an untrained net and a shuffled-label twin at the same search budget? Does a curiosity bonus change that search? Does the five-subject society solve more of a fixed task list than the curious subject alone?

No ARC file is read. No language model is called. The metric is exact match of the predicted grid to the hidden test grid.

## Draws

| Draw | Seed | n | What |
| --- | --- | --- | --- |
| Search tasks | 20261113 | 48 depth-2, 24 depth-1 | Stored in `experiments/frozen/search_tasks.json` before scoring |
| Society tasks | 20261115 | 24 | `generate_task` families, schedule order, stored in `experiments/frozen/society_tasks.json` |
| Training traces | 20261111 | 1600 kept | The same draw as `sample_trace`: with probability 1/2 one operation, otherwise two, then `_grid_for`. Unchanged outputs and outputs with a side above 16 are rejected. A trace whose input/output canonical pair appears in the search tasks is dropped and replaced. |

Depth-2 programs are ordered pairs of operations from two different families. Depth-1 programs are a single uniform operation. A draw is kept only when three fresh inputs all change under the program and the outputs stay at most 12 cells on a side. Two inputs are demonstrations. The third is the hidden test.

## Models

One architecture: 64 features, three hidden layers of width 384, 16 outputs. Init seed 20261107, a fresh NumPy generator per arm so the three arms share an initialization.

- Learned: 6 epochs, Adam learning rate 0.01, Adam shuffle seed 20261109, true multi-hot labels.
- Untrained: that initialization, no training. Search cost matches. Training cost does not. The protocol says so.
- Shuffled: the same traces, epochs, and Adam seed, with each label vector rolled forward by 1. Operation i's bit moves to operation i+1 (mod 16). No operation keeps its own label.

## Search budget

Every search arm uses the repository's curious search: beam 6, at most 48 demo-fit checks, curiosity weight 0, and a new empty archive on every task. The 16 single-op residual features inside `featurize` are computed for every arm. That is the matched budget.

Curiosity contrast, same learned weights, same depth-2 tasks, same order: weight 1.5 versus weight 0. The archive starts empty and persists across the 48 tasks. It is not reset per task.

## Society contrast

Same learned weights. Bounty 1,000,000, stake 100,000, the market rules in `docs/MARKET_SPEC.md`.

- Society: the five subjects in `default_agents`, curious curiosity 1.5, subcontract on.
- Single: only the curious subject, curiosity 1.5, subcontract off.

A task counts as solved when the market status is `solved`. That status already means the revealed grid matched the answer hash.

## Statistics

Paired bootstrap, 10,000 resamples, seed 0, NumPy 1.26.4 quantile method `linear`, percentiles 2.5 and 97.5. The point is the mean of left minus right, reported in percentage points. A contrast clears only if the lower bound is strictly greater than 0. Discordant counts are reported and are not the rule.

Primary contrasts:

1. Depth-2 test-exact, learned minus untrained.
2. Depth-2 test-exact, learned minus shuffled.
3. Depth-2 test-exact, curiosity on minus curiosity off.
4. Society tasks solved, society minus single curious.

Secondary, not gates: the same prior contrasts on depth-1; per-family solve counts; the fraction of test-exact search solves whose returned program equals the generator (alias description).

## One shot

`experiments/score.py` refuses to start if `experiments/results/ablation.json` exists or if the git worktree is dirty. It records `git rev-parse HEAD`. Run it once on the freeze commit. Do not edit the scorer and run it again.
