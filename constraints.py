"""Student-completed schedule evaluator for U0-HW-04."""

from __future__ import annotations

from itertools import combinations
from dataclasses import dataclass

from conference import ConferenceProblem, Schedule


@dataclass(frozen=True)
class Evaluation:
    hard_violations: int
    soft_penalty: int
    conflicted_talks: frozenset[str]
    details: tuple[str, ...]


def evaluate(problem: ConferenceProblem, schedule: Schedule) -> Evaluation:
    """Count hard violations and the precisely defined soft penalty.

    Hard violations are counted once per violated room-collision constraint,
    speaker-overlap constraint, and supplied audience-conflict constraint.
    Soft penalty is one per missed nonempty preferred-slot set plus, for each
    track, max(0, number of rooms used by that track - 1).
    """
    placements = schedule.as_mapping()
    talks = {talk.identifier: talk for talk in problem.talks}
    hard_violations = 0
    conflicted_talks: set[str] = set()
    details: list[str] = []

    for first_id, second_id in combinations(talks, 2):
        first = placements[first_id]
        second = placements[second_id]
        if first == second:
            hard_violations += 1
            conflicted_talks.update((first_id, second_id))
            details.append(
                f"room collision: {first_id}/{second_id} at "
                f"{first.room} @ {first.slot}"
            )
        if first.slot == second.slot and talks[first_id].speaker == talks[second_id].speaker:
            hard_violations += 1
            conflicted_talks.update((first_id, second_id))
            details.append(
                f"speaker overlap: {first_id}/{second_id} at {first.slot}"
            )

    for conflict in problem.audience_conflicts:
        first_id, second_id = sorted(conflict)
        if placements[first_id].slot == placements[second_id].slot:
            hard_violations += 1
            conflicted_talks.update((first_id, second_id))
            details.append(
                f"audience conflict: {first_id}/{second_id} at "
                f"{placements[first_id].slot}"
            )

    soft_penalty = 0
    for talk in problem.talks:
        if talk.preferred_slots and placements[talk.identifier].slot not in talk.preferred_slots:
            soft_penalty += 1

    for track in {talk.track for talk in problem.talks}:
        rooms_used = {
            placements[talk.identifier].room
            for talk in problem.talks
            if talk.track == track
        }
        soft_penalty += max(0, len(rooms_used) - 1)

    return Evaluation(
        hard_violations,
        soft_penalty,
        frozenset(conflicted_talks),
        tuple(details),
    )


def is_feasible(problem: ConferenceProblem, schedule: Schedule) -> bool:
    return evaluate(problem, schedule).hard_violations == 0
