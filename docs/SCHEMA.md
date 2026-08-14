# CladBench v1 — Data Schema

> The universal JSONL schema for all 12 categories. One JSON object per line. Schema enforced by `schema.json`.

## Why a universal schema

Twelve categories with four different question formats (MCQ, short answer, ranking, open answer) could justify four different schemas. They don't. One schema with format-conditional fields keeps the evaluation harness simple — the same `loaders.py` reads every category, the same `evaluate.py` CLI dispatches on `format` and `grading.method`.

## File layout

```
backend/cladbench/data/
├── 01_uk_building_regs/
│   ├── public.jsonl       (55 examples)
│   └── holdout.jsonl      (15 examples; gitignored; lives in private repo)
├── 02_epc_trajectory/
│   ├── public.jsonl       (50)
│   └── holdout.jsonl      (15)
├── ...
└── 12_regulatory_cliff_edge/
    ├── public.jsonl       (50)
    └── holdout.jsonl      (15)
```

The holdout files are present at this path but their actual content is in `buildingbrain/private/cladbench-holdout/` (mirror folder, gitignored). The public repo never sees holdout content.

## Required fields

Every example must have:
- `id` — stable identifier matching pattern `cb1-{NN}-{split}-{NNNN}`
- `category` — integer 1–12
- `format` — one of `mcq`, `short_answer`, `ranking`, `open_answer`, `mcq_with_rationale`
- `split` — `public` or `holdout`
- `question` — with at minimum `question.text`
- `answer` — fields depend on `format`
- `grading` — with at minimum `grading.method`

## Format → required answer fields

| `format` | Required in `answer` | `grading.method` typically |
|---|---|---|
| `mcq` | `choice` (A–H) | `exact_match` |
| `mcq_with_rationale` | `choice` + `rationale` | `exact_match_plus_judge` |
| `short_answer` | `text` | `exact_match_plus_judge` or `exact_match` |
| `ranking` | `ranking` (array of letters) | `spearman_plus_judge` |
| `open_answer` | `text` + recommended `citation` | `llm_judge_rubric` |

## Worked examples — one per format

### Example 1: MCQ (Category 1 — UK Building Regs)

```json
{
  "id": "cb1-01-public-0001",
  "category": 1,
  "category_name": "UK Building Regulations Q&A",
  "format": "mcq",
  "split": "public",
  "question": {
    "text": "For a new dwelling in England, what is the limiting U-value for an external wall under Approved Document L1A (2021)?",
    "options": [
      "0.20 W/m²K",
      "0.26 W/m²K",
      "0.30 W/m²K",
      "0.18 W/m²K"
    ]
  },
  "answer": {
    "choice": "B",
    "citation": "Approved Document L1A 2021, Table 4.1"
  },
  "grading": {
    "method": "exact_match",
    "case_sensitive": false
  },
  "source": {
    "primary": "Approved Document L1A 2021, Table 4.1",
    "curator": "hand",
    "review_status": "locked",
    "reviewed_at": "2026-07-08"
  },
  "metadata": {
    "difficulty": "practitioner",
    "tags": ["fabric", "new-build", "domestic"]
  }
}
```

### Example 2: Short answer (Category 2 — EPC Trajectory)

```json
{
  "id": "cb1-02-public-0003",
  "category": 2,
  "category_name": "EPC Trajectory Prediction",
  "format": "short_answer",
  "split": "public",
  "question": {
    "text": "A semi-detached 1960s property currently rated EPC D (54). The owner plans to install loft insulation (to 300mm), upgrade the boiler to a 92% efficiency condensing model, and add cavity wall insulation. What is the most likely resulting EPC band?"
  },
  "answer": {
    "text": "C",
    "rationale": "Combined fabric + heating measures typically lift this housing archetype 12-18 SAP points, placing the property in the high-50s to mid-60s range, comfortably in Band C."
  },
  "grading": {
    "method": "exact_match_plus_judge",
    "rubric": [
      {
        "criterion": "Correct band identified",
        "max_points": 3,
        "description": "Exact match on band letter."
      },
      {
        "criterion": "Rationale references measure stacking",
        "max_points": 2,
        "description": "Mentions combined effect of fabric + heating intervention."
      }
    ]
  },
  "source": {
    "primary": "SAP 10.2 methodology",
    "curator": "hand",
    "review_status": "locked"
  }
}
```

