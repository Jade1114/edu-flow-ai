# Edu-Flow-AI ML Pipeline

This directory contains the first LightGBM-based scheduling model pipeline for Edu-Flow-AI.

The model does not directly write the official timetable. It scores candidate scheduling decisions, while the backend orchestrates the decision flow, updates temporary schedule state, runs hard-constraint checks, and persists the final scheme after educational administration confirmation.

## Current Goal

Build the first offline training loop:

```text
Database / seed data
→ candidate scheduling samples
→ training_samples.csv
→ LightGBM training
→ schedule_ranker_v1.txt
→ local prediction demo
```

A single training sample represents:

```text
TeachingTask + candidate TimeSlot + candidate Classroom + current schedule state → score
```

## Directory Layout

```text
server/ml/
├── README.md
├── requirements.txt
├── data/
│   └── training_samples.csv        # generated, ignored by git later if needed
├── models/
│   └── schedule_ranker_v1.txt      # generated model artifact
└── scripts/
    ├── generate_training_samples.py
    ├── train_lightgbm.py
    ├── predict_demo.py
    ├── evaluate_model.py
    ├── generate_scheme_demo.py
    └── evaluate_scheme_demo.py
```

## Setup

From `server/ml`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The scripts read database settings from the same project environment variables used by Spring Boot:

- `DB_URL`
- `DB_USERNAME`
- `DB_PASSWORD`

If these are not set, the generator falls back to the local defaults in `application.yaml`.

## Scripts

### `scripts/generate_training_samples.py`

Generates candidate scheduling samples from current project data.

Input tables/entities:

- `teaching_task`
- `course`
- `teacher`
- `teacher_profile`
- `class_group`
- `classroom`
- `time_slot`
- `allocation_item` / `course_assignment` for current schedule state

Output:

```text
data/training_samples.csv
```

Example:

```bash
python scripts/generate_training_samples.py --max-rows 500
```

### `scripts/train_lightgbm.py`

Trains the first LightGBM scoring model from `training_samples.csv`.

Output:

```text
models/schedule_ranker_v1.txt
data/feature_schema.json
```

Example:

```bash
python scripts/train_lightgbm.py
```

### `scripts/predict_demo.py`

Loads the trained model and runs a local prediction demo against sample candidate rows.

Example:

```bash
python scripts/predict_demo.py --limit 12
```

### `scripts/evaluate_model.py`

Evaluates the trained model with aggregate metrics and grouped distribution checks.

Example:

```bash
python scripts/evaluate_model.py --top 10
```

### `scripts/generate_scheme_demo.py`

Generates a complete model-driven scheduling scheme demo without writing business tables.

Example:

```bash
python scripts/generate_scheme_demo.py
```

Output:

```text
data/generated_scheme_demo.csv
```

### `scripts/evaluate_scheme_demo.py`

Evaluates a generated scheme with scheme-level quality metrics.

Example:

```bash
python scripts/evaluate_scheme_demo.py
```

## First Model Boundary

The first model is a scoring model:

```text
candidate scheduling decision → score
```

It is responsible for choosing better candidate decisions during scheduling.

The backend remains responsible for:

- candidate construction
- model invocation
- temporary schedule state updates
- hard-constraint conflict checks
- scheme persistence
- final confirmation workflow

## Related Cabinet Notes

- `AI智能排课-LightGBM训练样本字段表.md`
- `AI智能排课-模型全权承担方案与说服逻辑.md`
- `AI智能排课-自训练模型学习方式与LightGBM定位.md`
