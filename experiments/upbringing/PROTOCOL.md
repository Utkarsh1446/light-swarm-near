# Frozen upbringing protocol

Numbers live in `experiments/upbringing/freeze.json`. This page matches that file. The earlier protocol in `experiments/PROTOCOL.md` is a different experiment and is not rerun.

Status: frozen before scoring. One run.

## Question

Five learners share one architecture and one random initialization. Each is then trained from scratch on its own curriculum. Search always uses the full 16-operation catalogue. Does upbringing change which task families each subject solves? Does the society solve more hidden tests than the best single subject, and more than one generalist given the same total training examples and the same total program-check budget?

## Subjects

| Name | Curriculum | Training rows | Label noise | Curiosity | Subcontract |
| --- | --- | --- | --- | --- | --- |
| geo | programs whose operations are all geometric | 1600 | 0 | 0 | no |
| colour | recolour operations only | 1600 | 0 | 0 | no |
| object | object and layout operations only | 1600 | 0 | 0 | no |
| mixed | operations drawn from the whole catalogue | 1600 | 0 | 1.5, archive persists across the frozen task order | yes, hires the other learner with the highest logit on the second operation |
| noisy | whole catalogue, small data | 200 | 0.25 chance each positive label moves to a different operation | 0 | no |

Width 384, three hidden layers, init seed 20261117 for every subject, so the weights match before training. Adam seeds are 20261123 plus the subject index. Training seeds are 20261121 plus the subject index. Learning rate 0.01, 6 epochs.

Features are the usual 64, with coordinates 33 through 48 set to 0. Those coordinates are single-operation residuals. Leaving them on would tell every curriculum the depth-1 answer. The first ablation did not mask them. This one does.

## Generalist

One extra network, not a member of the society. Mixed curriculum, no label noise, no curiosity, init seed 20261117, train seed 20261129, Adam seed 20261131, 8000 rows (5 times 1600), 6 epochs. Search beam 15 and budget 240, against the society's five beams of 6 and budgets of 48 (at most 240 program checks). Training examples and the program-check cap match. The generalist is one searcher, so it does not get five chances to be wrong and recover.

## Draws

Search tasks, seed 20261118, stored in `experiments/upbringing/frozen/search_tasks.json` before scoring. 16 tasks in each of geo, colour, object, and cross. Single-family tasks use one operation from that family. Cross tasks use two operations from two families. Three grids must change and stay within side 12. Two are demonstrations. One is the hidden test.

Market tasks, seed 20261119, stored in `experiments/upbringing/frozen/market_tasks.json`. 24 tasks from `generate_task` in schedule order, including traps. This is the payment trial. It is not the powered contrast.

## Metrics

A subject solves a search task when the program it accepts fits the demonstrations and the grid it predicts equals the hidden test. Archives reset every task except the mixed subject's curiosity archive, which persists in file order.

Society solve on the search tasks is the market status after every learner may bid, using the confidence and price rule in `confidence_from_prior` and `Agent.quote`. A wrong reveal is slashed and the task reopens.

Contrasts, bootstrap seed 0, 10,000 resamples, NumPy 1.26.4 linear quantiles, percentiles 2.5 and 97.5:

1. On geo tasks, geo minus colour, and geo minus object. Same for colour's tasks and object's tasks. Paired.
2. Society minus the best single subject on the 64 search tasks. The best subject is the one with the most solves. The interval chooses the best subject again inside each resample.
3. Society minus the generalist on the same 64 tasks. Paired.

The 24-task market trial records reputation and who was paid. Its solve counts are described, not used as a primary gate.

A contrast clears only if the lower bound is strictly above 0. Otherwise it is a null or a loss, as the numbers say.

## One shot

`experiments/upbringing/score.py` refuses a dirty worktree and refuses to overwrite `experiments/upbringing/results/ablation.json`. It records `git rev-parse HEAD`. It does not read or write `experiments/results/ablation.json`.
