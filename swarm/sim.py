"""Offline swarm loop: post, bid, assign, commit, reveal, repeat.

The ledger is the Python twin of the NEAR contract. Pass --testnet only when
NEAR_CONTRACT_ID is set; otherwise the command refuses instead of pretending
a chain ran.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from swarm.canonical import answer_hash, canonical, commitment, encode_demos
from swarm.market import CONTRACT, Market
from swarm.rules import DEFAULT_BOUNTY, DEFAULT_MAX_STAKE, DEFAULT_STAKE, REP_INIT
from swarm.tasks import SCHEDULE, generate_task
from swarm.upbringing import train_learners

ROOT = Path(__file__).resolve().parents[1]


def run_sim(
    rounds: int = 20,
    seed: int = 1,
    quick: bool = False,
    bounty: int = DEFAULT_BOUNTY,
    stake: int = DEFAULT_STAKE,
) -> dict:
    rng = random.Random(seed)
    width = 32 if quick else 384
    epochs = 2 if quick else 6
    samples = 80 if quick else 1600
    beam = 4 if quick else 6
    budget = 16 if quick else 48
    agents, _dropped = train_learners(
        width=width,
        epochs=epochs,
        lr=0.01,
        init_seed=seed + 17,
        train_seed=seed + 101,
        adam_seed=seed + 303,
        beam=beam,
        budget=budget,
        train_n_override=samples,
    )
    report_params = agents[0].prior.n_params() if agents[0].prior is not None else 0
    by_account = {agent.account: agent for agent in agents}
    market = Market(max_stake=DEFAULT_MAX_STAKE, block=0)
    market.owner = "owner.swarm.test"
    requester = "requester.swarm.test"
    initial = {requester: bounty * (rounds + 2), CONTRACT: 0}
    for agent in agents:
        initial[agent.account] = stake * (rounds + 2)
    market.bal = dict(initial)
    initial_sum = sum(initial.values())
    for agent in agents:
        market.register_agent(agent.account)

    series = {agent.name: [REP_INIT] for agent in agents}
    tasks_out = []
    for index in range(rounds):
        family = SCHEDULE[index % len(SCHEDULE)]
        spec = generate_task(family, rng)
        task_id = market.post_task(
            requester,
            encode_demos(spec.demos),
            canonical(spec.test_input),
            answer_hash(spec.test_output),
            stake,
            window=8,
            deposit=bounty,
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
        subcontract = None
        while True:
            if not market.assign_best(requester, task_id):
                break
            task = market.tasks[task_id]
            assignee = task.assignee
            agent = by_account[assignee]
            proposal = proposals[assignee]
            helper = agent.helper_for(proposal.program, by_account, spec.demos)
            if helper is not None:
                market.subcontract(assignee, task_id, helper.account, 2000)
                subcontract = {"helper": helper.name, "share_bps": 2000, "solver": agent.name}
            output = canonical(proposal.predicted)
            salt = f"r{index}{agent.name}"
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
            subcontract = None
        view = market.view_task(task_id)
        tasks_out.append(
            {
                "id": task_id,
                "round": index + 1,
                "family": spec.family,
                "program": list(spec.program),
                "status": view["status"],
                "winner": _name_of(view["assignee"], agents) if view["status"] == "solved" else None,
                "bounty": bounty,
                "stake": stake,
                "test_input": canonical(spec.test_input),
                "answer": canonical(spec.test_output),
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

    if sum(market.bal.values()) != initial_sum:
        raise RuntimeError("token conservation failed")

    headline = _headline(tasks_out, agents, market)
    return {
        "project": "Light Agents Swarm Market",
        "seed": seed,
        "rounds": rounds,
        "mode": "offline",
        "quick": quick,
        "prior": {
            "params": report_params,
            "epochs": epochs,
            "samples": samples,
            "width": width,
            "subjects": len(agents),
            "total_params": report_params * len(agents),
            "train_seconds": None,
            "top1_accuracy": None,
            "top6_recall": None,
            "depth2_top6_recall": None,
            "chance_top1": None,
            "ops": 16,
        },
        "agents": [
            {
                "id": agent.name,
                "account": agent.account,
                "upbringing": _upbringing(agent),
                "curiosity": agent.curiosity,
                "solves": market.agents[agent.account].solves,
                "fails": market.agents[agent.account].fails,
                "earned": market.agents[agent.account].earned,
                "slashed": market.agents[agent.account].slashed,
                "final_reputation": market.agents[agent.account].reputation,
                "reputation": series[agent.name],
                "mean_bid_price_frac": (agent.price_bps_sum / agent.bids / 10_000) if agent.bids else 0,
                "archive_size": len(agent.archive),
            }
            for agent in agents
        ],
        "tasks": tasks_out,
        "headline": headline,
        "conservation_ok": True,
        "contract": {
            "network": "offline-twin",
            "account_id": None,
            "explorer": None,
            "note": "Python twin of contract/src/lib.rs. See README for the wasm sandbox test and testnet deploy.",
        },
    }


def write_outputs(report: dict, out_path: Path, dashboard_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report)
    dashboard_path.write_text(f"window.SWARM_DATA = {payload};\n", encoding="utf-8")


def _train(np_rng, rng: random.Random, width: int, epochs: int, samples: int, eval_n: int, seed: int):
    started = time.perf_counter()
    prior = Prior(width, np_rng)
    rows = []
    guard = 0
    while len(rows) < samples and guard < samples * 30:
        guard += 1
        row = sample_trace(rng)
        if row is not None:
            rows.append(row)
    holdout_rng = random.Random(seed + 10007)
    holdout = []
    guard = 0
    while len(holdout) < eval_n and guard < eval_n * 30:
        guard += 1
        row = sample_trace(holdout_rng)
        if row is not None:
            holdout.append(row)
    prior.train(rows, epochs=epochs, lr=0.01, seed=seed + 3)
    top1, top6, depth2 = evaluate(prior, holdout)
    seconds = time.perf_counter() - started
    report = TrainReport(
        params=prior.n_params(),
        epochs=epochs,
        samples=len(rows),
        width=width,
        seconds=seconds,
        top1_accuracy=top1,
        top6_recall=top6,
        depth2_top6_recall=depth2,
        chance_top1=1 / 16,
    )
    return prior, report


def _headline(tasks: list[dict], agents, market: Market) -> dict:
    solved = [task for task in tasks if task["status"] == "solved"]
    by_family: dict[str, list[str | None]] = {}
    slashes = 0
    subcontracts = 0
    first_correct = 0
    for task in tasks:
        by_family.setdefault(task["family"], []).append(task["winner"])
        slashes += len([item for item in task["attempts"] if not item["correct"]])
        if task["payout"]["helper"]:
            subcontracts += 1
        if task["attempts"] and task["attempts"][0]["correct"]:
            first_correct += 1
    return {
        "posted": len(tasks),
        "solved": len(solved),
        "unsolved": len(tasks) - len(solved),
        "slashes": slashes,
        "subcontracts": subcontracts,
        "first_assignment_correct": first_correct,
        "winners": {task["id"]: task["winner"] for task in tasks},
        "winners_by_family": by_family,
        "solves_by_agent": {agent.name: market.agents[agent.account].solves for agent in agents},
        "fails_by_agent": {agent.name: market.agents[agent.account].fails for agent in agents},
        "final_reputation": {agent.name: market.agents[agent.account].reputation for agent in agents},
        "earned": {agent.name: market.agents[agent.account].earned for agent in agents},
    }


def _upbringing(agent) -> str:
    if agent.kind == "learner":
        return (
            f"Same  {agent.prior.n_params() if agent.prior else 0}-parameter prior as the other learners, "
            f"own curriculum, curiosity {agent.curiosity}, beam {agent.beam}, full catalogue."
        )
    if agent.kind == "mapfit":
        return "Global colour-map heuristic. No program search. Abstains unless one aligned map explains every demo."
    if agent.kind == "curious":
        return "All 16 ops, beam 6, budget 48, novelty bonus 1.5 on unseen behaviors, MLP prior, subcontracts the second op's specialist at 20%."
    return f"Exhaustive catalogue over {', '.join(agent.ops)}. No curiosity bonus."


def _name_of(account: str | None, agents) -> str | None:
    if account is None:
        return None
    for agent in agents:
        if agent.account == account:
            return agent.name
    return account


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Light Agents swarm market")
    parser.add_argument("--offline", action="store_true", help="Run the contract twin locally (default)")
    parser.add_argument("--testnet", action="store_true", help="Require a deployed testnet contract")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--quick", action="store_true", help="Tiny prior, for tests")
    parser.add_argument("--out", default="out/run.json")
    parser.add_argument("--dashboard", default="dashboard/data.js")
    args = parser.parse_args(argv)
    if args.testnet:
        raise SystemExit(
            "Testnet mode is a separate step. Do: bash scripts/deploy_testnet.sh - see README "
            "'Deploy to testnet'. This command does not spend tokens. Re-run with --offline."
        )
    report = run_sim(rounds=args.rounds, seed=args.seed, quick=args.quick)
    write_outputs(report, Path(args.out), Path(args.dashboard))
    headline = report["headline"]
    print(
        json.dumps(
            {
                "out": args.out,
                "dashboard": args.dashboard,
                "solved": headline["solved"],
                "unsolved": headline["unsolved"],
                "slashes": headline["slashes"],
                "subcontracts": headline["subcontracts"],
                "final_reputation": headline["final_reputation"],
                "solves_by_agent": headline["solves_by_agent"],
                "fails_by_agent": headline["fails_by_agent"],
                "prior_params": report["prior"]["params"],
                "total_params": report["prior"]["total_params"],
                "subjects": [agent["id"] for agent in report["agents"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
