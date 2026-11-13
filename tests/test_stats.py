import json
import unittest
from pathlib import Path

import numpy as np

from swarm.stats import bootstrap_versus_best, cycle_labels, paired_bootstrap

ROOT = Path(__file__).resolve().parents[1]


class StatsTest(unittest.TestCase):
    def test_cycle_is_a_derangement(self):
        target = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
        shifted = cycle_labels(target)
        self.assertEqual(float(shifted.sum()), float(target.sum()))
        self.assertTrue(np.all(np.flatnonzero(target) != np.flatnonzero(shifted)))
        self.assertEqual(int(shifted[1]), 1)
        self.assertEqual(int(shifted[3]), 1)

    def test_identical_outcomes_are_a_zero_interval(self):
        report = paired_bootstrap([1, 0, 1, 1], [1, 0, 1, 1])
        self.assertEqual(report["diff"], 0.0)
        self.assertEqual(report["ci_low"], 0.0)
        self.assertEqual(report["ci_high"], 0.0)
        self.assertFalse(report["clears"])

    def test_bootstrap_is_deterministic_and_covers_the_point(self):
        left = [1, 1, 0, 1, 0, 0, 1, 0]
        right = [0, 1, 0, 0, 0, 1, 1, 0]
        first = paired_bootstrap(left, right)
        second = paired_bootstrap(left, right)
        self.assertEqual(first, second)
        self.assertLessEqual(first["ci_low"], first["diff"])
        self.assertGreaterEqual(first["ci_high"], first["diff"])
        self.assertEqual(first["left_only"], 2)
        self.assertEqual(first["right_only"], 1)

    def test_best_single_interval_reselects(self):
        society = [1, 1, 1, 0]
        subjects = {"a": [1, 0, 0, 0], "b": [0, 1, 1, 0]}
        report = bootstrap_versus_best(society, subjects, n_resamples=200, seed=1)
        self.assertEqual(report["best_name"], "b")
        self.assertEqual(bootstrap_versus_best(society, subjects, n_resamples=200, seed=1), report)

    def test_protocol_text_matches_the_freeze_file(self):
        freeze = json.loads((ROOT / "experiments" / "freeze.json").read_text(encoding="utf-8"))
        text = (ROOT / "experiments" / "PROTOCOL.md").read_text(encoding="utf-8")
        for key in ("search_seed", "society_seed", "train_seed", "init_seed", "n_depth2", "n_depth1", "n_society", "train_n"):
            self.assertIn(str(freeze[key]), text)
        upbringing = json.loads((ROOT / "experiments" / "upbringing" / "freeze.json").read_text(encoding="utf-8"))
        page = (ROOT / "experiments" / "upbringing" / "PROTOCOL.md").read_text(encoding="utf-8")
        for key in ("search_seed", "market_seed", "init_seed", "train_n", "noisy_train_n", "n_per_family", "generalist_budget"):
            self.assertIn(str(upbringing[key]), page)


if __name__ == "__main__":
    unittest.main()
