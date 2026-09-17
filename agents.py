"""Repair-agent interfaces and student implementation points."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from conference import ConferenceProblem, Placement, Schedule, move
from constraints import evaluate
from llm_client import ChatClient
import time


@dataclass(frozen=True)
class RepairMetrics:
    edits: int = 0
    evaluator_calls: int = 0
    model_calls: int = 0
    malformed_requests: int = 0
    invalid_requests: int = 0
    repeated_requests: int = 0
    client_failures: int = 0
    runtime_seconds: float = 0.0


@dataclass(frozen=True)
class TraceStep:
    step: int
    request: str
    outcome: str
    hard_violations: int
    soft_penalty: int


@dataclass(frozen=True)
class RepairResult:
    schedule: Schedule
    feasible: bool
    metrics: RepairMetrics
    trace: tuple[TraceStep, ...]


class RandomMoveAgent:
    """Provided seeded baseline using the same one-talk move and budget."""

    def repair(
        self, problem: ConferenceProblem, initial: Schedule, budget: int, seed: int
    ) -> RepairResult:
        import time

        started = time.perf_counter()
        rng = random.Random(seed)
        schedule = initial
        calls = 1
        trace: list[TraceStep] = []
        current = evaluate(problem, schedule)
        for step in range(1, budget + 1):
            if current.hard_violations == 0:
                break
            talk_id = rng.choice(tuple(t.identifier for t in problem.talks))
            options = [p for p in problem.domain(talk_id) if p != schedule.placement(talk_id)]
            if not options:
                continue
            placement = rng.choice(options)
            schedule = move(problem, schedule, talk_id, placement)
            current = evaluate(problem, schedule)
            calls += 1
            trace.append(TraceStep(step, f"{talk_id}->{placement}", "applied", current.hard_violations, current.soft_penalty))
        return RepairResult(
            schedule,
            current.hard_violations == 0,
            RepairMetrics(
                edits=len(trace),
                evaluator_calls=calls,
                runtime_seconds=time.perf_counter() - started,
            ),
            tuple(trace),
        )


class MinConflictsAgent:
    def repair(
        self, problem: ConferenceProblem, initial: Schedule, budget: int, seed: int
    ) -> RepairResult:
        """Repair with conflicted-variable selection and lexicographic scoring."""

        started = time.perf_counter()
        rng = random.Random(seed)
        schedule = initial
        edits = 0
        evaluator_calls = 0
        trace: list[TraceStep] = []

        current = evaluate(problem, schedule)
        evaluator_calls += 1

        for step in range(1, budget + 1):
            if current.hard_violations == 0:
                break

            conflicted_talks = sorted(current.conflicted_talks)
            if not conflicted_talks:
                break
            talk_id = rng.choice(conflicted_talks)
            current_placement = schedule.placement(talk_id)
            candidates: list[tuple[tuple[int, int], Placement, Schedule, object]] = []

            for placement in problem.domain(talk_id):
                if placement == current_placement:
                    continue
                candidate_schedule = move(problem, schedule, talk_id, placement)
                candidate_evaluation = evaluate(problem, candidate_schedule)
                evaluator_calls += 1
                score = (
                    candidate_evaluation.hard_violations,
                    candidate_evaluation.soft_penalty,
                )
                candidates.append(
                    (score, placement, candidate_schedule, candidate_evaluation)
                )

            if not candidates:
                continue

            best_score = min(candidate[0] for candidate in candidates)
            best_candidates = [
                candidate for candidate in candidates if candidate[0] == best_score
            ]
            _, placement, schedule, current = rng.choice(best_candidates)
            edits += 1
            trace.append(
                TraceStep(
                    step,
                    f"{talk_id}->{placement}",
                    "applied",
                    current.hard_violations,
                    current.soft_penalty,
                )
            )

        return RepairResult(
            schedule,
            current.hard_violations == 0,
            RepairMetrics(
                edits=edits,
                evaluator_calls=evaluator_calls,
                runtime_seconds=time.perf_counter() - started,
            ),
            tuple(trace),
        )


class LLMRepairAgent:
    def __init__(self, client: ChatClient, history_limit: int = 6) -> None:
        if history_limit < 0:
            raise ValueError("history_limit must be nonnegative")
        self.client = client
        self.history_limit = history_limit

    def repair(
        self, problem: ConferenceProblem, initial: Schedule, budget: int, seed: int
    ) -> RepairResult:
        """Request exactly one JSON move per model call and validate it in code."""
        started = time.perf_counter()
        schedule = initial
        edits = 0
        evaluator_calls = 0
        model_calls = 0
        malformed_requests = 0
        invalid_requests = 0
        repeated_requests = 0
        client_failures = 0
        trace: list[TraceStep] = []
        history: list[str] = []

        current = evaluate(problem, schedule)
        evaluator_calls += 1

        def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON object key")
                result[key] = value
            return result

        def schedule_text() -> dict[str, dict[str, str]]:
            return {
                talk_id: {"room": placement.room, "slot": placement.slot}
                for talk_id, placement in schedule.assignments
            }

        def prompt_messages() -> list[dict[str, str]]:
            talks = {
                talk.identifier: {
                    "speaker": talk.speaker,
                    "track": talk.track,
                    "domain": [
                        {"room": placement.room, "slot": placement.slot}
                        for placement in problem.domain(talk.identifier)
                    ],
                }
                for talk in problem.talks
            }
            user_payload = {
                "schedule": schedule_text(),
                "talks": talks,
                "evaluation": {
                    "hard_violations": current.hard_violations,
                    "soft_penalty": current.soft_penalty,
                    "conflicted_talks": sorted(current.conflicted_talks),
                    "details": list(current.details),
                },
                "history": history[-self.history_limit :]
                if self.history_limit
                else [],
            }
            return [
                {
                    "role": "system",
                    "content": (
                        "Output ONLY a valid JSON object. No prose, no markdown, no code "
                        "fences (no ``` anywhere), no backticks, no explanation, no labels like "
                        "\"Answer:\", and no whitespace or characters before the opening "
                        "{ or after the closing }. If you output anything other than the "
                        "JSON object itself, the response is rejected. "
                        "Format: a single JSON object matching exactly this schema, e.g. "
                        '{"tool":"move","talk_id":"T1","room":"Canyon","slot":"10:30"}. '
                        "It is never an array, a string, or wrapped in another object. "
                        "Keys are exactly tool, talk_id, room, slot, and no others. "
                        "tool is always the literal string \"move\". talk_id, room, and "
                        "slot are each strings. "
                        "Content: choose one legal move consistent with the current "
                        "schedule and the talk's allowed domain given in the user message. "
                        "Remember: respond with the JSON object and absolutely nothing "
                        "else — first character {, last character }."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        json.dumps(user_payload, sort_keys=True)
                        + "\n\nRespond with only the JSON move object. No other text."
                    ),
                },
            ]

        def add_trace(step: int, request: str, outcome: str) -> None:
            trace.append(
                TraceStep(
                    step,
                    request,
                    outcome,
                    current.hard_violations,
                    current.soft_penalty,
                )
            )

        for step in range(1, budget + 1):
            if current.hard_violations == 0:
                break

            model_calls += 1
            try:
                response = self.client.chat(prompt_messages())
            except Exception as error:
                client_failures += 1
                outcome = f"client failure: {type(error).__name__}"
                history.append(outcome)
                add_trace(step, "", outcome)
                continue

            try:
                request = json.loads(
                    response, object_pairs_hook=reject_duplicate_keys
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                malformed_requests += 1
                outcome = "malformed"
                history.append(outcome)
                add_trace(step, response, outcome)
                continue

            if not isinstance(request, dict):
                invalid_requests += 1
                outcome = "invalid"
                history.append(outcome)
                add_trace(step, response, outcome)
                continue

            required_keys = {"tool", "talk_id", "room", "slot"}
            if (
                set(request) != required_keys
                or any(not isinstance(request[key], str) for key in required_keys)
                or request["tool"] != "move"
            ):
                invalid_requests += 1
                outcome = "invalid"
                history.append(outcome)
                add_trace(step, response, outcome)
                continue

            talk_id = request["talk_id"]
            placement = Placement(request["room"], request["slot"])
            try:
                current_placement = schedule.placement(talk_id)
                legal = placement in problem.domain(talk_id)
            except KeyError:
                legal = False
                current_placement = None

            if not legal:
                invalid_requests += 1
                outcome = "invalid"
                history.append(outcome)
                add_trace(step, response, outcome)
                continue

            if placement == current_placement:
                repeated_requests += 1
                outcome = "repeated"
                history.append(outcome)
                add_trace(step, response, outcome)
                continue

            schedule = move(problem, schedule, talk_id, placement)
            edits += 1
            current = evaluate(problem, schedule)
            evaluator_calls += 1
            outcome = "applied"
            history.append(outcome)
            add_trace(step, response, outcome)

        return RepairResult(
            schedule,
            current.hard_violations == 0,
            RepairMetrics(
                edits=edits,
                evaluator_calls=evaluator_calls,
                model_calls=model_calls,
                malformed_requests=malformed_requests,
                invalid_requests=invalid_requests,
                repeated_requests=repeated_requests,
                client_failures=client_failures,
                runtime_seconds=time.perf_counter() - started,
            ),
            tuple(trace),
        )
