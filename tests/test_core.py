import hashlib
import random
import unittest

from swarm.canonical import answer_hash, canonical, commitment, parse_grid
from swarm.colourmap import apply_map, infer_map
from swarm.dsl import apply_program, paint_largest
from swarm.market import Market
from swarm.rules import REP_INIT, solve_bonus
from swarm.tasks import generate_task


class CanonicalTest(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(canonical([[1, 2], [3, 0]]), "12;30")
        self.assertEqual(
            answer_hash("12;30"),
            hashlib.sha256(b"12;30").hexdigest(),
        )
        self.assertEqual(
            commitment("12;30", "abc"),
            "32001f14d790be3047995d91e37743245991f57c932807fcbbb73ecff0bfd690",
        )
        self.assertEqual(parse_grid("12;30"), [[1, 2], [3, 0]])

    def test_rejects_ragged_grid(self):
        with self.assertRaises(ValueError):
            parse_grid("12;3")


class DslTest(unittest.TestCase):
    def test_rot90(self):
        grid = [[1, 2], [3, 4]]
        self.assertEqual(apply_program(grid, ("rot90",)), [[3, 1], [4, 2]])

    def test_paint_largest_spares_the_small_object(self):
        grid = [
            [2, 2, 0, 0],
            [2, 2, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 3, 0],
        ]
        painted = paint_largest(grid)
        self.assertEqual(painted[0][0], 1)
        self.assertEqual(painted[3][2], 3)


class MarketTest(unittest.TestCase):
    def setUp(self):
        self.market = Market(max_stake=10_000, balances={"req": 5_000, "geo": 5_000, "obj": 5_000, "market": 0})
        self.market.owner = "owner"
        self.market.register_agent("geo")
        self.market.register_agent("obj")

    def _post(self, answer="12;30", bounty=1000, stake=100):
        return self.market.post_task("req", "12;30|12;30", "12;30", answer_hash(answer), stake, 8, bounty)

    def test_solve_pays_and_updates_reputation(self):
        task_id = self._post()
        self.market.place_bid("geo", task_id, 400, 8000, 100)
        self.assertTrue(self.market.assign_best("req", task_id))
        output = "12;30"
        self.market.commit_solution("geo", task_id, commitment(output, "abc"))
        self.market.advance_block()
        result = self.market.reveal_solution("geo", task_id, output, "abc")
        self.assertTrue(result["correct"])
        self.assertEqual(result["solver_paid"], 400)
        self.assertEqual(result["requester_refund"], 600)
        self.assertEqual(self.market.reputation("geo"), REP_INIT + solve_bonus(8000))
        self.assertEqual(self.market.bal["geo"], 5_000 - 100 + 400 + 100)
        self.market.audit()

    def test_wrong_answer_is_slashed_then_reassigned(self):
        task_id = self._post(answer="12;30")
        self.market.place_bid("geo", task_id, 300, 9000, 100)
        self.market.place_bid("obj", task_id, 500, 8000, 100)
        self.market.assign_best("req", task_id)
        self.assertEqual(self.market.tasks[task_id].assignee, "geo")
        self.market.commit_solution("geo", task_id, commitment("11;11", "abc"))
        self.market.advance_block()
        wrong = self.market.reveal_solution("geo", task_id, "11;11", "abc")
        self.assertFalse(wrong["correct"])
        self.assertEqual(self.market.reputation("geo"), REP_INIT - 60)
        self.assertEqual(self.market.tasks[task_id].status, "open")
        self.market.assign_best("req", task_id)
        self.assertEqual(self.market.tasks[task_id].assignee, "obj")
        self.market.commit_solution("obj", task_id, commitment("12;30", "zz"))
        self.market.advance_block()
        right = self.market.reveal_solution("obj", task_id, "12;30", "zz")
        self.assertTrue(right["correct"])
        self.assertEqual(right["solver_paid"], 500)
        self.assertEqual(self.market.bal["req"], 5_000 - 1000 + 100 + 500)
        self.market.audit()

    def test_subcontract_splits_the_price(self):
        task_id = self._post()
        self.market.place_bid("geo", task_id, 400, 8000, 100)
        self.market.assign_best("req", task_id)
        self.market.subcontract("geo", task_id, "obj", 2500)
        self.market.commit_solution("geo", task_id, commitment("12;30", "abc"))
        self.market.advance_block()
        result = self.market.reveal_solution("geo", task_id, "12;30", "abc")
        self.assertEqual(result["helper_paid"], 100)
        self.assertEqual(result["solver_paid"], 300)
        self.assertEqual(self.market.reputation("obj"), REP_INIT + 20)

    def test_reveal_in_the_commit_block_is_rejected(self):
        task_id = self._post()
        self.market.place_bid("geo", task_id, 400, 8000, 100)
        self.market.assign_best("req", task_id)
        self.market.commit_solution("geo", task_id, commitment("12;30", "abc"))
        with self.assertRaises(ValueError):
            self.market.reveal_solution("geo", task_id, "12;30", "abc")

    def test_cancel_refunds_open_task(self):
        task_id = self._post()
        self.market.place_bid("geo", task_id, 400, 8000, 100)
        self.market.cancel("req", task_id)
        self.assertEqual(self.market.tasks[task_id].status, "cancelled")
        self.assertEqual(self.market.bal["req"], 5_000)
        self.assertEqual(self.market.bal["geo"], 5_000)
        self.market.audit()

    def test_timeout_slashes_the_assignee(self):
        task_id = self._post()
        self.market.place_bid("geo", task_id, 400, 8000, 100)
        self.market.assign_best("req", task_id)
        self.market.advance_block(9)
        self.market.slash_timeout(task_id)
        self.assertEqual(self.market.tasks[task_id].status, "open")
        self.assertEqual(self.market.reputation("geo"), REP_INIT - 60)


class GeneratorTest(unittest.TestCase):
    def test_each_family_has_the_intended_shape(self):
        rng = random.Random(4)
        for family in ("geo", "colour", "object", "cross", "trap"):
            task = generate_task(family, rng)
            self.assertEqual(task.family, family)
            self.assertNotEqual(task.test_input, task.test_output)
            if family == "trap":
                mapping = infer_map(task.demos)
                self.assertIsNotNone(mapping)
                self.assertNotEqual(apply_map(task.test_input, mapping), task.test_output)
            if family == "cross":
                self.assertEqual(len(task.program), 2)


if __name__ == "__main__":
    unittest.main()
