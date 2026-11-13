"""Python twin of the NEAR market contract.

Same transitions as contract/src/lib.rs. Balances move here so the offline
simulation can show payouts without a chain. The Rust unit tests and the
sandbox test cover the wasm path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from swarm.canonical import (
    answer_hash,
    commitment,
    decode_demos,
    valid_grid,
    valid_hash,
    valid_salt,
)
from swarm.rules import (
    MAX_BIDS,
    MAX_SHARE_BPS,
    MAX_TASKS,
    MAX_WINDOW,
    MIN_WINDOW,
    REP_FAIL,
    REP_HELPER,
    REP_INIT,
    bid_score,
    helper_cut,
    solve_bonus,
)

CONTRACT = "market"


@dataclass
class Bid:
    bidder: str
    price: int
    confidence_bps: int
    stake: int
    slashed: bool = False
    refunded: bool = False


@dataclass
class Attempt:
    assignee: str
    correct: bool
    slashed: int
    reason: str


@dataclass
class Task:
    task_id: int
    requester: str
    demos: str
    test_input: str
    answer_hash: str
    bounty: int
    stake_required: int
    window: int
    status: str = "open"
    assignee: str | None = None
    deadline_block: int = 0
    commit_hash: str | None = None
    commit_block: int = 0
    helper: str | None = None
    share_bps: int = 0
    bids: list[Bid] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    solver_paid: int = 0
    helper_paid: int = 0
    requester_refund: int = 0
    slash_paid: int = 0


@dataclass
class AgentRec:
    account: str
    reputation: int = REP_INIT
    solves: int = 0
    fails: int = 0
    earned: int = 0
    slashed: int = 0


class Market:
    def __init__(self, max_stake: int, balances: dict[str, int] | None = None, block: int = 0):
        if max_stake <= 0:
            raise ValueError("max stake required")
        self.max_stake = max_stake
        self.owner = "owner"
        self.block = block
        self.tasks: dict[int, Task] = {}
        self.agents: dict[str, AgentRec] = {}
        self.task_count = 0
        self.bal: dict[str, int] = dict(balances or {})
        self.bal.setdefault(CONTRACT, 0)
        self.tasks_solved = 0
        self.total_slashed = 0
        self.total_paid = 0

    def advance_block(self, steps: int = 1) -> None:
        if steps < 1:
            raise ValueError("bad block step")
        self.block += steps

    def reputation(self, account: str) -> int:
        agent = self.agents.get(account)
        if agent is None:
            raise ValueError("agent not registered")
        return agent.reputation

    def register_agent(self, account: str) -> None:
        self._register(account)

    def _register(self, account: str) -> AgentRec:
        if not account or account == CONTRACT:
            raise ValueError("bad account")
        agent = self.agents.get(account)
        if agent is None:
            agent = AgentRec(account=account)
            self.agents[account] = agent
        return agent

    def _move(self, src: str, dst: str, amount: int) -> None:
        if amount < 0:
            raise ValueError("negative transfer")
        if amount == 0:
            return
        if self.bal.get(src, 0) < amount:
            raise ValueError("insufficient")
        self.bal[src] = self.bal.get(src, 0) - amount
        self.bal[dst] = self.bal.get(dst, 0) + amount

    def post_task(
        self,
        requester: str,
        demos: str,
        test_input: str,
        answer_hash: str,
        stake_required: int,
        window: int,
        deposit: int,
    ) -> int:
        if self.task_count >= MAX_TASKS:
            raise ValueError("task cap")
        if deposit <= 0:
            raise ValueError("bounty required")
        if stake_required <= 0 or stake_required > self.max_stake:
            raise ValueError("bad stake")
        if window < MIN_WINDOW or window > MAX_WINDOW:
            raise ValueError("bad window")
        if not valid_hash(answer_hash):
            raise ValueError("bad answer hash")
        if not valid_grid(test_input):
            raise ValueError("bad grid")
        decode_demos(demos)
        self._move(requester, CONTRACT, deposit)
        self.task_count += 1
        task = Task(
            task_id=self.task_count,
            requester=requester,
            demos=demos,
            test_input=test_input,
            answer_hash=answer_hash,
            bounty=deposit,
            stake_required=stake_required,
            window=window,
            deadline_block=self.block + window,
        )
        self.tasks[task.task_id] = task
        return task.task_id

    def place_bid(
        self,
        bidder: str,
        task_id: int,
        price: int,
        confidence_bps: int,
        deposit: int,
    ) -> None:
        task = self._open_task(task_id)
        if bidder == task.requester:
            raise ValueError("requester cannot bid")
        if confidence_bps < 1 or confidence_bps > 10_000:
            raise ValueError("bad confidence")
        if price <= 0 or price > task.bounty:
            raise ValueError("bad price")
        if deposit < task.stake_required or deposit > self.max_stake:
            raise ValueError("bad stake")
        if any(bid.bidder == bidder for bid in task.bids):
            raise ValueError("bid exists")
        if len(task.bids) >= MAX_BIDS:
            raise ValueError("bid cap")
        self._register(bidder)
        self._move(bidder, CONTRACT, deposit)
        task.bids.append(
            Bid(bidder=bidder, price=price, confidence_bps=confidence_bps, stake=deposit)
        )

    def assign_best(self, requester: str, task_id: int) -> bool:
        task = self._task(task_id)
        if requester != task.requester:
            raise ValueError("only requester assigns")
        if task.status != "open":
            raise ValueError("task not open")
        choice = self._best_bid(task)
        if choice is None:
            return False
        task.assignee = choice.bidder
        task.status = "assigned"
        task.commit_hash = None
        task.commit_block = 0
        task.helper = None
        task.share_bps = 0
        task.deadline_block = self.block + task.window
        return True

    def subcontract(self, assignee: str, task_id: int, helper: str, share_bps: int) -> None:
        task = self._assigned(task_id, assignee)
        if task.helper is not None:
            raise ValueError("subcontract exists")
        if helper == assignee or helper == task.requester:
            raise ValueError("bad helper")
        if helper not in self.agents:
            raise ValueError("helper not registered")
        if share_bps < 1 or share_bps > MAX_SHARE_BPS:
            raise ValueError("bad share")
        task.helper = helper
        task.share_bps = share_bps

    def commit_solution(self, assignee: str, task_id: int, commit_hash: str) -> None:
        task = self._assigned(task_id, assignee)
        if task.commit_hash is not None:
            raise ValueError("already committed")
        if not valid_hash(commit_hash):
            raise ValueError("bad commitment")
        task.commit_hash = commit_hash
        task.commit_block = self.block

    def reveal_solution(self, assignee: str, task_id: int, output: str, salt: str) -> dict:
        task = self._assigned(task_id, assignee)
        if task.commit_hash is None:
            raise ValueError("no commit")
        if self.block <= task.commit_block:
            raise ValueError("reveal too early")
        if not valid_salt(salt) or not valid_grid(output):
            raise ValueError("bad reveal")
        commit_ok = commitment(output, salt) == task.commit_hash
        answer_ok = answer_hash(output) == task.answer_hash
        if not commit_ok or not answer_ok:
            reason = "commit_mismatch" if not commit_ok else "wrong_answer"
            slashed = self._slash(task, assignee, reason)
            return {"correct": False, "slashed": slashed, "reason": reason, "solver_paid": 0, "helper_paid": 0, "requester_refund": 0}
        return self._pay(task, assignee)

    def cancel(self, requester: str, task_id: int) -> None:
        task = self._task(task_id)
        if requester != task.requester:
            raise ValueError("only requester cancels")
        if task.status != "open":
            raise ValueError("task not open")
        self._move(CONTRACT, requester, task.bounty)
        task.requester_refund += task.bounty
        for bid in task.bids:
            if not bid.slashed and not bid.refunded:
                self._move(CONTRACT, bid.bidder, bid.stake)
                bid.refunded = True
        task.status = "cancelled"

    def slash_timeout(self, task_id: int) -> None:
        task = self._task(task_id)
        if task.status != "assigned" or task.assignee is None:
            raise ValueError("task not assigned")
        if self.block <= task.deadline_block:
            raise ValueError("deadline not reached")
        self._slash(task, task.assignee, "timeout")

    def set_max_stake(self, caller: str, max_stake: int) -> None:
        if caller != self.owner:
            raise ValueError("only owner")
        if max_stake <= 0:
            raise ValueError("max stake required")
        self.max_stake = max_stake

    def liability(self) -> int:
        held = 0
        for task in self.tasks.values():
            if task.status in ("open", "assigned"):
                held += task.bounty
            for bid in task.bids:
                if not bid.slashed and not bid.refunded:
                    held += bid.stake
        return held

    def audit(self) -> None:
        if self.bal[CONTRACT] != self.liability():
            raise AssertionError(f"liability {self.liability()} != contract balance {self.bal[CONTRACT]}")
        if any(amount < 0 for amount in self.bal.values()):
            raise AssertionError("negative balance")

    def view_task(self, task_id: int) -> dict:
        task = self._task(task_id)
        return {
            "task_id": task.task_id,
            "requester": task.requester,
            "status": task.status,
            "assignee": task.assignee,
            "bounty": task.bounty,
            "solver_paid": task.solver_paid,
            "helper_paid": task.helper_paid,
            "requester_refund": task.requester_refund,
            "slash_paid": task.slash_paid,
            "helper": task.helper,
            "share_bps": task.share_bps,
            "attempts": [attempt.__dict__ for attempt in task.attempts],
            "bids": [
                {
                    "bidder": bid.bidder,
                    "price": bid.price,
                    "confidence_bps": bid.confidence_bps,
                    "stake": bid.stake,
                    "slashed": bid.slashed,
                }
                for bid in task.bids
            ],
        }

    def _pay(self, task: Task, assignee: str) -> dict:
        bid = self._bid_of(task, assignee)
        cut = helper_cut(bid.price, task.share_bps) if task.helper else 0
        solver_paid = bid.price - cut
        refund = task.bounty - bid.price
        self._move(CONTRACT, assignee, solver_paid)
        if task.helper and cut:
            self._move(CONTRACT, task.helper, cut)
            helper = self.agents[task.helper]
            helper.reputation += REP_HELPER
            helper.earned += cut
        if refund:
            self._move(CONTRACT, task.requester, refund)
        for item in task.bids:
            if not item.slashed and not item.refunded:
                self._move(CONTRACT, item.bidder, item.stake)
                item.refunded = True
        agent = self.agents[assignee]
        agent.reputation += solve_bonus(bid.confidence_bps)
        agent.solves += 1
        agent.earned += solver_paid
        task.solver_paid = solver_paid
        task.helper_paid = cut
        task.requester_refund += refund
        task.status = "solved"
        task.attempts.append(Attempt(assignee, True, 0, "solved"))
        self.tasks_solved += 1
        self.total_paid += solver_paid + cut
        return {
            "correct": True,
            "slashed": 0,
            "reason": "solved",
            "solver_paid": solver_paid,
            "helper_paid": cut,
            "requester_refund": refund,
            "helper": task.helper,
        }

    def _slash(self, task: Task, assignee: str, reason: str) -> int:
        bid = self._bid_of(task, assignee)
        if bid.slashed:
            raise ValueError("already slashed")
        self._move(CONTRACT, task.requester, bid.stake)
        bid.slashed = True
        agent = self.agents[assignee]
        agent.reputation = max(0, agent.reputation - REP_FAIL)
        agent.fails += 1
        agent.slashed += bid.stake
        task.slash_paid += bid.stake
        task.attempts.append(Attempt(assignee, False, bid.stake, reason))
        task.assignee = None
        task.commit_hash = None
        task.commit_block = 0
        task.helper = None
        task.share_bps = 0
        task.status = "open"
        self.total_slashed += bid.stake
        return bid.stake

    def _best_bid(self, task: Task) -> Bid | None:
        live = [bid for bid in task.bids if not bid.slashed]
        if not live:
            return None

        def key(bid: Bid) -> tuple[int, int, str]:
            score = bid_score(bid.confidence_bps, self.agents[bid.bidder].reputation, bid.price)
            return (-score, bid.price, bid.bidder)

        return sorted(live, key=key)[0]

    def _bid_of(self, task: Task, bidder: str) -> Bid:
        for bid in task.bids:
            if bid.bidder == bidder:
                return bid
        raise ValueError("bid missing")

    def _task(self, task_id: int) -> Task:
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("task not found")
        return task

    def _open_task(self, task_id: int) -> Task:
        task = self._task(task_id)
        if task.status != "open":
            raise ValueError("task not open")
        return task

    def _assigned(self, task_id: int, assignee: str) -> Task:
        task = self._task(task_id)
        if task.status != "assigned" or task.assignee != assignee:
            raise ValueError("not assignee")
        return task
