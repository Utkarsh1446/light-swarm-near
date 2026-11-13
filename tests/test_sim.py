import unittest

from swarm.sim import run_sim


class SimTest(unittest.TestCase):
    def test_quick_run_conserves_tokens_and_solves(self):
        report = run_sim(rounds=8, seed=2, quick=True)
        self.assertTrue(report["conservation_ok"])
        self.assertEqual(len(report["agents"]), 5)
        self.assertEqual([agent["id"] for agent in report["agents"]], ["geo", "colour", "object", "mixed", "noisy"])
        self.assertGreater(report["prior"]["params"], 0)
        self.assertEqual(report["prior"]["total_params"], report["prior"]["params"] * 5)
        self.assertGreaterEqual(report["headline"]["solved"], 1)
        self.assertEqual(report["headline"]["posted"], 8)
        again = run_sim(rounds=8, seed=2, quick=True)
        self.assertEqual(report["headline"]["final_reputation"], again["headline"]["final_reputation"])
        self.assertEqual(report["headline"]["winners"], again["headline"]["winners"])


if __name__ == "__main__":
    unittest.main()
