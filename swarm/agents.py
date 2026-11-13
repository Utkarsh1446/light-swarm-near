"""Upbringings: different catalogues, prices, and curiosity weights."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from swarm.colourmap import apply_map, infer_map
from swarm.dsl import FAMILY_OF, OP_INDEX, OP_NAMES, apply_program
from swarm.prior import Prior, featurize
from swarm.rules import REP_INIT
from swarm.search import first_demo_fit, programs_in


@dataclass
class Proposal:
    program: tuple[str, ...] | None
    predicted: list[list[int]]
    kind: str


@dataclass
class Agent:
    name: str
    account: str
    kind: str
    ops: tuple[str, ...]
    base_bps: int
    confidence_bps: int
    curiosity: float
    beam: int
    budget: int
    subcontract: bool
    prior: Prior | None = None
    archive: set[str] = field(default_factory=set)
    mask_residual: bool = False
    bids: int = 0
    price_bps_sum: int = 0

    def consider(self, demos, test_in) -> Proposal | None:
        if self.kind == "mapfit":
            mapping = infer_map(demos)
            if mapping is None:
                return None
            return Proposal(None, apply_map(test_in, mapping), "mapfit")
        if self.kind == "catalogue":
            program = first_demo_fit(demos, programs_in(self.ops)[: self.budget])
        elif self.kind in ("curious", "learner"):
            program = self._curious_fit(demos)
        else:
            raise ValueError(f"unknown kind {self.kind}")
        if program is None:
            return None
        if self.kind == "learner" and self.prior is not None:
            self.confidence_bps = confidence_from_prior(self.prior, demos, program, self.mask_residual)
        predicted = apply_program(test_in, program)
        if predicted is None:
            return None
        return Proposal(program, predicted, self.kind)

    def quote(self, reputation: int, bounty: int) -> int:
        base = self.base_bps
        if self.kind == "learner":
            # Same rule for every learner: a more confident bid asks a higher price.
            base = 3000 + (5000 * self.confidence_bps) // 10_000
        extra = base * 15 * max(0, reputation - REP_INIT) // 100_000
        frac_bps = min(9200, base + extra)
        price = max(1, bounty * frac_bps // 10_000)
        self.bids += 1
        self.price_bps_sum += frac_bps
        return price

    def helper_for(self, program: tuple[str, ...] | None, others: dict[str, "Agent"], demos=None) -> Agent | None:
        if not self.subcontract or not program or len(program) != 2:
            return None
        if self.kind == "learner":
            if demos is None:
                return None
            index = OP_INDEX[program[1]]
            best = None
            best_logit = None
            for agent in others.values():
                if agent.name == self.name or agent.prior is None:
                    continue
                scores = agent.prior.logits(masked_features(demos, agent.mask_residual))
                logit = float(scores[index])
                if best is None or logit > best_logit or (logit == best_logit and agent.name < best.name):
                    best = agent
                    best_logit = logit
            return best
        family = FAMILY_OF[program[1]]
        for agent in others.values():
            if agent.name == self.name or agent.kind != "catalogue":
                continue
            if agent.ops and FAMILY_OF[agent.ops[0]] == family:
                return agent
        return None

    def _curious_fit(self, demos) -> tuple[str, ...] | None:
        if self.prior is None:
            ranking = list(OP_NAMES)
        else:
            scores = self.prior.logits(masked_features(demos, self.mask_residual))
            decorated = []
            for index, name in enumerate(OP_NAMES):
                behavior = _behavior(demos, (name,))
                novelty = 0.0 if behavior in self.archive else self.curiosity
                decorated.append((float(scores[index]) + novelty, name, behavior))
            decorated.sort(key=lambda item: (-item[0], item[1]))
            for _score, _name, behavior in decorated[: self.beam]:
                self.archive.add(behavior)
            ranking = [name for _score, name, _behavior_id in decorated]
        top = ranking[: self.beam]
        programs = [(op,) for op in top]
        pair_scores = {name: float(len(top) - index) for index, name in enumerate(top)}
        pairs = [(left, right) for left in top for right in top]
        pairs.sort(key=lambda pair: (-(pair_scores[pair[0]] + pair_scores[pair[1]]), pair))
        programs.extend(pairs)
        return first_demo_fit(demos, programs[: self.budget])


def _behavior(demos, program: tuple[str, ...]) -> str:
    parts = []
    for grid_in, _grid_out in demos:
        produced = apply_program(grid_in, program)
        if produced is None:
            parts.append("none")
        else:
            parts.append(";".join("".join(str(value) for value in row) for row in produced))
    return "|".join(parts)


def default_agents(prior: Prior | None) -> list[Agent]:
    def acc(name: str) -> str:
        return f"{name}.swarm.test"

    return [
        Agent("geo", acc("geo"), "catalogue", ("rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose"), 3400, 9500, 0.0, 6, 48, False),
        Agent("colour", acc("colour"), "catalogue", ("cycle_fg", "fg_to_one", "invert_fg", "swap_top2"), 3400, 9500, 0.0, 4, 24, False),
        Agent(
            "object",
            acc("object"),
            "catalogue",
            ("crop_bbox", "keep_largest", "paint_largest", "gravity_down", "gravity_right", "tile2"),
            5000,
            9300,
            0.0,
            6,
            48,
            False,
        ),
        Agent("curious", acc("curious"), "curious", tuple(OP_NAMES), 6600, 7400, 1.5, 6, 48, True, prior, set()),
        Agent("mapfit", acc("mapfit"), "mapfit", (), 3600, 9100, 0.0, 0, 0, False),
    ]


def np_seed(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def masked_features(demos, mask_residual: bool) -> np.ndarray:
    features = featurize(demos)
    if mask_residual:
        features = features.copy()
        features[33:49] = 0
    return features


def confidence_from_prior(prior: Prior, demos, program: tuple[str, ...], mask_residual: bool) -> int:
    """Map the prior's preference for the chosen ops onto a confidence in basis points.

    The same formula is used for every learner. It is not a calibrated probability.
    """
    logits = prior.logits(masked_features(demos, mask_residual))
    chosen = [float(logits[OP_INDEX[name]]) for name in program]
    gap = sum(chosen) / len(chosen) - float(np.mean(logits))
    gap = max(-6.0, min(6.0, gap))
    preference = 1.0 / (1.0 + np.exp(-gap))
    return int(round(2000 + 7500 * preference))
