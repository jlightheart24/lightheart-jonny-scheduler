# Repairing a Conference Schedule

**Student:**  Jonny Lightheart<br>
**Private repository:** [URL]<br>
**Access:** [Confirm `fractal13` has read access]<br>
**Submitted commit:** [Hash]

## 1. PEAS Task-Environment Assessment

### Agent and Task Boundary

The conference schedule repair agents task will be to identify errors in a conference schedule and make apporpriate action to repair the schedule. Its task begins with taking a made schedule and its paramaters and observing it and ends with a viable schedule. 

This task will be benchmarked by the agents ability to return a completed schedule without introducting errors. 

### Performance Measure

The hard feasability of this agent is avoiding all hard violations. These include room colistion, speaker overlaps and audience conflicts

The soft quality will be tracked through the soft penalties that are given to the result eg. missing a preferred slot or track split across rooms. 

The move budget will be used to track the resource efficiently with a 20 move per run limit. 


### Environment

These are the tracked parts of this enviroment:

Talks: each talk has a speaker track, expected audience, required equipment, available slots, and preferred slots.

Rooms: These are the rooms that the talks can take place in. Each of the room has a capacity and some equipment. 

Slots: These are the time slots for the differents talks. Each talk has a preferred time slot. 

People: These are the speakers for each talk and multiple can be required for each talk. 

Tracks: these are the tracks of the talks and talks of the same track have a preference to staying in the same room. 

These are the hard constraints based on the environment:

Schedule Conflict: No two talks may use the same room and time slot.

Speaker Conflict: No two talks may use the same speaker and time slot. 

Audience Conflict: No two talks may share the same audience and time slot.

Capacity and equipment requirements: No talk may be scheduled in a room that violateds its capacity and equipment needs.

These are the soft preferences:

Preferred time slots: Talks have a time slot requested and this should be followed when possible.

Track locations: Talks of the same track should be in the same room when possible. 

State:
This is the current completed schedule. Each talk is mapped to one legal room-slot placement.

Evaulator:
The evaultor returns hard violations and soft penalties. It also mentions conflicted talks and gives detailed explanations of decisions. 
The agents goal is to return a state with zero hard violations and a good soft quality score within the action budget. 

Benchmark:
The benchmark for this agent will be the ability to handle this fixed scenario with six known talks. Fixed rooms and slots. This is a deterministic environment

In reality a conference like this would have non-detministic values. Things like audience a speaker tardiness, and technology issues, money budget etc. would be further variables that would need to be handled by the agent. 

### Actuators

The actuator the agent can take is moving one talk to another room and/or time slot. This action cannot violate the hard constrains of the talk.

The agent cannot change any other factor such as required speaker, equipment location or the track of a talk. 

The LLM request will get a JSON response from the LLM with the following categories:
tool: the move action
talk_id: the talk that wil be acted upon.
room: the room that the talk will be moved to.
slot: the time slot the talk will be moved to.

This move will then be validated as a viable move before the move is made. 

### Sensors

[Explain the state, domain, conflict, penalty, and history information available
to each policy. Compare programmatic access with the serialized LLM prompt and
identify one information limitation.]

State:
The state is the current complete schedule. The room and time slot for each talk.

Domain:
The othe information about each room and talk. The domain inclueds room capacity, required equipment and available time slots. 

Conflict Information:
This identifies any hard conflicts. This covers talks in the same room, talk in the same time slot, talks with the same speaker, and talks in a room that is too small. 

Penalty Information:
This identifies the penalties for some situations. This covers talks not in their preffered slots and tracks spread across multiple rooms. 

History Information:
This tracks the history of previous requests by the LLM.

Programatic Access:
Conflicts can directly inspect the scheulde, generate conflicts and apply move where the LLM receives the information and suggests a move. 

### Environment Classification

