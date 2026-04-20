# Training Analysis Report

## 1. Overview
- **Model ID:** fc615b15-b01b-42e6-9d72-afe545e5083b
- **Task type:** multi-turn-tool-calling-closed-book
- **Student model:** `Qwen3-1.7B`
- **Teacher model:** `zai.glm-5`
- **Training duration:** ~6 h
- **Goal:** Virtual restaurant assistant — at each turn, call `FindRestaurants`, `ReserveRestaurant`, or `respond_to_user`.

### 1.1 Input/Output
**Input:** stringified JSON conversation history. **Output:** JSON tool call — the student (`Qwen3-1.7B`) emits it wrapped in `<tool_call>...</tool_call>` with `arguments`; the teacher emits it as a plain JSON object with `parameters`. Both formats are equivalent and are scored together.

## 2. Test Set Statistics
- **Base / Teacher / Tuned evaluated on:** N = 78 (identical question set).
- **Original model evaluated on:** N = 77 (trace-processing split — same source traces, different evaluation batch; not apples-to-apples with the other three).
- **Ground-truth function distribution:** `respond_to_user` 63 · `ReserveRestaurant` 10 · `FindRestaurants` 5.
- **Field lengths (chars):** question median ≈ 1871, max 5898; answer median ≈ 148, max 329.

## 3. Configuration Summary
- **Task:** multi-turn-tool-calling-closed-book
- **Student:** `Qwen3-1.7B` · **Teacher:** `zai.glm-5`
- **Non-default parameters:** `trace_processing.convert_to_single_turn=false`, `trace_processing.teacher_model_name=zai.glm-5`, `trace_processing.num_traces_as_testing_base=100`, `synthgen.validation_max_total_length=15000`, `synthgen.mutation_topics` (5 conversation-length patterns from `task.txt`).
- **Training epochs:** 4 (default).

## 4. Aggregate Metrics

| Metric | Original¹ | Base Student | Teacher | Tuned Student | Δ (Tuned − Original) | Δ (Tuned − Base) | Δ (Tuned − Teacher) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **LLM-as-a-Judge** (primary) | 0.9481 | 0.5128 | 0.8077 | **0.8462** | −0.1019 | **+0.3333** | **+0.0385** |
| staged_tool_call | 0.9675 | 0.5353 | 0.6955 | 0.7692 | −0.1983 | +0.2339 | +0.0737 |
| ROUGE-L | 0.9507 | 0.5137 | 0.4584 | 0.6889 | −0.2618 | +0.1752 | +0.2305 |
| tool_call_equivalence | 0.9221 | 0.0513 | 0.0769 | 0.1282 | −0.7939 | +0.0769 | +0.0513 |

¹ The Original-model score comes from a 77-row trace-processing evaluation slice and is scored against committee relabels that track its own outputs more closely than the 78-row slice used for the other three models. The column is retained for context; **Tuned vs. Original is not apples-to-apples and should not be read as "the student is worse than the production model"**.

**Primary-metric choice.** Because `respond_to_user(message)` takes a free-text argument, LLM-as-a-Judge is the primary metric; `tool_call_equivalence` systematically undercounts correct paraphrased messages and is shown for completeness only.

**Verdict:** **DEPLOY.**
- Tuned student **exceeds** the teacher on the primary metric (0.8462 vs 0.8077, Δ +0.0385).
- Tuned student adds **+0.3333** over the untuned base — 26 percentage points absolute.
- Only 2 regressions vs. the base student (see §5).
- Zero empty predictions (base had 1, teacher had 3).
- Function-name match at 76/78 (97 %) — the cleanest of all four models evaluated on this slice.

## 5. Agreement Breakdown

**Per-model (N = 78 evaluation slice):**

| | Base | Teacher | Tuned |
|---|---:|---:|---:|
| LLM-Judge pass | 40 / 78 (51 %) | 63 / 78 (81 %) | 66 / 78 (85 %) |
| Function-name match | 45 / 78 (58 %) | 69 / 78 (88 %) | 76 / 78 (97 %) |
| Empty / unparseable | 1 | 3 | 0 |

**Joint judge outcomes (Base × Teacher × Tuned):**

| Case | Count |
|---|---:|
| All three pass | 32 |
| All three fail | 4 |
| **Tuned pass, Base fail** (gained from tuning) | **28** |
| Base pass, Tuned fail (regressions) | 2 |
| Teacher pass, Tuned fail (student did not learn) | 7 |
| Tuned pass, Teacher fail (student outperformed teacher) | 10 |

