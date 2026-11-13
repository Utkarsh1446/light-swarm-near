"""Write the frozen task draws. Does not train and does not score."""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm.canonical import canonical  # noqa: E402
from swarm.dsl import FAMILY_OF, OP_NAMES, apply_program  # noqa: E402
from swarm.tasks import SCHEDULE, _grid_for, generate_task  # noqa: E402

HERE = Path(__file__).resolve().parent


def load_freeze() -> dict:
    return json.loads((HERE / "freeze.json").read_text(encoding="utf-8"))


def _program(rng: random.Random, depth: int) -> tuple[str, ...]:
    if depth == 1:
        return (OP_NAMES[rng.randrange(len(OP_NAMES))],)
    while True:
        left = OP_NAMES[rng.randrange(len(OP_NAMES))]
        right = OP_NAMES[rng.randrange(len(OP_NAMES))]
        if FAMILY_OF[left] != FAMILY_OF[right]:
            return (left, right)


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
    demos = [{"in": canonical(grid), "out": canonical(output)} for grid, output in realized[:2]]
    return {
        "program": list(program),
        "demos": demos,
        "test_input": canonical(realized[2][0]),
        "test_output": canonical(realized[2][1]),
    }


def draw_search(freeze: dict) -> list[dict]:
    rng = random.Random(freeze["search_seed"])
    rows = []
    for split, depth, count in (("depth2", 2, freeze["n_depth2"]), ("depth1", 1, freeze["n_depth1"])):
        got = 0
        skips = 0
        while got < count:
            task = _realize(rng, _program(rng, depth))
            if task is None:
                skips += 1
                if skips > count * 50:
                    raise RuntimeError(f"could not draw {split}")
                continue
            task["id"] = f"{split}-{got:02d}"
            task["split"] = split
            rows.append(task)
            got += 1
    return rows


def draw_society(freeze: dict) -> list[dict]:
    rng = random.Random(freeze["society_seed"])
    rows = []
    for index in range(freeze["n_society"]):
        family = SCHEDULE[index % len(SCHEDULE)]
        task = generate_task(family, rng)
        rows.append(
            {
                "id": f"society-{index:02d}",
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
    society = draw_society(freeze)
    search_path = frozen / "search_tasks.json"
    society_path = frozen / "society_tasks.json"
    search_path.write_text(json.dumps(search, indent=2) + "\n", encoding="utf-8")
    society_path.write_text(json.dumps(society, indent=2) + "\n", encoding="utf-8")
    lines = []
    for path in (search_path, society_path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (frozen / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"search tasks {len(search)}")
    print(f"society tasks {len(society)}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
