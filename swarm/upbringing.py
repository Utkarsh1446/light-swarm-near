"""Five learners, one architecture, five curricula.

Every subject starts from the same Gaussian initialization. Training data is
the only difference, plus a curiosity weight at search time for the mixed
subject. Search is always over the full 16-operation catalogue. Residual
features are masked so a curriculum can matter: those features otherwise
name the depth-1 operation directly.
"""

from __future__ import annotations

import random

import numpy as np

from swarm.agents import Agent
from swarm.dsl import COLOUR_OPS, GEO_OPS, OBJECT_OPS, OP_INDEX, OP_NAMES, apply_program
from swarm.prior import Prior
from swarm.tasks import _grid_for
from swarm.upbringing_features import mask_copy

CURRICULUM_OPS = {
    "geo": GEO_OPS,
    "colour": COLOUR_OPS,
    "object": OBJECT_OPS,
    "mixed": OP_NAMES,
}

SUBJECTS = (
    {"name": "geo", "curriculum": "geo", "curiosity": 0.0, "train_n": 1600, "label_noise": 0.0, "subcontract": False},
    {"name": "colour", "curriculum": "colour", "curiosity": 0.0, "train_n": 1600, "label_noise": 0.0, "subcontract": False},
    {"name": "object", "curriculum": "object", "curiosity": 0.0, "train_n": 1600, "label_noise": 0.0, "subcontract": False},
    {"name": "mixed", "curriculum": "mixed", "curiosity": 1.5, "train_n": 1600, "label_noise": 0.0, "subcontract": True},
    {"name": "noisy", "curriculum": "mixed", "curiosity": 0.0, "train_n": 200, "label_noise": 0.25, "subcontract": False},
)


def draw_program(rng: random.Random, curriculum: str) -> tuple[str, ...]:
    ops = CURRICULUM_OPS[curriculum]
    if rng.random() < 0.5:
        return (ops[rng.randrange(len(ops))],)
    return (ops[rng.randrange(len(ops))], ops[rng.randrange(len(ops))])


def _label(program: tuple[str, ...], rng: random.Random, label_noise: float) -> np.ndarray:
    target = np.zeros(len(OP_NAMES), dtype=np.float32)
    for name in dict.fromkeys(program):
        target[OP_INDEX[name]] = 1.0
    if label_noise <= 0:
        return target
    for index in range(len(target)):
        if target[index] > 0.5 and rng.random() < label_noise:
            target[index] = 0.0
            choice = rng.randrange(len(target) - 1)
            if choice >= index:
                choice += 1
            target[choice] = 1.0
    return target


def draw_row(rng: random.Random, curriculum: str, label_noise: float):
    """One training row, or None if the program does not change the grid."""
    program = draw_program(rng, curriculum)
    grid = _grid_for(rng, program)
    output = apply_program(grid, program)
    if output is None or output == grid or len(output) > 16 or len(output[0]) > 16:
        return None
    features = mask_copy([(grid, output)])
    return features, _label(program, rng, label_noise)


def collect_rows(rng: random.Random, curriculum: str, label_noise: float, count: int, banned: set | None = None):
    from swarm.canonical import canonical

    rows = []
    dropped = 0
    guard = 0
    while len(rows) < count and guard < count * 40:
        guard += 1
        program = draw_program(rng, curriculum)
        grid = _grid_for(rng, program)
        output = apply_program(grid, program)
        if output is None or output == grid or len(output) > 16 or len(output[0]) > 16:
            continue
        if banned is not None:
            pair = (canonical(grid), canonical(output))
            if pair in banned:
                dropped += 1
                continue
        rows.append((mask_copy([(grid, output)]), _label(program, rng, label_noise)))
    if len(rows) < count:
        raise RuntimeError(f"only gathered {len(rows)} {curriculum} rows")
    return rows, dropped


def fresh_prior(width: int, init_seed: int) -> Prior:
    return Prior(width, np.random.default_rng(init_seed))


def train_subject(spec: dict, width: int, epochs: int, lr: float, init_seed: int, train_seed: int, adam_seed: int, banned=None, log_loss: bool = False):
    rng = random.Random(train_seed)
    rows, dropped = collect_rows(rng, spec["curriculum"], spec["label_noise"], spec["train_n"], banned)
    prior = fresh_prior(width, init_seed)
    prior.train(rows, epochs=epochs, lr=lr, seed=adam_seed, log_loss=log_loss)
    return prior, dropped, len(rows)


def make_learner(spec: dict, prior: Prior, beam: int, budget: int) -> Agent:
    return Agent(
        spec["name"],
        f"{spec['name']}.swarm.test",
        "learner",
        tuple(OP_NAMES),
        3000,
        5000,
        spec["curiosity"],
        beam,
        budget,
        spec["subcontract"],
        prior,
        set(),
        True,
    )


def train_learners(width: int, epochs: int, lr: float, init_seed: int, train_seed: int, adam_seed: int, beam: int, budget: int, subjects=SUBJECTS, banned=None, train_n_override: int | None = None):
    agents = []
    dropped = {}
    for index, spec in enumerate(subjects):
        spec = dict(spec)
        if train_n_override is not None:
            # Keep the noisy subject's small-data ratio: 200/1600 of the full count.
            if spec["name"] == "noisy":
                spec["train_n"] = max(8, train_n_override // 8)
            else:
                spec["train_n"] = train_n_override
        prior, n_drop, _n = train_subject(
            spec,
            width,
            epochs,
            lr,
            init_seed,
            train_seed + index,
            adam_seed + index,
            banned,
        )
        agents.append(make_learner(spec, prior, beam, budget))
        dropped[spec["name"]] = n_drop
    return agents, dropped
