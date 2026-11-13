"""Score the frozen ablation once.

Refuses a dirty worktree and refuses to overwrite an existing result file.
A smoke path (`--smoke`) trains a tiny net on two toy tasks and writes under
/tmp. It is not the experiment.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm.agents import Agent, default_agents  # noqa: E402
from swarm.canonical import answer_hash, canonical, commitment, encode_demos, parse_grid  # noqa: E402
from swarm.dsl import OP_NAMES  # noqa: E402
from swarm.market import Market  # noqa: E402
from swarm.prior import Prior, featurize  # noqa: E402
from swarm.rules import DEFAULT_MAX_STAKE, REP_INIT  # noqa: E402
from swarm.stats import cycle_labels, paired_bootstrap  # noqa: E402
from swarm.tasks import TaskSpec  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULT = HERE / "results" / "ablation.json"


def load_freeze() -> dict:
    return json.loads((HERE / "freeze.json").read_text(encoding="utf-8"))


def git_head() -> str:
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if status.strip():
        raise SystemExit("refusing to score: worktree is dirty; commit the freeze first")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def rows_from_json(payload: list[dict]) -> list[dict]:
    parsed = []
    for row in payload:
        demos = [(parse_grid(pair["in"]), parse_grid(pair["out"])) for pair in row["demos"]]
        parsed.append(
            {
                **row,
                "demos_grid": demos,
                "test_in_grid": parse_grid(row["test_input"]),
                "test_out_grid": parse_grid(row["test_output"]),
            }
        )
    return parsed


def seen_pairs(tasks: list[dict]) -> set[tuple[str, str]]:
    pairs = set()
    for task in tasks:
        for pair in task["demos"]:
            pairs.add((pair["in"], pair["out"]))
        pairs.add((task["test_input"], task["test_output"]))
    return pairs


def collect_training_grids(freeze: dict, banned: set[tuple[str, str]]) -> tuple[list, int]:
    """Same generator as sample_trace, but keep grids so eval pairs can be dropped."""
    from swarm.dsl import OP_INDEX, OP_NAMES, apply_program
    from swarm.tasks import _grid_for

    rng = random.Random(freeze["train_seed"])
    rows = []
    dropped = 0
    guard = 0
    limit = freeze["train_n"] * 40
    while len(rows) < freeze["train_n"] and guard < limit:
        guard += 1
        if rng.random() < 0.5:
            program = (OP_NAMES[rng.randrange(len(OP_NAMES))],)
        else:
            program = (OP_NAMES[rng.randrange(len(OP_NAMES))], OP_NAMES[rng.randrange(len(OP_NAMES))])
        grid = _grid_for(rng, program)
        output = apply_program(grid, program)
        if output is None or output == grid or len(output) > 16 or len(output[0]) > 16:
            continue
        pair = (canonical(grid), canonical(output))
        if pair in banned:
            dropped += 1
            continue
        target = np.zeros(len(OP_NAMES), dtype=np.float32)
        for name in dict.fromkeys(program):
            target[OP_INDEX[name]] = 1.0
        rows.append((featurize([(grid, output)]), target))
    if len(rows) < freeze["train_n"]:
        raise RuntimeError(f"only gathered {len(rows)} training rows")
    return rows, dropped


def make_prior(freeze: dict, train: bool, labels, rows) -> Prior:
    prior = Prior(freeze["width"], np.random.default_rng(freeze["init_seed"]))
    if train:
        prior.train(list(zip((row[0] for row in rows), labels, strict=True)), epochs=freeze["epochs"], lr=freeze["lr"], seed=freeze["adam_seed"])
    return prior


def search_outcomes(tasks: list[dict], prior: Prior, curiosity: float, persist_archive: bool, beam: int, budget: int) -> list[dict]:
    archive: set[str] = set()
    outcomes = []
    for task in tasks:
        agent = Agent(
            "search",
            "search.swarm.test",
            "curious",
            tuple(OP_NAMES),
            6600,
            7400,
            curiosity,
            beam,
            budget,
            False,
            prior,
            archive if persist_archive else set(),
        )
        proposal = agent.consider(task["demos_grid"], task["test_in_grid"])
        if not persist_archive:
            pass
        else:
            archive = agent.archive
        correct = proposal is not None and proposal.predicted == task["test_out_grid"]
        returned = list(proposal.program) if proposal and proposal.program else None
        outcomes.append(
            {
                "id": task["id"],
                "correct": int(correct),
                "program": returned,
                "generator": task["program"],
                "alias": int(correct and returned is not None and returned != task["program"]),
                "exact_generator": int(correct and returned == task["program"]),
            }
        )
    return outcomes


def play_market(tasks: list[dict], agents: list[Agent], freeze: dict) -> list[int]:
    bounty = freeze["bounty"]
    stake = freeze["stake"]
    requester = "requester.swarm.test"
    market = Market(max_stake=DEFAULT_MAX_STAKE, block=0)
    market.owner = "owner.swarm.test"
    market.bal = {requester: bounty * (len(tasks) + 2), "market": 0}
    for agent in agents:
        market.bal[agent.account] = stake * (len(tasks) + 2)
        market.register_agent(agent.account)
    solved = []
    for index, task in enumerate(tasks):
        spec = TaskSpec(
            task.get("family", "search"),
            tuple(task["program"]),
            task["demos_grid"],
            task["test_in_grid"],
            task["test_out_grid"],
        )
        task_id = market.post_task(
            requester,
            encode_demos(spec.demos),
            canonical(spec.test_input),
            answer_hash(spec.test_output),
            stake,
            8,
            bounty,
        )
        proposals = {}
        for agent in agents:
            proposal = agent.consider(spec.demos, spec.test_input)
            if proposal is None:
                continue
            price = agent.quote(market.reputation(agent.account), bounty)
            market.place_bid(agent.account, task_id, price, agent.confidence_bps, stake)
            proposals[agent.account] = proposal
        while True:
            if not market.assign_best(requester, task_id):
                break
            assignee = market.tasks[task_id].assignee
            agent = next(item for item in agents if item.account == assignee)
            proposal = proposals[assignee]
            helper = agent.helper_for(proposal.program, {item.account: item for item in agents})
            if helper is not None:
                market.subcontract(assignee, task_id, helper.account, 2000)
            output = canonical(proposal.predicted)
            salt = f"e{index}{agent.name}"
            market.commit_solution(assignee, task_id, commitment(output, salt))
            market.advance_block()
            result = market.reveal_solution(assignee, task_id, output, salt)
            if result["correct"]:
                break
        solved.append(int(market.tasks[task_id].status == "solved"))
        market.audit()
    return solved


def contrast(name: str, left: list[int], right: list[int], freeze: dict, left_name: str, right_name: str) -> dict:
    raw = paired_bootstrap(left, right, n_resamples=freeze["bootstrap_resamples"], seed=freeze["bootstrap_seed"])
    return {
        "name": name,
        "left": left_name,
        "right": right_name,
        "n": raw["n"],
        "left_solved": int(sum(left)),
        "right_solved": int(sum(right)),
        "left_rate_pp": round(100 * raw["left_rate"], 4),
        "right_rate_pp": round(100 * raw["right_rate"], 4),
        "diff_pp": round(100 * raw["diff"], 4),
        "ci_low_pp": round(100 * raw["ci_low"], 4),
        "ci_high_pp": round(100 * raw["ci_high"], 4),
        "clears": raw["clears"],
        "left_only": raw["left_only"],
        "right_only": raw["right_only"],
    }


def run(freeze: dict, search_tasks: list[dict], society_tasks: list[dict], head: str) -> dict:
    banned = seen_pairs(search_tasks)
    rows, dropped = collect_training_grids(freeze, banned)
    true_labels = [row[1] for row in rows]
    shuffled_labels = [cycle_labels(row[1]) for row in rows]
    learned = make_prior(freeze, True, true_labels, rows)
    untrained = make_prior(freeze, False, true_labels, rows)
    shuffled = make_prior(freeze, True, shuffled_labels, rows)
    depth2 = [task for task in search_tasks if task["split"] == "depth2"]
    depth1 = [task for task in search_tasks if task["split"] == "depth1"]
    learned_d2 = search_outcomes(depth2, learned, 0.0, False, freeze["beam"], freeze["budget"])
    untrained_d2 = search_outcomes(depth2, untrained, 0.0, False, freeze["beam"], freeze["budget"])
    shuffled_d2 = search_outcomes(depth2, shuffled, 0.0, False, freeze["beam"], freeze["budget"])
    learned_d1 = search_outcomes(depth1, learned, 0.0, False, freeze["beam"], freeze["budget"])
    untrained_d1 = search_outcomes(depth1, untrained, 0.0, False, freeze["beam"], freeze["budget"])
    shuffled_d1 = search_outcomes(depth1, shuffled, 0.0, False, freeze["beam"], freeze["budget"])
    curiosity_on = search_outcomes(depth2, learned, freeze["curiosity_on"], True, freeze["beam"], freeze["budget"])
    curiosity_off = search_outcomes(depth2, learned, 0.0, True, freeze["beam"], freeze["budget"])
    society_agents = default_agents(learned)
    single = [
        Agent(
            "curious",
            "curious.swarm.test",
            "curious",
            tuple(OP_NAMES),
            6600,
            7400,
            freeze["curiosity_on"],
            freeze["beam"],
            freeze["budget"],
            False,
            learned,
            set(),
        )
    ]
    society_solved = play_market(society_tasks, society_agents, freeze)
    single_solved = play_market(society_tasks, single, freeze)
    bits = lambda rows_: [row["correct"] for row in rows_]
    contrasts = [
        contrast("depth2_learned_minus_untrained", bits(learned_d2), bits(untrained_d2), freeze, "learned", "untrained"),
        contrast("depth2_learned_minus_shuffled", bits(learned_d2), bits(shuffled_d2), freeze, "learned", "shuffled"),
        contrast("depth2_curiosity_on_minus_off", bits(curiosity_on), bits(curiosity_off), freeze, "curiosity_on", "curiosity_off"),
        contrast("society_minus_single_curious", society_solved, single_solved, freeze, "society", "single_curious"),
        contrast("depth1_learned_minus_untrained", bits(learned_d1), bits(untrained_d1), freeze, "learned", "untrained"),
        contrast("depth1_learned_minus_shuffled", bits(learned_d1), bits(shuffled_d1), freeze, "learned", "shuffled"),
    ]
    def alias_rate(rows_):
        correct = [row for row in rows_ if row["correct"]]
        if not correct:
            return {"correct": 0, "exact_generator": 0, "alias": 0}
        return {
            "correct": len(correct),
            "exact_generator": sum(row["exact_generator"] for row in correct),
            "alias": sum(row["alias"] for row in correct),
        }
    families = {}
    for task, flag in zip(society_tasks, society_solved, strict=True):
        families.setdefault(task["family"], {"n": 0, "solved": 0})
        families[task["family"]]["n"] += 1
        families[task["family"]]["solved"] += flag
    return {
        "protocol": freeze["protocol"],
        "freeze_commit": head,
        "params": learned.n_params(),
        "train_rows": len(rows),
        "train_dropped_as_eval_overlap": dropped,
        "contrasts": contrasts,
        "alias": {
            "depth2_learned": alias_rate(learned_d2),
            "depth1_learned": alias_rate(learned_d1),
        },
        "society_by_family": families,
        "vectors": {
            "depth2_learned": bits(learned_d2),
            "depth2_untrained": bits(untrained_d2),
            "depth2_shuffled": bits(shuffled_d2),
            "depth2_curiosity_on": bits(curiosity_on),
            "depth2_curiosity_off": bits(curiosity_off),
            "depth1_learned": bits(learned_d1),
            "depth1_untrained": bits(untrained_d1),
            "depth1_shuffled": bits(shuffled_d1),
            "society": society_solved,
            "single_curious": single_solved,
        },
    }


def smoke() -> None:
    freeze = load_freeze()
    freeze = {**freeze, "width": 32, "epochs": 1, "train_n": 32, "beam": 4, "budget": 8}
    tiny = [
        {
            "id": "s0",
            "split": "depth1",
            "program": ["rot90"],
            "demos": [{"in": "12;30", "out": "31;42"}],
            "test_input": "11;22",
            "test_output": "21;21",
        }
    ]
    # The grids above need not be a real rotation. Smoke only checks that
    # training and a search call return without writing the official result.
    parsed = rows_from_json(tiny)
    rows, dropped = collect_training_grids(freeze, set())
    prior = make_prior(freeze, True, [row[1] for row in rows], rows)
    outcomes = search_outcomes(parsed, prior, 0.0, False, freeze["beam"], freeze["budget"])
    if prior.n_params() <= 0 or not outcomes:
        raise SystemExit("smoke failed")
    print(json.dumps({"smoke": True, "params": prior.n_params(), "dropped": dropped, "called": True}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        smoke()
        return
    if RESULT.exists():
        raise SystemExit(f"refusing to score again: {RESULT} exists")
    head = git_head()
    freeze = load_freeze()
    search_tasks = rows_from_json(json.loads((HERE / "frozen" / "search_tasks.json").read_text(encoding="utf-8")))
    society_tasks = rows_from_json(json.loads((HERE / "frozen" / "society_tasks.json").read_text(encoding="utf-8")))
    payload = run(freeze, search_tasks, society_tasks, head)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    dashboard = ROOT / "dashboard" / "ablation.js"
    dashboard.write_text("window.ABLATION = " + json.dumps(payload) + ";\n", encoding="utf-8")
    summary = [{key: item[key] for key in ("name", "left_solved", "right_solved", "n", "diff_pp", "ci_low_pp", "ci_high_pp", "clears")} for item in payload["contrasts"]]
    print(json.dumps({"freeze_commit": head, "params": payload["params"], "contrasts": summary}, indent=2))


if __name__ == "__main__":
    main()
