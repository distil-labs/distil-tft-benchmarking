# Teacher Evaluation Analysis Report

## 1. Overview
- **Model ID:** fc615b15-b01b-42e6-9d72-afe545e5083b
- **Task type:** multi-turn-tool-calling-closed-book
- **Goal:** Virtual restaurant assistant — at each turn, call `FindRestaurants`, `ReserveRestaurant`, or `respond_to_user`.

### 1.1 Input/Output
**Input:** stringified JSON conversation history (alternating `user` natural-language turns and `assistant` tool-call turns).
**Output:** JSON tool call, `{"name": "<tool>", "parameters": {...}}`.

## 2. Test Set Statistics
- **Total examples:** 78
- **Ground-truth function distribution:** `respond_to_user` 63 · `ReserveRestaurant` 10 · `FindRestaurants` 5
- **Field lengths (chars):** question median ≈ 1871, max 5898; answer median ≈ 148, max 329.

## 3. Configuration Summary
- **Task:** multi-turn-tool-calling-closed-book
- **Student:** `Qwen3-1.7B`
- **Teacher:** `zai.glm-5`
- **Non-default parameters:** `trace_processing.convert_to_single_turn=false`, `trace_processing.teacher_model_name=zai.glm-5`, `trace_processing.num_traces_as_testing_base=100`, `synthgen.validation_max_total_length=15000`, `synthgen.mutation_topics` (5 conversation-length patterns from `task.txt`).

## 4. Aggregate Metrics

| Metric | Score |
|--------|------:|
| **LLM-as-a-Judge** (primary) | **0.8077** |
| staged_tool_call | 0.6955 |
| ROUGE-L | 0.4584 |
| tool_call_equivalence | 0.0769 |
| binary_tool_call | 0.0769 |

**Primary-metric choice.** The tool schema includes `respond_to_user(message: str)` with a free-text argument. Per `references/tasks/teacher-evaluation.md`, `tool_call_equivalence` is unreliable for free-text arguments — it rejects paraphrases that are semantically correct. LLM-as-a-Judge is the correct primary metric here and `tool_call_equivalence` is shown for completeness only.

**Verdict:** **PROCEED** (0.8077 ≥ 0.70 threshold for tool calling).

## 5. Agreement Breakdown
- **LLM-Judge pass:** 63 / 78 (80.8%)
- **Function-name match:** 69 / 78 (88.5%)
- **Empty predictions:** 3 / 78 (3.8%) — teacher returned `""`.
- **Date handling:** all 4 predicted `date` values use 2019, matching the trace timeframe — no year drift.

### Function-name confusion matrix (rows = GT, cols = teacher)

| | FindRestaurants | ReserveRestaurant | respond_to_user | `<none>` |
|---|---:|---:|---:|---:|
| **FindRestaurants**   | 4 | 1 | 0 | 0 |
| **ReserveRestaurant** | 0 | 6 | 4 | 0 |
| **respond_to_user**   | 0 | 1 | 59 | 3 |

The 4 `ReserveRestaurant → respond_to_user` and 1 `respond_to_user → ReserveRestaurant` swaps cluster at decision-point turns (confirmation, mid-conversation parameter changes). 3 of the 15 judge-failures are the empty predictions on minimal-context inputs.

## 6. Analysis of Disagreements (15 judge-failed)

**Patterns identified:**

1. **Decision-point confusion (≈ 7 cases).** The teacher either fires `ReserveRestaurant` before the user has confirmed (row 18: *"I want to try booking again. Is there anything available at 7:30 pm?"* → teacher reserves directly instead of asking for confirmation), or picks `respond_to_user` when the user has already confirmed and the service call is expected (rows 16, 25, 26: user says *"Yes that works for me"* and the teacher answers an unrelated follow-up instead of reserving).

2. **Empty predictions on minimal-context inputs (3 cases).** Single-turn opens with vague queries like *"I need a reservation to a restaurant."* trigger the teacher to return an empty string instead of a clarifying `respond_to_user` call.

3. **Paraphrase / content-scope mismatches (≈ 5 cases).** Both outputs are plausible `respond_to_user` replies but differ on which question is answered — e.g. row 25: user asks about price, teacher hedges with *"I'll make the reservation now and check the price range for you"* where the ground-truth simply reserves.

**Recommended actions (optional — not blocking):**
- The failures do not point to a job-description or data fix. Proceed to training.
- Worth monitoring after training: if the student also produces empty outputs on minimal-context greetings, add a `mutation_topic` covering "user opens with a vague/minimal request" to force more such examples during synthgen.

**Representative failures:**

| # | Last user turn | Expected | Teacher | Failure mode |
|---|---|---|---|---|
| 16 | "Yes, that works for me. What is their address? Do they serve alcohol?" | `ReserveRestaurant(Kingston 11 Cuisine, Oakland, …)` | `respond_to_user` giving address + alcohol info | Missed service-call moment |
| 18 | "I want to try booking again. Is there anything available at 7:30 pm?" | `respond_to_user` confirming details | `ReserveRestaurant(...)` directly | Early service call |
| 25 | "Yes that works for me. Is it in the bargain price range?" | `ReserveRestaurant(Coupa Cafe - Ramona, …)` | `respond_to_user("I'll make the reservation now and check …")` | Hedge instead of committing to the call |
| — | "I need a reservation to a restaurant." | `respond_to_user("Do you have a preferred city and place?")` | `""` (empty) | Refused on minimal context |
