"""Export the five upbringing learners for in-browser inference.

Retrains with the frozen seeds and the same banned evaluation pairs. The
scored result file is not read for weights and is not rewritten. Logging the
training loss does not change the Adam updates.
"""

from __future__ import annotations

import base64
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm.agents import masked_features  # noqa: E402
from swarm.canonical import canonical  # noqa: E402
from swarm.tasks import generate_task  # noqa: E402
from swarm.upbringing import SUBJECTS, make_learner, train_subject  # noqa: E402
from experiments.upbringing.score import banned_pairs, load_freeze, parse_tasks, search_one  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = ROOT / "dashboard" / "weights"


def pack(array) -> str:
    return base64.b64encode(array.astype("<f4").tobytes()).decode("ascii")


def main() -> None:
    freeze = load_freeze()
    search = json.loads((ROOT / "experiments/upbringing/frozen/search_tasks.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / "experiments/upbringing/frozen/market_tasks.json").read_text(encoding="utf-8"))
    banned = banned_pairs(search + market)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"protocol": freeze["protocol"], "subjects": []}
    agents = []
    for index, spec in enumerate(SUBJECTS):
        prior, dropped, count = train_subject(
            spec,
            freeze["width"],
            freeze["epochs"],
            freeze["lr"],
            freeze["init_seed"],
            freeze["train_seed"] + index,
            freeze["adam_seed"] + index,
            banned,
            log_loss=True,
        )
        payload = {
            "name": spec["name"],
            "curiosity": spec["curiosity"],
            "dims": [64, freeze["width"], freeze["width"], freeze["width"], 16],
            "params": prior.n_params(),
            "epoch_loss": [round(value, 6) for value in prior.epoch_loss],
            "weights_b64": [pack(weight) for weight in prior.weights],
            "bias_b64": [pack(bias) for bias in prior.biases],
        }
        (OUT / f"{spec['name']}.json").write_text(json.dumps(payload), encoding="utf-8")
        meta["subjects"].append(
            {
                "name": spec["name"],
                "curiosity": spec["curiosity"],
                "curriculum": spec["curriculum"],
                "train_n": spec["train_n"],
                "label_noise": spec["label_noise"],
                "params": prior.n_params(),
                "dropped": dropped,
                "rows": count,
                "epoch_loss": payload["epoch_loss"],
            }
        )
        agents.append(make_learner(spec, prior, freeze["beam"], freeze["budget"]))
        print(spec["name"], prior.n_params(), "dropped", dropped, "loss", payload["epoch_loss"], flush=True)

    rng = random.Random(20261118)
    random_probe = {
        "seed": 20261118,
        "random": [rng.random() for _ in range(8)],
        "randrange16": [rng.randrange(16) for _ in range(8)],
        "randint": [rng.randint(1, 9) for _ in range(4)],
    }
    generated = {}
    for family in ("geo", "colour", "object", "cross"):
        task = generate_task(family, random.Random(20261118 + len(family)))
        generated[family] = {
            "program": list(task.program),
            "demos": [{"in": canonical(left), "out": canonical(right)} for left, right in task.demos],
            "test_input": canonical(task.test_input),
            "test_output": canonical(task.test_output),
        }

    cases = []
    for task in parse_tasks(search[:4]):
        row = {
            "family": task["family"],
            "demos": task["demos"],
            "test_input": task["test_input"],
            "test_output": task["test_output"],
            "features": masked_features(task["demos_grid"], True).tolist(),
            "subjects": {},
        }
        for agent in agents:
            agent.archive = set()
            found = search_one(agent, task, reset_archive=True)
            logits = agent.prior.logits(masked_features(task["demos_grid"], True))
            row["subjects"][agent.name] = {
                "logits": [float(value) for value in logits],
                "program": found["program"],
                "predicted": found["predicted"],
                "correct": found["correct"],
            }
        cases.append(row)

    fixture = {"random_probe": random_probe, "generated": generated, "cases": cases}
    (OUT / "fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
