"""Student tests for the evaluator and repair agents."""

import unittest

from agents import LLMRepairAgent, MinConflictsAgent
from conference import Placement, move
from constraints import evaluate
from llm_client import ScriptedClient
from scenarios import evaluation_scenarios


class FailingClient:
    def chat(self, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("test failure detail")

class StudentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = evaluation_scenarios()[0]

    def test_evaluator_counts_hard_violations_and_soft_penalty(self) -> None:
        result = evaluate(self.scenario.problem, self.scenario.initial_schedule)

        self.assertEqual(result.hard_violations, 5)
        self.assertEqual(result.soft_penalty, 5)
        self.assertEqual(
            result.conflicted_talks,
            frozenset({"T1", "T2", "T3", "T4", "T5"}),
        )

    def test_invalid_move_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            move(
                self.scenario.problem,
                self.scenario.initial_schedule,
                "T1",
                Placement("Canyon", "09:00"),
            )

    def test_min_conflicts_repairs_schedule(self) -> None:
        result = MinConflictsAgent().repair(
            self.scenario.problem, self.scenario.initial_schedule, 20, 7
        )

        self.assertTrue(result.feasible)
        self.assertLessEqual(result.metrics.edits, 20)
        self.assertGreaterEqual(result.metrics.evaluator_calls, 1)

    def test_duplicate_json_keys_are_malformed(self) -> None:
        client = ScriptedClient(
            ['{"tool":"move","talk_id":"T1","talk_id":"T2",'
             '"room":"Canyon","slot":"10:30"}']
        )

        result = LLMRepairAgent(client).repair(
            self.scenario.problem, self.scenario.initial_schedule, 1, 0
        )

        self.assertEqual(result.metrics.model_calls, 1)
        self.assertEqual(result.metrics.malformed_requests, 1)
        self.assertEqual(result.metrics.edits, 0)
        self.assertEqual(result.schedule, self.scenario.initial_schedule)

    def test_zero_history_sends_no_prior_outcomes(self) -> None:
        client = ScriptedClient(["not json"])

        LLMRepairAgent(client, history_limit=0).repair(
            self.scenario.problem, self.scenario.initial_schedule, 1, 0
        )

        user_message = client.messages_seen[0][1]["content"]
        self.assertIn('"history": []', user_message)

    def test_prompt_requires_json_only_no_prose(self) -> None:
        client = ScriptedClient(['{"tool":"move","talk_id":"T1","room":"Canyon","slot":"10:30"}'])

        LLMRepairAgent(client).repair(
            self.scenario.problem, self.scenario.initial_schedule, 1, 0
        )

        system_message = client.messages_seen[0][0]["content"]
        self.assertIn("Output ONLY a valid JSON object", system_message)
        self.assertIn("No prose", system_message)
        self.assertIn("no markdown", system_message)

    def test_client_failure_preserves_state_and_consumes_budget(self) -> None:
        result = LLMRepairAgent(FailingClient()).repair(
            self.scenario.problem, self.scenario.initial_schedule, 1, 0
        )

        self.assertEqual(result.metrics.model_calls, 1)
        self.assertEqual(result.metrics.client_failures, 1)
        self.assertEqual(result.metrics.edits, 0)
        self.assertEqual(result.schedule, self.scenario.initial_schedule)
        self.assertIn("client failure: RuntimeError", result.trace[0].outcome)


if __name__ == "__main__":
    unittest.main()