| Dimension | Classification | Benchmark-specific justification |
|---|---|---|
| Observability | Fully observable | The complete schedule, legal domains, problem data, conflicts, and evaluator results are available to the programmatic policy; the LLM receives a serialized subset of this information. |
| Outcomes | Deterministic | Given the same problem, schedule, and move, validation and evaluation produce the same result. Seeded tie breaking can change which move a policy chooses, but not the result of a particular move. |
| Temporal structure | Sequential and finite-horizon | Each move changes the current schedule and affects later decisions, with at most 20 moves or model calls per run. |
| Dynamics | Static between actions | The rooms, talks, constraints, and domains do not change during a run; only the schedule changes when an action is applied. |
| State and actions | Discrete | The state is a finite mapping of talks to room-slot placements, and an action moves one talk to one domain-valid placement. |
| Multiplicity | Single-agent | One repair policy acts on the schedule at a time; the comparison runs Min-Conflicts and the LLM policy separately from the same paired start. |

### Agent-Environment Cycle and Implementation Mapping

One cycle begins with the policy observing the current schedule and evaluation
results. It selects one talk and a legal placement, submits or applies the move,
and the program evaluates the resulting schedule. The updated schedule and
metrics become the input to the next cycle. The cycle stops when the schedule is
feasible or the 20-move/call budget is exhausted.

| PEAS element | Code or data interface | Evidence or metric |
|---|---|---|
| Performance measure | `constraints.evaluate`, `RepairResult.feasible`, and `RepairMetrics` | Final hard violations, feasibility rate, soft penalty among successful runs, edits, evaluator/model calls, request failures, and runtime |
| Environment | `ConferenceProblem`, `Talk`, `Room`, `Placement`, `Schedule`, and `evaluation_scenarios()` | Six talks, three rooms, three slots, fixed domains and constraints, four deterministic starting scenarios |
| Actuators | `conference.move()` and the LLM JSON move request | Applied edits, valid/invalid/repeated requests, and whether the final schedule is feasible |
| Sensors | `Schedule`, `ConferenceProblem.domain()`, `constraints.evaluate()`, and bounded LLM history | Current assignments, legal placements, conflicted talks, hard violations, soft penalty, details, prior outcomes, and trace steps |

## 2. CSP Model and Evaluator

### Variables, Domains, and Unary Filtering

The CSP has one variable for each talk, `T1` through `T6`. The value assigned
to a variable is a room and time-slot pair, such as `(Auditorium, 09:00)`.

The domain of each talk contains every room-slot pair that passes the talk's
individual requirements. `ConferenceProblem.domain(talk_id)` constructs this
domain by keeping only placements where the room has enough capacity, contains
all required equipment, and the talk is available during that slot. For
example, `T1` expects 140 attendees and requires recording equipment, so only
the Auditorium can appear in its domain.

These are unary constraints because each check concerns one talk and one
possible placement. They filter illegal values before the schedule is checked
for relationships between talks, such as room collisions, speaker overlaps,
and audience conflicts.

### Structural Validity, Feasibility, and Goal

A structurally valid state is a complete schedule containing every expected
talk exactly once, with each talk assigned to a placement in its domain. The
schedule therefore has the correct shape and every individual placement
satisfies capacity, equipment, and availability requirements. The
`is_structurally_valid` check and `move` operation enforce this property.

Structural validity does not guarantee feasibility. A structurally valid
schedule can still have two talks in the same room and slot, overlapping talks
by the same speaker, or an overlapping supplied audience-conflict pair. The
evaluator determines feasibility by checking these relational hard constraints;
the schedule is feasible when its `hard_violations` count is zero.

The goal is to return a final feasible schedule, preferably with the lowest
soft penalty among feasible results, within the move or model-call budget. The
edit path is only the sequence of actions used to search for that state. It is
reported through metrics such as edits and request outcomes, but it is not the
solution itself: an intermediate conflict does not matter if the final
schedule is feasible, and an efficient path does not make an infeasible final
schedule acceptable.

### Hard Constraints and Soft Penalty

Hard Violations: 
Room Collisions - two talks assigned to the same room and slot.
Speaker Overlap - two talks with the same speaker and slot.
Audience Conflict - supplied audience scheduled in the same slot. 

The schedule is only feasible if there are no hard violations.

Soft penalties:
Missed preferred slot: if a talk misses a non-empty prefferd slot increase the penalty by one.
Track movement: Add one to the penalty for each different room beyond the first used for a track.

The lower the penalty the better. Only condsidered after there are confirmed to be no hard violations.

Example:
T1: Auditorium @ 9:00
T2: Canyon @ 10:39
T3: Mesa @ 10:30
T4: Canyon @ 9:00
T5: Auditorium @ 13:00
T6: Mesa @ 13:00

