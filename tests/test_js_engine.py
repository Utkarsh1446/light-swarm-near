"""The browser engine must match the Python learners on a fixed draw."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "dashboard" / "weights" / "fixture.json"

NODE = r"""
const fs = require("fs");
const E = require("./dashboard/engine.js");
const fx = JSON.parse(fs.readFileSync("./dashboard/weights/fixture.json", "utf8"));
const names = ["geo", "colour", "object", "mixed", "noisy"];
const models = {};
for (const name of names) {
  const packed = JSON.parse(fs.readFileSync("./dashboard/weights/" + name + ".json", "utf8"));
  models[name] = E.decodeWeights(packed);
}
const probe = new E.PythonRandom(fx.random_probe.seed);
const randoms = [];
for (let i = 0; i < fx.random_probe.random.length; i += 1) randoms.push(probe.random());
const ranges = [];
for (let i = 0; i < fx.random_probe.randrange16.length; i += 1) ranges.push(probe.randrange(16));
const ints = [];
for (let i = 0; i < fx.random_probe.randint.length; i += 1) ints.push(probe.randint(1, 9));
const cases = fx.cases.map((task) => {
  const subjects = {};
  for (const name of names) {
    const features = Float32Array.from(task.features);
    const scores = Array.from(E.logits(models[name], features));
    const found = E.predict(models[name], task, { beam: 6, budget: 48, archive: new Set() });
    subjects[name] = {
      logits: scores,
      program: found.program,
      predicted: found.predicted,
      correct: found.correct ? 1 : 0,
    };
  }
  return subjects;
});
const generated = {};
for (const family of Object.keys(fx.generated)) {
  const rng = new E.PythonRandom(20261118 + family.length);
  generated[family] = E.packTask(E.generateTask(family, rng));
}
process.stdout.write(JSON.stringify({ randoms, ranges, ints, cases, generated }));
"""


class JsEngineTest(unittest.TestCase):
    def test_matches_python_fixture(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw = subprocess.check_output(["node", "-e", NODE], cwd=ROOT, text=True)
        got = json.loads(raw)
        probe = fixture["random_probe"]
        self.assertEqual(got["ranges"], probe["randrange16"])
        self.assertEqual(got["ints"], probe["randint"])
        for left, right in zip(got["randoms"], probe["random"]):
            self.assertAlmostEqual(left, right, places=12)
        for family, expected in fixture["generated"].items():
            produced = got["generated"][family]
            self.assertEqual(produced["program"], expected["program"])
            self.assertEqual(produced["demos"], expected["demos"])
            self.assertEqual(produced["test_input"], expected["test_input"])
            self.assertEqual(produced["test_output"], expected["test_output"])
        names = ["geo", "colour", "object", "mixed", "noisy"]
        for task, expected in zip(got["cases"], fixture["cases"]):
            for name in names:
                self.assertEqual(task[name]["program"], expected["subjects"][name]["program"])
                self.assertEqual(task[name]["predicted"], expected["subjects"][name]["predicted"])
                self.assertEqual(task[name]["correct"], expected["subjects"][name]["correct"])
                diffs = [abs(a - b) for a, b in zip(task[name]["logits"], expected["subjects"][name]["logits"])]
                self.assertLess(max(diffs), 1e-4, name)


if __name__ == "__main__":
    unittest.main()