### Example 3: Ranking (Category 5 — Retrofit Prioritisation)

```json
{
  "id": "cb1-05-public-0001",
  "category": 5,
  "category_name": "Retrofit Prioritisation",
  "format": "ranking",
  "split": "public",
  "question": {
    "text": "A 1930s semi-detached owner-occupier property in Bristol. Budget £25,000. Rank the candidate measures by carbon-per-pound, applying fabric-first sequencing.",
    "candidates": [
      "External wall insulation £14k, 1.8 tCO₂e/yr saved",
      "ASHP replacing gas boiler £12k, 1.2 tCO₂e/yr",
      "Double-glazed windows £6k, 0.4 tCO₂e/yr",
      "Loft insulation top-up £400, 0.3 tCO₂e/yr",
      "PV array 4kWp £6k, 0.9 tCO₂e/yr",
      "MVHR system £5k, 0.2 tCO₂e/yr"
    ]
  },
  "answer": {
    "ranking": ["d", "a", "c", "e", "b", "f"],
    "rationale": "Loft top-up has the best £/tCO₂e/yr ratio; EWI then windows complete fabric improvements first; PV then ASHP then MVHR within the active-systems group."
  },
  "grading": {
    "method": "spearman_plus_judge",
    "rubric": [
      {
        "criterion": "Spearman rank correlation with reference >= 0.7",
        "max_points": 3
      },
      {
        "criterion": "Fabric-first sequencing applied",
        "max_points": 2
      }
    ]
  }
}
```

### Example 4: Open answer with rubric (Category 7 — Thermal Comfort)

```json
{
  "id": "cb1-07-public-0001",
  "category": 7,
  "category_name": "Thermal Comfort Diagnosis",
  "format": "open_answer",
  "split": "public",
  "question": {
    "text": "Open-plan office in Cambridge, 80 occupants, complaints concentrated in the west-facing zone from 14:00-17:00 during July-August. Building has fixed external blinds set to 60° and a VAV cooling system. Diagnose the likely overheating issue under CIBSE TM52."
  },
  "answer": {
    "text": "Likely a combination of solar gain through unshaded portion of west-facing fenestration and inadequate VAV box throw in the west zone. Apply TM52 Criterion 1 (Hours of Exceedance) — modelling will likely show >3% of occupied hours above the upper acceptable limit.",
    "citation": "CIBSE TM52: The Limits of Thermal Comfort"
  },
  "grading": {
    "method": "llm_judge_rubric",
    "rubric": [
      {
        "criterion": "References TM52 methodology by name",
        "max_points": 1
      },
      {
        "criterion": "Identifies solar gain as primary cause",
        "max_points": 1
      },
      {
        "criterion": "Identifies airflow distribution as secondary cause",
        "max_points": 1
      },
      {
        "criterion": "Recommends modelling or measurement step",
        "max_points": 1
      },
      {
        "criterion": "Mentions blind angle / shading as a remedial action",
        "max_points": 1
      }
    ]
  },
  "source": {
    "primary": "CIBSE TM52 (2013)",
    "curator": "hand",
    "review_status": "locked"
  }
}
```

## Validation

Every JSONL file in `backend/cladbench/data/` must pass:

```bash
backend/.venv/Scripts/python.exe -m cladbench.validate backend/cladbench/data/01_uk_building_regs/public.jsonl
```

This validates against `schema.json` and additionally enforces:
- IDs are unique within a category and split
- `category` field matches the directory name
- `split` field matches the filename
- `grading.method` is consistent with `format`

The validator is built in Layer 3.