Hard Violations: No room has two talk at the same time. No speaker has two talks at the same time. Therefore there are no hard violations.

Soft Penalties:
T6 is at 13:00 but prefers 10:30 - +1
AI uses Auditorium and Mesa - +1
Soft Penalty: 2

## 3. Min-Conflicts

Conflicted-talk:
This evaluator returns any talk with a hard violation. If there are no conflicted talks, the schedule is feasible and the agent stops. 

Candidate placements:
This will very that the move command puts the talks into a legal domain. Each candidate will be evaulated for being a legal move. 

Lexicographic scoring:
Candidates are compared in priority order as follows:
Hard violations: Lowest number of hard violations. 
Soft Penalty: Prefers lower soft penalty scores.

Current value:
While the current value is important we will not be using it to compare to potential candidates. The current value can be used as a baseline to evaluate the schedule. 

Tie breaking: If two candidates both have the same number hard violations and the same soft penalty score a random one will be chosen using random.Random(seed)

Budget and stopping:
The budget will limit the amount of total moves we can make. After 20 moves the program will stop.

Metrics:
After each one this will be what is reported:
Feasability: Does the final schedule have zero hard violations.
Edits: How many moves were made.
Evaluator Calls: number of times the evaluator is called
Runtime Seconds: the amount of time the program takes to run.

## 4. LLM Tool Policy

**Exact model tag:** `Gemma-4-26B-A4B-it-oQ4e-mtp`<br>
**Endpoint category:** Course OpenAI-compatible service (`http://golem:8000/v1`); API key supplied via the `OPENAI_API_KEY` environment variable and not recorded here<br>
**Temperature:** 0<br>
**Seed support and value:** The seed is passed through to the course endpoint's `seed` request field; seeds 0, 1, and 2 were used, one per paired run

### Prompt and Tool Schema

The LLM is asked to repair the current schedule by returning exactly one JSON
move request. The final report must include the exact system and user messages
used by `LLMRepairAgent`; those strings should be copied from the completed
implementation or provided in a reproducible appendix. The model is not
allowed to rewrite the full schedule or return multiple moves.

The required JSON object has this form:

```json
{"tool":"move","talk_id":"T1","room":"Canyon","slot":"10:30"}
```

`tool` must be `"move"`; `talk_id` must identify a known talk; and `room` and
`slot` must identify a placement in that talk's legal domain. JSON objects with
duplicate keys are rejected instead of allowing a later value to silently
replace an earlier one. For example, a request containing two `talk_id` keys is
malformed.

The conversation history is bounded by `history_limit`, which defaults to six
prior outcomes. Only the most recent outcomes are serialized in later prompts;
the current schedule remains authoritative. When `history_limit=0`, no prior
outcomes are included, so the request is based only on the current problem and
schedule.

The parser requires one JSON object with the required fields and the correct
value types. It rejects malformed JSON, the wrong tool name, unknown talks,
unknown rooms or slots, placements outside the talk's domain, and requests that
repeat the talk's current placement. Only a request that passes all checks is
applied with `move()` and then evaluated for hard violations and soft penalty.

### Validation and Failure Handling

Each model call is counted before the client is invoked, so every request
attempt consumes one unit of the call budget. A malformed request is a model
response that cannot be parsed as the required JSON object, including invalid
JSON or duplicate keys. An invalid request parses as JSON but fails schema or
domain validation, such as using an unknown talk, an unknown room or slot, or
an illegal talk placement. A repeated request asks for the talk's current
placement. These requests are rejected, recorded in their corresponding
metrics, and leave the schedule unchanged.

If the client raises an ordinary `Exception`, the agent records a client
failure using only the exception type, such as `client failure: TimeoutError`.
The exception message and any response contents are not retained. The failed
call still consumes budget, the schedule remains unchanged, and the agent may
continue with another call. The implementation catches `Exception`, not
`BaseException`, so process-control events such as interruption are not
silently converted into ordinary client failures.

A model proposal does not prove feasibility. Even a well-formed, domain-valid
move can create a room collision, speaker overlap, or audience conflict. After
an accepted move is applied, the deterministic evaluator must calculate the
resulting hard violations and soft penalty. Only a final schedule with zero
hard violations is considered feasible.

