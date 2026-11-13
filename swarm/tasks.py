"""Procedural ARC-style tasks.

Every grid is generated here. No ARC-AGI file is read. Rejection sampling keeps
each family inside the upbringing that should be able to solve it:

- geo / colour / object: the first program in that family's catalogue that fits
  the demos also fits the hidden test, and the other catalogues do not fit.
- cross: a two-op program from two families; no single family fits the demos.
- trap: a global colour map fits the demos and fails the test; paint_largest
  generalises. The map bidder is the one that gets slashed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from swarm.colourmap import apply_map, infer_map
from swarm.dsl import (
    COLOUR_OPS,
    FAMILY_OF,
    GEO_OPS,
    OBJECT_OPS,
    OP_INDEX,
    OP_NAMES,
    apply_program,
    shape,
)
from swarm.prior import featurize
from swarm.search import any_demo_fit, first_that_generalises

OBJECT_NORMAL = ("crop_bbox", "keep_largest", "gravity_down", "gravity_right", "tile2")
CROSS_PROGRAMS = (
    ("rot90", "fg_to_one"),
    ("flip_h", "cycle_fg"),
    ("transpose", "invert_fg"),
    ("rot180", "swap_top2"),
    ("flip_v", "fg_to_one"),
    ("gravity_down", "cycle_fg"),
)
SCHEDULE = (
    "geo",
    "colour",
    "object",
    "cross",
    "trap",
    "geo",
    "colour",
    "object",
    "cross",
    "trap",
    "geo",
    "cross",
    "colour",
    "object",
    "trap",
    "cross",
    "geo",
    "trap",
    "colour",
    "trap",
)


@dataclass
class TaskSpec:
    family: str
    program: tuple[str, ...]
    demos: list[tuple[list[list[int]], list[list[int]]]]
    test_input: list[list[int]]
    test_output: list[list[int]]


def generate_task(family: str, rng: random.Random, attempts: int = 80) -> TaskSpec:
    for _ in range(attempts):
        if family == "trap":
            task = _try_trap(rng)
        elif family == "cross":
            task = _try_cross(rng)
        elif family == "geo":
            task = _try_family(rng, "geo", GEO_OPS, GEO_OPS)
        elif family == "colour":
            task = _try_family(rng, "colour", COLOUR_OPS, COLOUR_OPS)
        elif family == "object":
            task = _try_family(rng, "object", OBJECT_NORMAL, OBJECT_OPS)
        else:
            raise ValueError(f"unknown family {family}")
        if task is not None and _accept(task):
            return task
    raise RuntimeError(f"could not sample a {family} task in {attempts} draws")


def sample_trace(rng: random.Random) -> tuple[np.ndarray, np.ndarray] | None:
    """One training row: features of a synthetic pair, multi-hot of ops used."""
    if rng.random() < 0.5:
        program = (OP_NAMES[rng.randrange(len(OP_NAMES))],)
    else:
        program = (
            OP_NAMES[rng.randrange(len(OP_NAMES))],
            OP_NAMES[rng.randrange(len(OP_NAMES))],
        )
    grid = _grid_for(rng, program)
    output = apply_program(grid, program)
    if output is None or output == grid:
        return None
    if len(output) > 16 or len(output[0]) > 16:
        return None
    target = np.zeros(len(OP_NAMES), dtype=np.float32)
    for name in dict.fromkeys(program):
        target[OP_INDEX[name]] = 1.0
    return featurize([(grid, output)]), target


def _accept(task: TaskSpec) -> bool:
    if task.family == "trap":
        mapping = infer_map(task.demos)
        if mapping is None or apply_map(task.test_input, mapping) == task.test_output:
            return False
        if any_demo_fit(task.demos, GEO_OPS) or any_demo_fit(task.demos, COLOUR_OPS):
            return False
        return first_that_generalises(task.demos, task.test_input, task.test_output, OBJECT_OPS)
    if task.family == "cross":
        if any(any_demo_fit(task.demos, ops) for ops in (GEO_OPS, COLOUR_OPS, OBJECT_OPS)):
            return False
        return apply_program(task.test_input, task.program) == task.test_output
    own = {"geo": GEO_OPS, "colour": COLOUR_OPS, "object": OBJECT_OPS}[task.family]
    others = [ops for name, ops in (("geo", GEO_OPS), ("colour", COLOUR_OPS), ("object", OBJECT_OPS)) if name != task.family]
    if not first_that_generalises(task.demos, task.test_input, task.test_output, own):
        return False
    if any(any_demo_fit(task.demos, ops) for ops in others):
        return False
    if task.family != "colour" and infer_map(task.demos) is not None:
        return False
    if task.family == "colour":
        mapping = infer_map(task.demos)
        if mapping is None or apply_map(task.test_input, mapping) != task.test_output:
            return False
    return True


def _try_family(rng: random.Random, family: str, choices: tuple[str, ...], _search_ops: tuple[str, ...]) -> TaskSpec | None:
    program = (choices[rng.randrange(len(choices))],)
    return _from_program(rng, family, program)


def _try_cross(rng: random.Random) -> TaskSpec | None:
    program = CROSS_PROGRAMS[rng.randrange(len(CROSS_PROGRAMS))]
    if FAMILY_OF[program[0]] == FAMILY_OF[program[1]]:
        return None
    return _from_program(rng, "cross", program)


def _from_program(rng: random.Random, family: str, program: tuple[str, ...]) -> TaskSpec | None:
    inputs = []
    for _ in range(30):
        grid = _grid_for(rng, program)
        output = apply_program(grid, program)
        if output is None or output == grid:
            continue
        if len(output) > 12 or len(output[0]) > 12:
            continue
        inputs.append((grid, output))
        if len(inputs) == 3:
            break
    if len(inputs) < 3:
        return None
    return TaskSpec(family, program, inputs[:2], inputs[2][0], inputs[2][1])


def _try_trap(rng: random.Random) -> TaskSpec | None:
    demos = []
    for _ in range(2):
        grid = _trap_demo(rng)
        output = apply_program(grid, ("paint_largest",))
        if output is None or output == grid:
            return None
        demos.append((grid, output))
    test = _trap_test(rng)
    test_out = apply_program(test, ("paint_largest",))
    if test_out is None or test_out == test:
        return None
    return TaskSpec("trap", ("paint_largest",), demos, test, test_out)


def _trap_demo(rng: random.Random) -> list[list[int]]:
    grid = [[0] * 6 for _ in range(6)]
    _paint_rect(grid, rng.randrange(0, 2), rng.randrange(0, 2), 3, 3, 2)
    _paint_rect(grid, rng.randrange(4, 5), rng.randrange(4, 5), 2, 1, 3)
    return grid


def _trap_test(rng: random.Random) -> list[list[int]]:
    grid = [[0] * 6 for _ in range(6)]
    _paint_rect(grid, 0, 0, 3, 3, 2)
    _paint_rect(grid, 4, 4, 1, 2, 2)
    # rng is accepted so successive traps still differ if the caller wants,
    # while the geometry stays a large object plus a smaller same-colour one.
    if rng.random() < 0.5:
        _paint_rect(grid, 0, 0, 3, 2, 2)
        _paint_rect(grid, 4, 3, 2, 1, 2)
    return grid


def _paint_rect(grid, row: int, col: int, height: int, width: int, colour: int) -> None:
    for r in range(row, min(len(grid), row + height)):
        for c in range(col, min(len(grid[0]), col + width)):
            grid[r][c] = colour


def _grid_for(rng: random.Random, program: tuple[str, ...]) -> list[list[int]]:
    op = program[0]
    if op == "crop_bbox" or (len(program) > 1 and program[1] == "crop_bbox"):
        return _embed(rng, _random_grid(rng, 3))
    if op == "tile2":
        return _random_grid(rng, 3)
    grid = _random_grid(rng, 5)
    if op == "gravity_down":
        for col in range(len(grid[0])):
            grid[-1][col] = 0
    elif op == "gravity_right":
        for row in grid:
            row[-1] = 0
    return grid


def _embed(rng: random.Random, inner: list[list[int]]) -> list[list[int]]:
    height, width = shape(inner)
    canvas_h = height + 2
    canvas_w = width + 2
    grid = [[0] * canvas_w for _ in range(canvas_h)]
    row0 = rng.randrange(0, canvas_h - height + 1)
    col0 = rng.randrange(0, canvas_w - width + 1)
    for row in range(height):
        for col in range(width):
            grid[row0 + row][col0 + col] = inner[row][col]
    return grid


def _random_grid(rng: random.Random, max_side: int) -> list[list[int]]:
    height = rng.randint(3, max_side)
    width = rng.randint(3, max_side)
    colours = rng.randint(2, 5)
    grid = [[0] * width for _ in range(height)]
    nonzero = 0
    for row in range(height):
        for col in range(width):
            if rng.random() < 0.65:
                grid[row][col] = rng.randint(1, colours)
                nonzero += 1
    if nonzero < 4:
        grid[0][0] = 1
        grid[0][1] = 2
        grid[1][0] = 2
        grid[1][1] = 1
    return grid
