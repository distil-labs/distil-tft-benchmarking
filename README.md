# TFT (Training from Traces) Benchmark

**Blog post**: [Why Training on Production Traces Fails (and What to Do Instead)](https://www.distillabs.ai/blog/traces-vs-synthetic-benchmark/)

Teams deploying LLM agents often attempt to reduce costs and latency by fine-tuning smaller models on production conversation logs. However, production traces contain inherent noise — incorrect tool calls, inconsistent schemas, irrelevant data — that gets embedded as training signal. This benchmark quantifies the problem and demonstrates a solution.

We compare two approaches to training Small Language Models (SLMs) from production traces:

- **TFT Pipeline**: trace filtering + committee relabeling + synthetic data generation + finetuning
- **Direct Training**: train directly on raw/corrupted traces (no filtering, no relabeling, no synth gen)

Rather than treating traces as labeled examples, TFT uses them as *context*. A teacher LLM reads traces alongside the task description and tool schema, then generates clean synthetic conversations. A validation layer filters the output before student model training.

Both pipelines are evaluated on the same held-out test set across 5 scenarios, each testing a specific real-world failure mode.

## Dataset

Based on the [Schema-Guided Dialogue (SGD)](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue) dataset. The target task is **multi-turn tool calling** for a restaurant search and reservation service with three tools:

- `respond_to_user` -- send text messages to the user
- `FindRestaurants` -- search restaurants by cuisine, city, price range, live music, alcohol
- `ReserveRestaurant` -- reserve a table (restaurant name, city, time, date, party size)

### Test set

All scenarios share the same test set: **34 multi-turn Restaurants_1 conversations** (held out from the 367 available traces). At evaluation time, `expand_tool_calling_turns=true` expands these into **~359 per-turn evaluation pairs**, where each pair is a conversation prefix ending at an assistant tool call.

### Training traces

The remaining **327 Restaurants_1 traces** (test conversations excluded) form the canonical source. Each scenario applies different corruptions or constraints to these traces before training.

## Scenarios

### Scenario 1: Baseline

**Training data**: 327 clean Restaurants_1 traces (no corruption).

Tests the quality ceiling -- how well each pipeline performs with perfect data. TFT and Direct Training should perform similarly since there is nothing to clean up.

### Scenario 2: Noisy Labels

**Training data**: 327 Restaurants_1 traces, 50% of assistant tool calls corrupted (10% clean traces preserved for TFT seeds).

Corruption types (designed to attack tool **timing**, not just content):
- **Service tools** (`FindRestaurants`, `ReserveRestaurant`): swap_tool (33%), swap_params (33%), replace_with_respond_to_user (33%)
- **`respond_to_user`**: replace_with_service_tool (50%), replace_with_hotels_message (50%)

52% of corruptions change the tool choice itself (service <-> respond_to_user), teaching the model wrong tool timing.

### Scenario 3: Schema Drift

**Training data**: 50/50 mix of Restaurants_2 (146 traces) and Restaurants_1 (146 traces) = 292 total. **0% of training data uses correct R1 function names.**

- R2 traces: function names renamed to non-R1 names (`SearchDining`, `BookDining`, `send_user_message`)
- R1 traces: function AND parameter names randomly renamed per-trace from 6 alternatives each
- Result: 21 unique function names, 47 unique parameter names across the training set
- 10% clean R1 traces preserved

Tests adaptation to API version changes -- traces use chaotic, inconsistent tool naming.

### Scenario 4: Low Data

**Training data**: 5 clean Restaurants_1 traces (subsampled from 327 with fixed seed).

Tests extreme data scarcity. Direct Training has only ~55 per-turn examples after expansion. TFT must amplify from just 5 seed conversations via synthetic data generation.

### Scenario 5: Trace Mixing

**Training data**: 80% Hotels_1 (142 traces) + 20% Restaurants_1 (36 traces) = 178 total.

Hotels traces are corrupted to maximize confusion:
1. Function names renamed to R1 equivalents (`SearchHotel` -> `FindRestaurants`, `ReserveHotel` -> `ReserveRestaurant`)
2. Message order shuffled randomly within each conversation

The model sees R1 function names used with hotel content (room bookings, check-in dates) in random order, learning wrong associations for `FindRestaurants` and `ReserveRestaurant`.

## Results

All results use **llm-as-a-judge** as the primary metric (0-1 scale), evaluated on the shared test set (~359 expanded turn pairs).

| Scenario | TFT | Direct | Delta |
|----------|-----|--------|-------|
| S1 Baseline | 0.866 | 0.864 | +0.2pp |
| S2 Noisy Labels | **0.844** | 0.721 | **+12.3pp** |
| S3 Schema Drift | **0.844** | 0.585 | **+25.9pp** |
| S4 Low Data | **0.852** | 0.649 | **+20.3pp** |
| S5 Trace Mixing | **0.858** | 0.694 | **+16.4pp** |

TFT matches Direct Training on clean data (S1) and outperforms it on every corrupted scenario by 12-26 percentage points.

### Teacher model evaluation

For reference, teacher models evaluated on the same test set (5 seeds each):

| Teacher Model | Mean (judge) | Std |
|--------------|-------------|-----|
| GLM-5 | 0.835 | 0.006 |
| Qwen3-235B | 0.768 | 0.018 |
| MiniMax-M2 | 0.762 | 0.010 |
| DeepSeek-3.2 | 0.744 | 0.014 |

## Trained Models

All trained models are published on HuggingFace. Each is a Qwen3-1.7B model fine-tuned with LoRA (merged weights).

| Scenario | TFT Model | Direct Model |
|----------|-----------|--------------|
| S1 Baseline | [distillabs/tft-benchmark-s1-tft-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s1-tft-Qwen3-1.7B) | [distillabs/tft-benchmark-s1-direct-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s1-direct-Qwen3-1.7B) |
| S2 Noisy Labels | [distillabs/tft-benchmark-s2-tft-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s2-tft-Qwen3-1.7B) | [distillabs/tft-benchmark-s2-direct-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s2-direct-Qwen3-1.7B) |
| S3 Schema Drift | [distillabs/tft-benchmark-s3-tft-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s3-tft-Qwen3-1.7B) | [distillabs/tft-benchmark-s3-direct-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s3-direct-Qwen3-1.7B) |
| S4 Low Data | [distillabs/tft-benchmark-s4-tft-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s4-tft-Qwen3-1.7B) | [distillabs/tft-benchmark-s4-direct-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s4-direct-Qwen3-1.7B) |
| S5 Trace Mixing | [distillabs/tft-benchmark-s5-tft-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s5-tft-Qwen3-1.7B) | [distillabs/tft-benchmark-s5-direct-Qwen3-1.7B](https://huggingface.co/distillabs/tft-benchmark-s5-direct-Qwen3-1.7B) |

## Configuration

### Models

- **Student**: Qwen3-1.7B
- **Teacher / synth gen**: zai.glm-5
- **Judge**: openai.gpt-oss-120b
- **Committee** (TFT relabeling): openai.gpt-oss-120b + zai.glm-5

### Key settings

- Task: `multi-turn-tool-calling-closed-book`
- Synthetic data generation target: 2000 examples
- Generation: 1 example per LLM call (prevents length truncation)
- Mutation topics: 4 buckets matching test set turn-length distribution (9-13, 13-17, 15-19, 21-29 turns)
- Max total length: 20,000 tokens
- Relevance/coherence filtering: configurable per scenario (see individual configs)

## Directory Structure

```
distil-tft-benchmarking/
├── README.md
├── scenario-1-baseline/
│   ├── tft/                    # Trace-processing input (for run-e2e-distillation)
│   │   ├── config.yaml
│   │   ├── job_description.json
│   │   ├── traces.jsonl        # Production traces (scenario-specific, possibly corrupted)
│   │   └── test.jsonl          # Shared test set (34 multi-turn conversations)
│   ├── tft-raw-data/           # Traces + task spec for training new models
│   │   ├── traces.jsonl        # Same traces as tft/
│   │   └── task.txt            # Task description, judge instructions, mutation topics
│   └── direct/                 # Direct training input (for run-finetune)
│       ├── config.yaml
│       ├── job_description.json
│       ├── train.jsonl         # Full multi-turn conversations expanded from traces
│       └── test.jsonl          # Shared test set
├── scenario-2-noisy-labels/
│   ├── tft/
│   ├── tft-raw-data/
│   └── direct/
├── scenario-3-schema-drift/
│   ├── tft/
│   ├── tft-raw-data/
│   └── direct/
├── scenario-4-low-data/
│   ├── tft/
│   ├── tft-raw-data/
│   └── direct/
└── scenario-5-trace-mixing/
    ├── tft/
    ├── tft-raw-data/
    └── direct/
```