## 5. Controlled Experiment

**Paired command (`--compare --live`):**
```
python3 run_experiment.py --compare --live \
  --model Gemma-4-26B-A4B-it-oQ4e-mtp \
  --endpoint http://golem:8000/v1 --temperature 0 --seeds 0,1,2 \
  --max-tokens 8192
```
<br>
**Utah Tech Tailnet connection confirmed:** [Yes]<br>
**Scenarios:** conference-1, conference-2, conference-3, conference-4 (all four)<br>
**Seeds:** 0, 1, 2<br>
**Budget:** 20 calls/moves per run<br>
**Machine/runtime context:** macOS 26.6.2 (Darwin 25.6.0, arm64), Python 3.9.6,
connected to the course endpoint at `http://golem:8000/v1` over the Utah Tech
Tailnet

| Method | Runs | Feasible | Rate | Mean final hard | Successful runs | Mean soft among successes | Mean edits | Edit variance/range | Mean runtime | Runtime variance/range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Min-conflicts | 12 | 12 | 100% | 0.00 | 12 | 4.83 | 3.00 | 1–4 | 0.002684s | 0.000517s–0.004380s |
| LLM policy | 12 | 12 | 100% | 0.00 | 12 | 6.08 | 3.17 | 2–5 | 255.351597s | 87.980007s–528.042619s |

| Method-specific metric | Mean per applicable run | Total | Denominator |
|---|---:|---:|---|
| Min-conflicts evaluator calls | 11.75 | 141 | 12 runs |
| LLM model calls | 5.50 | 66 | 12 runs |
| LLM malformed requests | 2.08 | 25 | 12 runs |
| LLM invalid requests | 0.00 | 0 | 12 runs |
| LLM repeated requests | 0.00 | 0 | 12 runs |
| LLM client failures | 0.25 | 3 | All 12 runs, including failure runs |

Per-pair detail (all 12 pairs, min-conflicts / LLM edits and LLM client failures):

| Pair | Min-conflicts edits | LLM edits | LLM client failures |
|---|---:|---:|---:|
| conference-1/seed-0 | 3 | 4 | 0 |
| conference-1/seed-1 | 3 | 4 | 1 |
| conference-1/seed-2 | 3 | 4 | 0 |
| conference-2/seed-0 | 3 | 5 | 0 |
| conference-2/seed-1 | 3 | 2 | 1 |
| conference-2/seed-2 | 3 | 2 | 0 |
| conference-3/seed-0 | 4 | 3 | 0 |
| conference-3/seed-1 | 4 | 5 | 0 |
| conference-3/seed-2 | 3 | 3 | 0 |
| conference-4/seed-0 | 1 | 2 | 1 |
| conference-4/seed-1 | 2 | 2 | 0 |
| conference-4/seed-2 | 4 | 2 | 0 |

All 3 LLM client failures were truncated completions (`finish_reason: "length"`):
the model spent its full token budget on `reasoning_content` before emitting
the `content` field, which `llm_client.py` originally accessed with a plain
`data["choices"][0]["message"]["content"]` key lookup and therefore raised a
`KeyError`. This was fixed by falling back to `.get("content", "")` so a
truncated completion is instead treated as a malformed request in the retry
loop, and `--max-tokens` was raised from the default 2048 to 8192 to give the
model enough budget to reach the answer after its reasoning.

Do not discard request or client failures, and retain affected runs in every
all-run denominator. Soft penalty is conditional on success; state the
successful-run denominator rather than treating failures as zero or missing
without explanation. Include the runner's explicit pair identifiers.

## 6. Representative Traces

Both traces below start from the same `conference-1`/seed-0 pair
(`--scenario conference-1 --seeds 0`), the shared, immutable initial schedule
for that scenario, so the two policies are compared from an identical
starting point.

### Min-Conflicts Trace

Initial evaluation: 5 hard violations, soft penalty 5.

| Step | Talk moved | New placement | Outcome | Hard violations after | Soft penalty after |
|---:|---|---|---|---:|---:|
| 1 | T4 | Canyon, 13:00 | applied | 4 | 4 |
| 2 | T1 | Auditorium, 13:00 | applied | 1 | 5 |
| 3 | T5 | Auditorium, 10:30 | applied | 0 | 5 |