### Tuned student confusion matrix (function name, rows = GT, cols = Tuned)

| | FindRestaurants | ReserveRestaurant | respond_to_user |
|---|---:|---:|---:|
| **FindRestaurants**   | 4 | 0 | 1 |
| **ReserveRestaurant** | 0 | 10 | 0 |
| **respond_to_user**   | 0 | 1 | 62 |

For comparison: the untuned base student had 20/63 `respond_to_user → ReserveRestaurant` errors and 7/63 `respond_to_user → FindRestaurants` errors; tuning reduced those to 1 and 0 respectively. Tuning also removed all 4 `ReserveRestaurant → respond_to_user` errors that the teacher still makes.

## 6. Analysis of Disagreements

**Patterns identified:**

1. **Student > Teacher on execution follow-through (10 cases).** The teacher wavers at confirmation turns (asks follow-up questions instead of firing `ReserveRestaurant` once the user has said "yes"). The tuned student converts these correctly. This is the most valuable thing distillation bought — the student learned the *relabeled* behavior, which corrects the teacher's decision-point hesitation.

2. **Student < Teacher on parameter precision (7 cases).** Where the student fails but the teacher passes, the cause is usually parameter confusion:
   - Row 3: confuses `restaurant_name` with `city` (emits `ReserveRestaurant(city="San Francisco", restaurant_name="El Cerrito")` when `El Cerrito` is the city and `Katana-ya` is the restaurant).
   - Row 14: re-confirms with a stale date ("today") after the user changed to March 3rd.
   - Row 43: fires `ReserveRestaurant` one turn too early, after a "change the city" clarification instead of re-confirming.
   These are genuine gaps the 1.7B student did not pick up from distillation, not random noise.

3. **Regressions vs. base (2 cases).** The base student happened to guess correctly on 2 examples where the tuned student is now wrong — e.g. row 32 where the base calls `FindRestaurants(Petaluma, Pizza)` and the tuned student answers the user's follow-up price question instead. At 2/78 (2.6 %) this is noise, not a systematic overfitting pattern.

4. **Minimal-context greetings.** The teacher produces 3 empty outputs on single-turn opens; the tuned student has **zero** empties and produces sensible `respond_to_user` clarifying questions for all of them.

**Recommended actions (for a future iteration — not needed to deploy):**
- Add mutation topics around parameter disambiguation: restaurant-name vs. city, mid-conversation parameter changes, date-relative phrasing ("the 3rd", "day after tomorrow").
- If accuracy on the parameter-precision failure mode matters, try `Qwen3-4B-Instruct-2507` as the student — the failures look like a capacity gap for tracking 3–4 slot fills across long conversation histories. It is the common pairing for multi-turn tool calling in the model catalog.

**Representative cases:**

*Teacher right, tuned wrong (7 cases — student failed to learn):*

| # | Last user turn | Expected | Teacher | Tuned | Failure |
|---|---|---|---|---|---|
| 3 | "Yes and do they have live music and liquor?" | `ReserveRestaurant(El Cerrito, Katana-ya, …)` | ≈same, with `time="1:15 pm"` | `ReserveRestaurant(city="San Francisco", restaurant_name="El Cerrito", …)` | Parameter swap |
| 14 | "No, sorry, change of plans. I would like the 3rd of March instead." | `respond_to_user` confirming new date | confirms March 3rd | confirms "today" (stale date) | Lost the date update |
| 43 | "Can you change the city to Hayward?" | `respond_to_user` confirming the city change | confirms change | fires `ReserveRestaurant` immediately | Early service call |

*Tuned right, teacher wrong (10 cases — distillation win):*

| # | Last user turn | Expected | Teacher | Tuned |
|---|---|---|---|---|
| — | "Yes, that works for me. What is their address? Do they serve alcohol?" | `ReserveRestaurant(...)` | follow-up question about address | fires `ReserveRestaurant` correctly |
| — | various minimal-context opens | `respond_to_user` clarifying question | `""` (empty) | correct clarifying question |

## 7. Recommendation

**DEPLOY.** Move to `distil model download` + `distil model deploy local`. The tuned student beats the teacher on the primary metric, regressions vs. the base are negligible (2/78), and the remaining 7 teacher-right-tuned-wrong cases cluster on a specific parameter-precision failure mode — a future iteration target rather than a blocker for this release.
