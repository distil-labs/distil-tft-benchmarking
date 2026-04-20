# Original Model Analysis Report

## 1. Overview
- **Model ID:** fc615b15-b01b-42e6-9d72-afe545e5083b
- **Task type:** multi-turn-tool-calling-closed-book
- **Original model:** unknown (production traces in `scenario-2-noisy-labels/tft-raw-data/traces.jsonl`)
- **Goal:** Virtual restaurant assistant — at each turn, call `FindRestaurants`, `ReserveRestaurant`, or `respond_to_user`.

### 1.1 Input/Output
**Input:** JSON array (stringified) of the conversation history so far — alternating `user` messages (natural language or tool results) and `assistant` messages (previous tool calls).
```
[{"role": "user", "content": "I want some breakfast in Fairfield"}, ...]
```
**Output:** JSON tool call of the form `{"name": "<tool>", "parameters": {...}}`.
```
{"name": "FindRestaurants", "parameters": {"city": "Fairfield", "cuisine": "Breakfast"}}
```

## 2. Test Set Statistics
- **Total examples:** 77
- **Provenance:** platform-generated test split (no user-provided `test.jsonl`); each example is a conversation truncated before one assistant turn.
- **Label distribution (ground-truth function):** `respond_to_user` 63 · `ReserveRestaurant` 8 · `FindRestaurants` 6.
- **Field lengths (chars):** question min=63 / median=1758 / max=5488; answer min=68 / median=117 / max=252.
- **Turns per example:** min=1, median=9, max=23 — coverage spans all conversation-length buckets from `task.txt`.

## 3. Trace Processing Configuration
- **Observation format:** `openai_messages`
- **Relabeling enabled:** `true` (default)
- **Convert to single turn:** `false` (multi-turn structure preserved)
- **Relabeling committee:** default — `zai.glm-5`, `Qwen3-235B-A22B-Instruct-2507`, `openai.gpt-oss-120b-thinking`, `deepseek.v3.2`
- **Non-default trace_processing parameters:** `convert_to_single_turn=false`, `teacher_model_name=zai.glm-5`, `num_traces_as_testing_base=100`.

## 4. Aggregate Metrics

| Metric | Original Model |
|--------|---------------:|
| LLM-as-a-Judge | **0.9481** |
| tool_call_equivalence | 0.9221 |
| binary_tool_call | 0.9221 |
| staged_tool_call | 0.9675 |
| ROUGE-L | 0.9507 |

**Verdict:** INFORMATIONAL — **HIGH agreement (≥ 0.8)** on the test set. Relabeling didn't change much on the test turns; production labels look largely clean *at decision points the evaluator samples*. Continue to teacher evaluation.

> Caveat: raw visual inspection of the full conversations in `traces.jsonl` showed clearly-wrong outputs (wrong domain, wrong parameters, ignored user intent). The per-turn test slice sees cleaner labels than the raw conversations — likely because many turns are routine greetings/acknowledgments that even a noisy model gets right, while the noise concentrates in decision points and in *history* turns the evaluator doesn't score. Committee relabeling of the training base will still be doing real work — the test-side 0.92 does not imply the training data was clean end-to-end.

## 5. Agreement Breakdown
- **Function-name match:** 75 / 77 (97.4%)
- **Exact tool-call match:** 71 / 77 (92.2%)
- **LLM-judge pass:** 73 / 77 (94.8%)
- **Disagrees:** 6 / 77 (7.8%)

### Function-name confusion matrix (rows = ground truth, cols = original prediction)

| | FindRestaurants | ReserveRestaurant | respond_to_user |
|---|---:|---:|---:|
| **FindRestaurants**   | 6 | 0 | 0 |
| **ReserveRestaurant** | 0 | 7 | 1 |
| **respond_to_user**   | 0 | 1 | 62 |

Only 2/77 function-name mismatches, and both are decision-point confusions between `ReserveRestaurant` and `respond_to_user`.

## 6. Analysis of Disagreements

**Patterns identified:**
1. **Paraphrase-only differences (2/6).** Same function, same intent, different wording (#1, #6). Judge correctly scores these as `good`; they pull `tool_call_equivalence` down without reflecting model error.
2. **Service-call vs. respond confusion at decision points (2/6).** #2 reserves before confirming with the user; #3 claims a reservation was made without actually calling `ReserveRestaurant`. These are the genuinely noisy labels scenario-2 is about — the model decides "service call vs. talk to user" incorrectly.
3. **Lost-context factual errors (2/6).** #4 answers a stale question about address after the reservation completed; #5 closes the conversation with "anything else?" when the user asked a factual question. The model stopped tracking what was last asked.

**Implications for training:**
- The student will learn the *relabeled* distribution, which systematically fixes decision-point and context-tracking errors. If the teacher maintains this quality on synthetic data, distillation should produce a student that's meaningfully better than the original model at exactly these weak spots.
- No markdown-fence issue in relabeled answers (all 77 answers parse cleanly as JSON).
- No `output_is_json` flag needed in config — tool-call format already enforces JSON structure.

**Representative disagreements:**

| # | Last user turn (truncated) | Expected | Original | Cause |
|---|---|---|---|---|
| 2 | "Can you tell me if they have a live band?" | `respond_to_user` answering about live band | `ReserveRestaurant(...)` | Early service call |
| 3 | "Yes, go ahead." | `ReserveRestaurant(Lemongrass, Martinez, 2019-03-04, 19:00, 1)` | `respond_to_user("Great, your reservation was made...")` | Hallucinated completion (no actual service call) |
| 4 | Tool result after `ReserveRestaurant` | `respond_to_user` confirming reservation | `respond_to_user` answering address question | Lost context |
| 5 | "Do you know if their menu is inexpensive and what their address is?" | `respond_to_user` with price+address | `respond_to_user("Is there anything else...")` | Ignored factual question |