Stopped after 3 moves because `hard_violations` reached 0 (feasible), well
under the 20-move budget. Final: feasible, soft penalty 5, 13 evaluator calls
(one per candidate move considered, not just applied moves).

### LLM Trace

Same start: 5 hard violations, soft penalty 5.

| Step | Request | Outcome | Hard violations after | Soft penalty after |
|---:|---|---|---:|---:|
| 1 | *(none — see below)* | malformed | 5 | 5 |
| 2 | `{"tool":"move","talk_id":"T1","room":"Auditorium","slot":"10:30"}` | applied | 2 | 6 |
| 3 | `{"tool":"move","talk_id":"T2","room":"Canyon","slot":"10:30"}` | applied | 2 | 5 |
| 4 | `{"tool":"move","talk_id":"T1","room":"Auditorium","slot":"13:00"}` | applied | 1 | 5 |
| 5 | *(none — see below)* | malformed | 1 | 5 |
| 6 | *(none — see below)* | malformed | 1 | 5 |
| 7 | *(none — see below)* | malformed | 1 | 5 |
| 8 | `{"tool":"move","talk_id":"T5","room":"Auditorium","slot":"10:30"}` | applied | 0 | 5 |

Steps 1, 5, 6, and 7 recorded an empty request string because the model's
completion was truncated before the `content` field was written
(`finish_reason: "length"`, all `2048`–`8192` token budget spent on
`reasoning_content`); `agents.py` records the raw response text in the trace,
which is empty in that case, so these are malformed requests rather than
client failures. Stopped after 8 model calls when `hard_violations` reached 0
(feasible), leaving 12 of the 20-call budget unused. Final: feasible, soft
penalty 5 — the same soft penalty as min-conflicts on this pair, reached in
more edits (4 vs. 3) and roughly 820,000x the wall-clock time (451.29s vs.
0.00055s), driven entirely by per-call model latency rather than search
inefficiency.

## 7. Analysis

### Guarantees and Search Behavior

`MinConflictsAgent` has a structural guarantee that `LLMRepairAgent` does not:
for a conflicted talk, it evaluates every candidate placement in that talk's
domain and applies the lexicographically best one (fewest hard violations,
then lowest soft penalty), so each applied move is provably at least as good
as the current placement by that ordering. It has no guarantee of finding the
global optimum — it is a local search and can settle for a schedule with
higher soft penalty than some other feasible schedule — but on all 12 pairs it
reached zero hard violations well inside the 20-move budget (mean 3.00 edits,
range 1–4).

`LLMRepairAgent` has essentially the opposite profile. The only guarantee the
code enforces is domain legality: a proposed move is applied only if its
`talk_id`, `room`, and `slot` are a placement in that talk's domain
(`agents.py`, the `legal` check before `move()` is called). Domain legality
says nothing about the move's relational effect — nothing rejects a legal move
that creates a new room collision, speaker overlap, or audience conflict
elsewhere in the schedule. In the traced run, hard violations happened to
decrease or hold steady after every applied move (5→2→2→1→0), but that is an
empirical property of this run, not a property the validation logic
guarantees. The agent can also spend calls on outcomes that make no progress
at all — malformed, invalid, repeated, or client-failure calls leave the
schedule untouched — which is exactly what the 25 malformed calls out of 66
total model calls in the full experiment show.

### State Versus Path and Invariants

Both policies are judged only by the final schedule's feasibility (and,
conditionally, its soft penalty) — the sequence of edits used to get there is
not part of the goal. `move()` enforces one invariant along every path
regardless of policy: it only ever applies a placement that is legal for that
talk's domain, so the schedule is structurally valid (every talk assigned
exactly once, to a domain-legal placement) at every step, even while it is
still infeasible. This is why a rejected LLM request (malformed, invalid,
repeated) is safe to simply skip — the schedule invariant is never at risk,
only budget is spent. On the traced pair, min-conflicts and the LLM policy
reached the identical final soft penalty (5) despite very different paths: 3
monotonically-improving moves for min-conflicts versus 8 model calls for the
LLM (4 applied, 4 malformed), with soft penalty briefly rising to 6 mid-path
before returning to 5. The final states are equally acceptable under the
stated goal; the extra malformed calls and the temporary soft-penalty increase
along the LLM's path do not by themselves disqualify its result.

