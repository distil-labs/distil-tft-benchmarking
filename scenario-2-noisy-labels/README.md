# Scenario 2 — Noisy Labels

End-to-end distillation of a multi-turn tool-calling SLM from noisy production traces.

- **Task type:** `multi-turn-tool-calling-closed-book`
- **Student:** `Qwen3-1.7B` · **Teacher:** `zai.glm-5`
- **Raw traces:** `tft-raw-data/` (327 conversations + `task.txt`)
- **Distil Labs workspace:** `distil-workspace/`

## What happened in `distil-workspace/`

### 1. Data prep (`convert_traces.py`)
Converts `tft-raw-data/traces.jsonl` — each line a `{"context": "<JSON-stringified messages>"}` — into the `openai_messages` format expected by the platform: `{"messages": [...]}` per line, `ensure_ascii=True`, control chars stripped. Output: `traces.jsonl` (327 conversations).

### 2. Job + config authored
- `job_description.json` — task description, 3 tool schemas (`FindRestaurants`, `ReserveRestaurant`, `respond_to_user`), and the LLM-as-a-Judge rubric lifted from `task.txt`.
- `config.yaml` — key choices:
  - `trace_processing.convert_to_single_turn: false` (keep multi-turn conversations intact)
  - `trace_processing.teacher_model_name: zai.glm-5` (GLM-5 arbitrates committee relabels)
  - `synthgen.validation_max_total_length: 15000` (trace p90 ≈ 8.5k chars)
  - `synthgen.mutation_topics` — 5 conversation-length patterns from `task.txt`

### 3. TFT upload + trace processing
`distil model upload-traces` kicked off the pipeline: relevance filtering → committee relabeling (4 teachers, GLM-5 arbitrating) → multi-turn-preserving train/test split.

### 4. Original-model baseline (`original-model-analysis.md`)
Downloaded the production model's predictions and compared against the relabeled ground truth. High per-turn agreement (0.95 LLM-Judge) on the test slice; relabeling does heavier lifting on the training base.

### 5. Teacher evaluation (`teacher-eval-analysis-iter-1.md`)
`distil model run-teacher-evaluation` scored `zai.glm-5` on the test set: **LLM-Judge = 0.808 → PROCEED** (≥ 0.70 threshold for tool calling).

### 6. Training + analysis (`training-analysis-iter-1.md`)
~6 h on the platform. Final scores on N=78:

| | Base (untuned) | Teacher | Tuned |
|---|---:|---:|---:|
| LLM-as-a-Judge | 0.513 | 0.808 | **0.846** |
| Function-name match | 45/78 | 69/78 | **76/78** |

Tuned student **beats the teacher** on the primary metric (+0.0385), adds +0.333 over the untuned base, and has zero empty predictions. **Verdict: DEPLOY.**

## Files in `distil-workspace/`

| File | Purpose |
|---|---|
| `convert_traces.py` | Raw-trace → `openai_messages` conversion |
| `traces.jsonl` | Converted traces uploaded to the platform |
| `job_description.json` | Task description, tools, judge rubric |
| `config.yaml` | Training + trace-processing configuration |
| `original-model-predictions.jsonl` · `teacher-eval-full-download.jsonl` · `base-model-predictions-download.jsonl` · `tuned-model-predictions-download.jsonl` | Per-example predictions at each stage |
| `original-model-analysis.md` | Baseline report — production model vs. relabeled ground truth |
| `teacher-eval-analysis-iter-1.md` | Teacher evaluation report (PROCEED) |
| `training-analysis-iter-1.md` | Final training report (DEPLOY) |
