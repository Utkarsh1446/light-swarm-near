"""Draw the upbringing evaluation tasks. Does not train and does not score."""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from swarm.canonical import canonical  # noqa: E402
from swarm.dsl import COLOUR_OPS, FAMILY_OF, GEO_OPS, OBJECT_OPS, OP_NAMES, apply_program  # noqa: E402
from swarm.tasks import SCHEDULE, _grid_for, generate_task  # noqa: E402

HERE = Path(__file__).resolve().parent
FAMILY_OPS = {"geo": GEO_OPS, "colour": COLOUR_OPS, "object": OBJECT_OPS}


def load_freeze() -> dict:
    return json.loads((HERE / "freeze.json").read_text(encoding="utf-8"))


def _realize(rng: random.Random, program: tuple[str, ...]) -> dict | None:
    realized = []
    for _ in range(40):
        grid = _grid_for(rng, program)
        output = apply_program(grid, program)
        if output is None or output == grid:
            continue
        if len(output) > 12 or len(output[0]) > 12:
            continue
        realized.append((grid, output))
        if len(realized) == 3:
            break
    if len(realized) < 3:
        return None
    return {
        "program": list(program),
        "demos": [{"in": canonical(grid), "out": canonical(output)} for grid, output in realized[:2]],
        "test_input": canonical(realized[2][0]),
        "test_output": canonical(realized[2][1]),
    }


def _program(rng: random.Random, family: str) -> tuple[str, ...]:
    if family == "cross":
        while True:
            left = OP_NAMES[rng.randrange(len(OP_NAMES))]
            right = OP_NAMES[rng.randrange(len(OP_NAMES))]
            if FAMILY_OF[left] != FAMILY_OF[right]:
                return (left, right)
    ops = FAMILY_OPS[family]
    return (ops[rng.randrange(len(ops))],)


def draw_search(freeze: dict) -> list[dict]:
    rng = random.Random(freeze["search_seed"])
    rows = []
    for family in freeze["families"]:
        got = 0
        skips = 0
        while got < freeze["n_per_family"]:
            task = _realize(rng, _program(rng, family))
            if task is None:
                skips += 1
                if skips > freeze["n_per_family"] * 50:
                    raise RuntimeError(family)
                continue
            task["id"] = f"{family}-{got:02d}"
            task["family"] = family
            rows.append(task)
            got += 1
    return rows


def draw_market(freeze: dict) -> list[dict]:
    rng = random.Random(freeze["market_seed"])
    rows = []
    for index in range(freeze["n_market"]):
        family = SCHEDULE[index % len(SCHEDULE)]
        task = generate_task(family, rng)
        rows.append(
            {
                "id": f"market-{index:02d}",
                "family": task.family,
                "program": list(task.program),
                "demos": [{"in": canonical(grid), "out": canonical(output)} for grid, output in task.demos],
                "test_input": canonical(task.test_input),
                "test_output": canonical(task.test_output),
            }
        )
    return rows


def main() -> None:
    freeze = load_freeze()
    frozen = HERE / "frozen"
    frozen.mkdir(parents=True, exist_ok=True)
    search = draw_search(freeze)
    market = draw_market(freeze)
    paths = []
    for name, rows in (("search_tasks.json", search), ("market_tasks.json", market)):
        path = frozen / name
        path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in paths]
    (frozen / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"search {len(search)} market {len(market)}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