### Prompt Sensitivity and Reproducibility

The dominant sensitivity observed was not prompt wording but token budget.
With `--max-tokens 2048`, every one of the 60 live LLM calls across all 12
pairs failed with a `client failure: KeyError`, because the model's
`reasoning_content` alone consumed the full completion budget before it wrote
a `content` field (`finish_reason: "length"`). Raising `--max-tokens` to 8192
— with the prompt text otherwise unchanged — dropped client failures from 60
to 3 and let the agent reach feasibility on all 12 pairs. Malformed requests
(25 total) persisted even at the higher budget, which suggests the model is
still occasionally truncating or otherwise failing to close its JSON.

Reproducibility is limited even at `temperature=0` with a fixed `seed`: the
number of malformed/client-failure outcomes differed across seeds and
scenarios (e.g. `conference-1`/seed-1 and `conference-2`/seed-1 each recorded
1 client failure while their sibling seeds recorded 0), and the same
scenario/seed pair was not independently re-run to check for exact
byte-identical output. Temperature and seed control decoding, but they do not
guarantee identical reasoning length or a deterministic point of truncation
on a served, possibly batched, inference endpoint, so exact repeatability of
this experiment is not established, only its qualitative outcome (12/12
feasible, similar soft-penalty range).

### Resource Fairness

The paired design starts both policies from the exact same problem and
initial schedule for each scenario/seed combination
(`run_paired_comparison`), so neither policy has an advantage in starting
state. The shared budget is nominally symmetric — 20 units for either policy
— but the two policies spend a unit of budget on different things: min-conflicts
consumes one evaluator call per *candidate* placement it considers for the
most-conflicted talk (mean 11.75 evaluator calls across runs, more than its
mean 3.00 edits, since only the chosen candidate becomes an edit), while the
LLM agent consumes one model call per *attempt*, whether or not it results in
an edit (mean 5.50 model calls, of which many were malformed). By call count
alone, the LLM policy actually used less of its budget. But the real
resource — wall-clock time — is nowhere close to symmetric: mean runtime was
0.0027s for min-conflicts versus 255.35s for the LLM policy, a difference of
roughly five orders of magnitude driven entirely by per-call model latency.
A 20-unit budget that costs microseconds per unit for one policy and tens of
seconds to minutes per unit for the other is fair in the sense the assignment
defines (equal call/move allowance), but it does not represent equal
real-world cost.

### Constraint Verification

Programmatic domain validation before `move()` and deterministic re-evaluation
after `move()` are both necessary because the model's output cannot be
trusted as self-verifying. Across the full experiment, 25 of 66 live model
calls (38%) produced output that could not even be parsed as the required
JSON object, and as discussed above, a syntactically valid, domain-legal move
is not by itself proof that the move does not introduce a new relational
conflict elsewhere in the schedule. `constraints.evaluate()` is the only
ground truth for hard-violation and soft-penalty counts; it is called after
every applied move specifically because neither the model's confidence nor
the shape of its JSON response is evidence of correctness.

### PEAS Alignment and External Validity

The experiment measures exactly the performance criteria defined in Section 1:
`RepairResult.feasible` and `RepairMetrics` report hard-violation feasibility,
soft penalty conditional on success, and calls/edits against the fixed
20-unit budget, with no other proxy substituted. The sensors and actuators
supplied to the LLM (the serialized schedule, per-talk domains, evaluator
output, and bounded history) match what Section 1's PEAS analysis specifies,
so the comparison isolates decision quality and latency rather than an
information asymmetry between the two policies.

The external validity is limited by the benchmark's scale and determinism,
both flagged as limitations in Section 1: six talks, three rooms, three
slots, and a static, fully observable environment. The malformed-rate and
runtime findings here should not be generalized past this scale — a larger
conference would serialize a larger `talks`/`domain` payload per prompt,
which the max-tokens finding above suggests would increase truncation risk
rather than decrease it, and a real conference's non-deterministic
disruptions (speaker tardiness, room/equipment failures) are entirely outside
what either policy was tested against here.

## 8. Testing and Reproducibility

**Test command/result:**
```
python3 -m unittest test_conference.py test_interfaces.py test_llm_client.py test_student.py -v
```
`Ran 14 tests in 0.004s — OK` (all passing).

