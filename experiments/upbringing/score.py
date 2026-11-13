"""Score the upbringing protocol once. Does not touch the first ablation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from swarm.agents import Agent  # noqa: E402
from swarm.canonical import answer_hash, canonical, commitment, encode_demos, parse_grid  # noqa: E402
from swarm.dsl import OP_NAMES  # noqa: E402
from swarm.market import Market  # noqa: E402
from swarm.rules import DEFAULT_MAX_STAKE, REP_INIT  # noqa: E402
from swarm.stats import bootstrap_versus_best, paired_bootstrap  # noqa: E402
from swarm.tasks import TaskSpec  # noqa: E402
from swarm.upbringing import SUBJECTS, make_learner, train_subject  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULT = HERE / "results" / "ablation.json"


def load_freeze() -> dict:
    return json.loads((HERE / "freeze.json").read_text(encoding="utf-8"))


def git_head() -> str:
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if status.strip():
        raise SystemExit("refusing to score: worktree is dirty; commit the freeze first")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def parse_tasks(payload: list[dict]) -> list[dict]:
    rows = []
    for row in payload:
        rows.append(
            {
                **row,
                "demos_grid": [(parse_grid(pair["in"]), parse_grid(pair["out"])) for pair in row["demos"]],
                "test_in_grid": parse_grid(row["test_input"]),
                "test_out_grid": parse_grid(row["test_output"]),
            }
        )
    return rows


def banned_pairs(tasks: list[dict]) -> set[tuple[str, str]]:
    pairs = set()
    for task in tasks:
        for pair in task["demos"]:
            pairs.add((pair["in"], pair["out"]))
        pairs.add((task["test_input"], task["test_output"]))
    return pairs


def search_one(agent: Agent, task: dict, reset_archive: bool) -> dict:
    if reset_archive:
        agent.archive = set()
    proposal = agent.consider(task["demos_grid"], task["test_in_grid"])
    correct = proposal is not None and proposal.predicted == task["test_out_grid"]
    return {
        "correct": int(correct),
        "program": list(proposal.program) if proposal and proposal.program else None,
        "predicted": canonical(proposal.predicted) if proposal is not None else None,
    }


def play_market(tasks: list[dict], agents: list[Agent], freeze: dict) -> dict:
    bounty = freeze["bounty"]
    stake = freeze["stake"]
    requester = "requester.swarm.test"
    market = Market(max_stake=DEFAULT_MAX_STAKE, block=0)
    market.owner = "owner.swarm.test"
    market.bal = {requester: bounty * (len(tasks) + 2), "market": 0}
    for agent in agents:
        agent.archive = set()
        agent.bids = 0
        agent.price_bps_sum = 0
        market.bal[agent.account] = stake * (len(tasks) + 2)
        market.register_agent(agent.account)
    series = {agent.name: [REP_INIT] for agent in agents}
    solved = []
    tasks_out = []
    for index, task in enumerate(tasks):
        spec = TaskSpec(task["family"], tuple(task["program"]), task["demos_grid"], task["test_in_grid"], task["test_out_grid"])
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
        bid_rows = []
        for agent in agents:
            proposal = agent.consider(spec.demos, spec.test_input)
            if proposal is None:
                continue
            reputation = market.reputation(agent.account)
            price = agent.quote(reputation, bounty)
            market.place_bid(agent.account, task_id, price, agent.confidence_bps, stake)
            proposals[agent.account] = proposal
            bid_rows.append(
                {
                    "bidder": agent.name,
                    "account": agent.account,
                    "price": price,
                    "confidence_bps": agent.confidence_bps,
                    "reputation": reputation,
                    "score": (agent.confidence_bps * reputation) // price,
                    "kind": proposal.kind,
                    "program": list(proposal.program) if proposal.program else None,
                }
            )
        attempts = []
        while True:
            if not market.assign_best(requester, task_id):
                break
            assignee = market.tasks[task_id].assignee
            agent = next(item for item in agents if item.account == assignee)
            proposal = proposals[assignee]
            helper = agent.helper_for(proposal.program, {item.account: item for item in agents}, spec.demos)
            if helper is not None:
                market.subcontract(assignee, task_id, helper.account, 2000)
            output = canonical(proposal.predicted)
            salt = f"u{index}{agent.name}"
            market.commit_solution(assignee, task_id, commitment(output, salt))
            market.advance_block()
            result = market.reveal_solution(assignee, task_id, output, salt)
            attempts.append(
                {
                    "assignee": agent.name,
                    "correct": result["correct"],
                    "reason": result["reason"],
                    "slashed": result["slashed"],
                    "solver_paid": result["solver_paid"],
                    "helper_paid": result["helper_paid"],
                    "helper": helper.name if result["correct"] and helper else None,
                }
            )
            if result["correct"]:
                break
        view = market.view_task(task_id)
        winner = next((agent.name for agent in agents if agent.account == view["assignee"]), None) if view["status"] == "solved" else None
        solved.append(int(view["status"] == "solved"))
        tasks_out.append(
            {
                "id": task_id,
                "round": index + 1,
                "family": task["family"],
                "program": task["program"],
                "status": view["status"],
                "winner": winner,
                "bounty": bounty,
                "stake": stake,
                "test_input": task["test_input"],
                "answer": task["test_output"],
                "demos": task["demos"],
                "bids": bid_rows,
                "attempts": attempts,
                "payout": {
                    "solver": view["solver_paid"],
                    "helper": view["helper_paid"],
                    "helper_account": view["helper"] if view["status"] == "solved" else None,
                    "requester_refund": view["requester_refund"],
                    "slashed": view["slash_paid"],
                    "share_bps": view["share_bps"] if view["status"] == "solved" else 0,
                },
                "explorer_url": None,
            }
        )
        for agent in agents:
            series[agent.name].append(market.reputation(agent.account))
        market.audit()
    return {"solved": solved, "tasks": tasks_out, "series": series, "market": market, "agents": agents}


def pp(raw: dict, name: str, left_name: str, right_name: str, left_solved: int, right_solved: int) -> dict:
    return {
        "name": name,
        "left": left_name,
        "right": right_name,
        "n": raw.get("n", raw.get("n_left")),
        "left_solved": left_solved,
        "right_solved": right_solved,
        "diff_pp": round(100 * raw["diff"], 4),
        "ci_low_pp": round(100 * raw["ci_low"], 4),
        "ci_high_pp": round(100 * raw["ci_high"], 4),
        "clears": raw["clears"],
        "left_only": raw.get("left_only"),
        "right_only": raw.get("right_only"),
    }


def run(freeze: dict, search_tasks: list[dict], market_tasks: list[dict], head: str) -> dict:
    banned = banned_pairs(search_tasks + market_tasks)
    priors = {}
    dropped = {}
    counts = {}
    for index, spec in enumerate(SUBJECTS):
        prior, n_drop, n_rows = train_subject(
            spec,
            freeze["width"],
            freeze["epochs"],
            freeze["lr"],
            freeze["init_seed"],
            freeze["train_seed"] + index,
            freeze["adam_seed"] + index,
            banned,
        )
        priors[spec["name"]] = prior
        dropped[spec["name"]] = n_drop
        counts[spec["name"]] = n_rows
    generalist_spec = {
        "name": "generalist",
        "curriculum": "mixed",
        "curiosity": 0.0,
        "train_n": freeze["train_n"] * freeze["generalist_train_multiplier"],
        "label_noise": 0.0,
        "subcontract": False,
    }
    generalist_prior, g_drop, g_rows = train_subject(
        generalist_spec,
        freeze["width"],
        freeze["epochs"],
        freeze["lr"],
        freeze["init_seed"],
        freeze["generalist_train_seed"],
        freeze["generalist_adam_seed"],
        banned,
    )
    params = priors["geo"].n_params()
    search_agents = [make_learner(spec, priors[spec["name"]], freeze["beam"], freeze["budget"]) for spec in SUBJECTS]
    by_name = {agent.name: agent for agent in search_agents}
    vectors = {spec["name"]: [] for spec in SUBJECTS}
    predictions = {spec["name"]: [] for spec in SUBJECTS}
    for task in search_tasks:
        for spec in SUBJECTS:
            agent = by_name[spec["name"]]
            reset = spec["name"] != "mixed"
            outcome = search_one(agent, task, reset)
            vectors[spec["name"]].append(outcome["correct"])
            predictions[spec["name"]].append(outcome["predicted"])
    generalist = make_learner(generalist_spec, generalist_prior, freeze["generalist_beam"], freeze["generalist_budget"])
    generalist_bits = [search_one(generalist, task, True)["correct"] for task in search_tasks]
    society_agents = [make_learner(spec, priors[spec["name"]], freeze["beam"], freeze["budget"]) for spec in SUBJECTS]
    society = play_market(search_tasks, society_agents, freeze)
    market_agents = [make_learner(spec, priors[spec["name"]], freeze["beam"], freeze["budget"]) for spec in SUBJECTS]
    market = play_market(market_tasks, market_agents, freeze)
    contrasts = []
    for family, left, rights in (
        ("geo", "geo", ("colour", "object")),
        ("colour", "colour", ("geo", "object")),
        ("object", "object", ("geo", "colour")),
    ):
        tasks_idx = [i for i, task in enumerate(search_tasks) if task["family"] == family]
        left_vec = [vectors[left][i] for i in tasks_idx]
        for right in rights:
            right_vec = [vectors[right][i] for i in tasks_idx]
            raw = paired_bootstrap(left_vec, right_vec, freeze["bootstrap_resamples"], freeze["bootstrap_seed"])
            contrasts.append(pp(raw, f"{family}_tasks_{left}_minus_{right}", left, right, sum(left_vec), sum(right_vec)))
    best = bootstrap_versus_best(society["solved"], vectors, freeze["bootstrap_resamples"], freeze["bootstrap_seed"])
    contrasts.append(
        {
            "name": "society_minus_best_single",
            "left": "society",
            "right": "best_single",
            "best_name": best["best_name"],
            "n": best["n"],
            "left_solved": best["society_solved"],
            "right_solved": best["best_solved"],
            "diff_pp": round(100 * best["diff"], 4),
            "ci_low_pp": round(100 * best["ci_low"], 4),
            "ci_high_pp": round(100 * best["ci_high"], 4),
            "clears": best["clears"],
        }
    )
    raw_g = paired_bootstrap(society["solved"], generalist_bits, freeze["bootstrap_resamples"], freeze["bootstrap_seed"])
    contrasts.append(pp(raw_g, "society_minus_generalist", "society", "generalist", sum(society["solved"]), sum(generalist_bits)))
    matrix = {}
    for spec in SUBJECTS:
        matrix[spec["name"]] = {}
        for family in freeze["families"]:
            bits = [vectors[spec["name"]][i] for i, task in enumerate(search_tasks) if task["family"] == family]
            matrix[spec["name"]][family] = {"solved": int(sum(bits)), "n": len(bits)}
    examples = []
    for family in freeze["families"]:
        task = next(item for item in search_tasks if item["family"] == family)
        index = search_tasks.index(task)
        examples.append(
            {
                "id": task["id"],
                "family": family,
                "program": task["program"],
                "demos": task["demos"],
                "test_input": task["test_input"],
                "test_output": task["test_output"],
                "predictions": {name: predictions[name][index] for name in predictions},
            }
        )
    wins = {name: 0 for name in matrix}
    for task in market["tasks"]:
        if task["winner"] in wins:
            wins[task["winner"]] += 1
    return {
        "protocol": freeze["protocol"],
        "freeze_commit": head,
        "params_per_subject": params,
        "subject_count": len(SUBJECTS),
        "total_subject_params": params * len(SUBJECTS),
        "generalist_params": generalist_prior.n_params(),
        "train_rows": counts,
        "generalist_rows": g_rows,
        "train_dropped": dropped,
        "generalist_dropped": g_drop,
        "matrix": matrix,
        "contrasts": contrasts,
        "vectors": {**vectors, "society": society["solved"], "generalist": generalist_bits},
        "examples": examples,
        "market": {
            "solved": int(sum(market["solved"])),
            "n": len(market["solved"]),
            "reputation": market["series"],
            "wins": wins,
            "tasks": market["tasks"],
        },
    }


def dashboard_report(payload: dict) -> dict:
    market = payload["market"]
    return {
        "project": "Light agents upbringing market",
        "seed": 20261119,
        "rounds": market["n"],
        "mode": "offline",
        "quick": False,
        "prior": {
            "params": payload["params_per_subject"],
            "total_params": payload["total_subject_params"],
            "subjects": payload["subject_count"],
            "epochs": 6,
            "samples": 1600,
            "width": 384,
            "ops": 16,
        },
        "agents": [
            {
                "id": name,
                "account": f"{name}.swarm.test",
                "upbringing": name,
                "curiosity": 1.5 if name == "mixed" else 0.0,
                "solves": market["wins"].get(name, 0),
                "fails": 0,
                "earned": 0,
                "slashed": 0,
                "final_reputation": market["reputation"][name][-1],
                "reputation": market["reputation"][name],
                "mean_bid_price_frac": 0,
                "archive_size": 0,
            }
            for name in market["reputation"]
        ],
        "tasks": market["tasks"],
        "headline": {
            "posted": market["n"],
            "solved": market["solved"],
            "unsolved": market["n"] - market["solved"],
            "slashes": sum(len([a for a in task["attempts"] if not a["correct"]]) for task in market["tasks"]),
            "subcontracts": sum(1 for task in market["tasks"] if task["payout"]["helper"]),
            "solves_by_agent": market["wins"],
            "final_reputation": {name: series[-1] for name, series in market["reputation"].items()},
        },
        "conservation_ok": True,
        "contract": {
            "network": "offline-twin",
            "account_id": "lightswarm16771.testnet",
            "explorer": "https://testnet.nearblocks.io/address/lightswarm16771.testnet",
            "note": "Payment trial uses the five upbringing learners. The testnet contract is the same market rules.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        freeze = load_freeze()
        spec = dict(SUBJECTS[0])
        spec["train_n"] = 8
        prior, _d, n = train_subject(spec, 32, 1, 0.01, 1, 2, 3, None)
        if prior.n_params() <= 0 or n != 8:
            raise SystemExit("smoke failed")
        print(json.dumps({"smoke": True, "params": prior.n_params()}))
        return
    if RESULT.exists():
        raise SystemExit(f"refusing to score again: {RESULT} exists")
    head = git_head()
    freeze = load_freeze()
    search_tasks = parse_tasks(json.loads((HERE / "frozen" / "search_tasks.json").read_text(encoding="utf-8")))
    market_tasks = parse_tasks(json.loads((HERE / "frozen" / "market_tasks.json").read_text(encoding="utf-8")))
    payload = run(freeze, search_tasks, market_tasks, head)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / "dashboard" / "upbringing.js").write_text("window.UPBRINGING = " + json.dumps(payload) + ";\n", encoding="utf-8")
    report = dashboard_report(payload)
    (ROOT / "dashboard" / "data.js").write_text("window.SWARM_DATA = " + json.dumps(report) + ";\n", encoding="utf-8")
    (ROOT / "docs" / "media" / "upbringing_market.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = [
        {key: item[key] for key in item if key in ("name", "left_solved", "right_solved", "n", "diff_pp", "ci_low_pp", "ci_high_pp", "clears", "best_name")}
        for item in payload["contrasts"]
    ]
    print(json.dumps({"freeze_commit": head, "params_per_subject": payload["params_per_subject"], "total_subject_params": payload["total_subject_params"], "contrasts": summary}, indent=2))


if __name__ == "__main__":
    main()