- `test_evaluator_counts_hard_violations_and_soft_penalty` (`test_student.py`) checks
  that `constraints.evaluate` reports the correct hard-violation count and soft
  penalty for a fixed, hand-constructed schedule.
- `test_invalid_move_is_rejected` checks that `conference.move()`/the LLM
  validation path refuses a placement outside a talk's domain rather than
  silently applying it.
- `test_min_conflicts_repairs_schedule` checks that `MinConflictsAgent` drives a
  fixed infeasible starting schedule to zero hard violations within budget.
- `test_duplicate_json_keys_are_malformed` checks that a model response
  containing a repeated JSON key (e.g. two `talk_id` keys) is rejected as
  malformed rather than silently taking the last value, using
  `reject_duplicate_keys`.
- `test_zero_history_sends_no_prior_outcomes` checks that `history_limit=0`
  produces a user prompt whose `"history"` field is an empty list.
- `test_client_failure_preserves_state_and_consumes_budget` checks that when
  the chat client raises an exception, the schedule is left unchanged, the
  call still counts against the budget, and the failure is recorded as
  `client failure: <ExceptionType>`.
- `test_chat_sends_required_request_and_returns_content` /
  `test_chat_requires_nonempty_key` (`test_llm_client.py`) check
  `OpenAICompatibleClient` builds the expected request body and rejects an
  empty API key, using a mocked HTTP layer rather than a live model.
- `test_llm_agent_applies_valid_json_move` (`test_interfaces.py`) checks that a
  single well-formed scripted JSON move is parsed, validated, and applied.
- `test_prompt_requires_json_only_no_prose` checks that the system prompt
  contains the JSON-only instructions the parser relies on.

All of these use `ScriptedClient`, a deterministic fake that returns
pre-scripted response strings instead of calling a model
(`llm_client.py:53-65`). They prove the agent's parsing, validation, budget
accounting, and prompt construction are correct for known inputs, but they
cannot show whether a real model reliably produces legal, useful moves, how
often it produces malformed or truncated output, or how its latency compares
to `MinConflictsAgent`. That evidence only comes from the live `--compare
--live` run against the course endpoint in Section 5, which is why the
scripted suite and the empirical experiment are reported separately.

## 9. AI-Assistance Disclosure

**Tools:** Claude Code (Claude Sonnet 5)<br>
**Material effect:** Claude diagnosed a live-run bug where every LLM call
failed as a `client failure: KeyError` (root cause: the model exhausted
`max_tokens` on `reasoning_content` before writing `content`, so
`data["choices"][0]["message"]["content"]` raised `KeyError`); proposed and
applied the fix (`llm_client.py`: `.get("content", "")` instead of a bare key
lookup) and the mitigation (raising `--max-tokens` to 8192); found and fixed a
mismatch between the system prompt text in `agents.py` and the literal
substrings asserted by `test_prompt_requires_json_only_no_prose`.
Helped with drafting the written analysis for the project results.<br>
**Verification:** The prompt/test fix was verified by re-running
`python3 -m unittest test_conference.py test_interfaces.py test_llm_client.py
test_student.py -v`, which went from 1 failure to 14/14 passing. The
`max-tokens` fix was verified empirically: client failures dropped from 60/60
live calls (100%) to 3/66 (4.5%) across the full 12-pair experiment, and
feasibility rose from 0/12 to 12/12. [Student: confirm you reviewed Section 7's
analysis and the transcribed metrics against your own run output before
submitting, and note any edits you made.]

## Submission Checklist

- [ ] One accessible PDF named `lastname-firstname-conference-repair.pdf` with
      selectable text and semantic headings/tables.
- [ ] All four scenarios and seeds 0, 1, 2 appear in paired results.
- [ ] Exact model configuration, prompts, failures, and denominators are present.
- [ ] Both representative traces are included.
- [ ] PEAS, environment classifications, interaction cycle, and implementation
      mapping are complete and consistent with the technical work.
- [ ] Private GitHub URL, submitted commit, and `fractal13` read access are confirmed.
- [ ] Tests pass and no credentials, tokens, authenticated URLs, or secrets are
      present in the PDF or repository.
- [ ] AI-assistance disclosure is complete.
