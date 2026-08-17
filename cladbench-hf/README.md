---
license: apache-2.0
language:
  - en
pretty_name: CladBench v1
size_categories:
  - n<1K
task_categories:
  - question-answering
  - multiple-choice
  - text-generation
tags:
  - benchmark
  - evaluation
  - built-environment
  - building-regulations
  - energy
  - sustainability
  - breeam
  - ifc
  - embodied-carbon
  - net-zero
  - uk
configs:
  - config_name: all
    default: true
    data_files:
      - split: test
        path: data/all/test-*.parquet
  - config_name: uk_building_regs
    data_files:
      - split: test
        path: data/uk_building_regs/test-*.parquet
  - config_name: epc_trajectory
    data_files:
      - split: test
        path: data/epc_trajectory/test-*.parquet
  - config_name: ifc_entity_reasoning
    data_files:
      - split: test
        path: data/ifc_entity_reasoning/test-*.parquet
  - config_name: bms_sensor_anomaly
    data_files:
      - split: test
        path: data/bms_sensor_anomaly/test-*.parquet
  - config_name: retrofit_prioritisation
    data_files:
      - split: test
        path: data/retrofit_prioritisation/test-*.parquet
  - config_name: breeam_credit_eligibility
    data_files:
      - split: test
        path: data/breeam_credit_eligibility/test-*.parquet
  - config_name: thermal_comfort
    data_files:
      - split: test
        path: data/thermal_comfort/test-*.parquet
  - config_name: cibse_technical
    data_files:
      - split: test
        path: data/cibse_technical/test-*.parquet
  - config_name: material_spec
    data_files:
      - split: test
        path: data/material_spec/test-*.parquet
  - config_name: energy_bill_anomaly
    data_files:
      - split: test
        path: data/energy_bill_anomaly/test-*.parquet
  - config_name: net_zero_pathway
    data_files:
      - split: test
        path: data/net_zero_pathway/test-*.parquet
  - config_name: regulatory_cliff_edge
    data_files:
      - split: test
        path: data/regulatory_cliff_edge/test-*.parquet
---

# CladBench v1

An open evaluation benchmark for large language models on the UK and EU built
environment. 536 questions across twelve categories, with every model response and score
released.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21951911.svg)](https://doi.org/10.5281/zenodo.21951911)

- **Code, results and paper:** https://github.com/cladbrain/cladbench
- **Paper:** 12 pages, in the repository and on Zenodo
- **Results as at:** 13 August 2026

---

## ⚠️ Read this before using the answer key

**The 536 reference answers are not equally well evidenced, and the dataset tells you
which is which.** Loading this and treating every answer as sound ground truth will
mislead you.

| `review_status` | n | What stands behind it |
|---|---|---|
| `primary_source_verified` | **196** | The figure was located in the source document itself, or the calculation re-derived |
| `cross_validated` / `reviewed` | **257** | Three frontier models were asked whether the answer was right, and agreed |
| `unverifiable` | **83** | Checked, and recorded as **not usable as ground truth**, with a stated reason |

**Cross-validation is the weak tier.** On Category 1 it passed all 55 questions, of which
45 subsequently required correction once the Approved Documents were actually opened —
most often citation drift, where a correct value was attributed to the wrong table. Model
agreement measures consensus among instruments that share a failure mode.

If you need a strict subset:

```python
from datasets import load_dataset

ds = load_dataset("cladbrain/cladbench", split="test")
strict = ds.filter(lambda r: r["review_status"] == "primary_source_verified")   # 196
```

But note that subset is **not** a scaled-down copy of the benchmark: 164 of the 196 come
from four categories, and Categories 4, 5 and 11 contribute none at all. What a source
document can settle is not evenly distributed. Use it as a robustness check, not as a
headline.

The 83 unverifiable questions are 48 EPC bands needing SAP modelling nobody has run, 29
CIBSE values behind a licence that was not purchased, 4 undecided policy positions, and 2
BREEAM answers found to contradict the manual. Each carries its reason in
`unverifiable_reason`.

## Regulatory currency

55 questions depend on a position that can change — not yet in force, under consultation,
or commencing after the evaluation date. They carry `policy_dependency: "live"` and an
`as_at` date.

**They are valid as at 13 August 2026 and their ground truth expires.** A model evaluated
against them later may be marked wrong for holding a *more* current position than the
reference.

```python
durable = ds.filter(lambda r: r["policy_dependency"] == "settled")   # 481
```

---

## What is in it

| Cat | Category | n | Format | Grading |
|---|---|---|---|---|
| 1 | UK Building Regulations | 55 | mcq | exact match |
| 2 | EPC Trajectory | 50 | short answer | band tolerance |
| 3 | IFC Entity Reasoning | 40 | mcq | exact match |
| 4 | BMS Sensor Anomaly | 48 | mcq | exact match |
| 5 | Retrofit Prioritisation | 30 | ranking | Spearman + judge |
| 6 | BREEAM Credit Eligibility | 54 | mcq + rationale | exact match + judge |
| 7 | Thermal Comfort | 40 | open answer | LLM-judge rubric |
| 8 | CIBSE Technical | 50 | mcq | exact match |
| 9 | Material/Product Spec | 50 | mcq + rationale | exact match + judge |
| 10 | Energy Bill Anomaly | 30 | short answer | LLM-judge rubric |
| 11 | Net Zero Pathway | 40 | open answer | LLM-judge rubric |
| 12 | Regulatory Cliff-Edge | 49 | short answer | LLM-judge rubric |

Coverage is primarily UK practice, with selected EU regulatory content.

One config per category, plus `all`:

```python
regs = load_dataset("cladbrain/cladbench", "uk_building_regs", split="test")
```

## Fields

| Field | Notes |
|---|---|
| `id`, `category`, `category_name`, `format` | |
| `question`, `context`, `options`, `candidates` | `options` for MCQ; `candidates` for ranking |
| `answer_choice`, `answer_text`, `answer_ranking`, `answer_rationale` | which one is populated depends on `format` |
| `citation` | the clause, table or article the answer rests on. Empty for Categories 2 and 5, where the reference is a modelled band or a recommended ordering rather than a printed value |
| `grading_method`, `rubric`, `case_sensitive` | |
| `review_status`, `unverifiable_reason`, `verified_at`, `curated_at`, `correction` | **read these** |
| `source_primary`, `curator` | |
| `policy_dependency`, `policy_targets`, `as_at` | |
| `difficulty`, `tags` | difficulty is a curation-time tag, not item-response calibrated |

`curated_at` is a provenance timestamp recording when the record was written by the
curation tooling. **It is not a review date, and no field in this dataset asserts human
sign-off** — because none has happened.

---

## Baseline results

Seven models. All rubric-graded answers marked by **DeepSeek Chat** and **Grok 4** —
neither of which is evaluated here. 95% confidence intervals from 10,000 bootstrap
resamples.

| Model | Overall | 95% CI |
|---|---|---|
| Claude Opus 4.7 | 0.888 | [0.867, 0.908] |
| Claude Opus 4.8 | 0.869 | [0.847, 0.890] |
| Gemini 2.5 Pro | 0.831 | [0.808, 0.854] |
| GPT-5 | 0.823 | [0.795, 0.848] |
| GPT-4o | 0.691 | [0.660, 0.722] |
| Llama 3.3 70B Instruct Turbo (FP8) | 0.655 | [0.622, 0.688] |
| Qwen 2.5 7B Instruct Turbo (FP8) | 0.540 | [0.504, 0.575] |

**Gemini 2.5 Pro and GPT-5 are not separated by this benchmark.** Their difference is
+0.009 with a 95% interval of [−0.022, +0.039]. Please describe them as comparable rather
than ranking them.

**The overall number is the least interesting result here.** Every model scores at least
0.75 on BMS anomaly classification; on regulatory cliff-edge questions the same seven
span 0.901 to 0.126 — a wider range than the 0.348 separating the best model from the
worst overall. Which category a task falls in matters more than which model runs it.

All 3,752 per-question model responses and scores are released in the GitHub repository,
so the figures can be recomputed without access to any evaluated model.

## Limitations

Please read these before quoting a number.

1. **The questions are model-generated.** All 536 were written by Claude Opus 4.7, then
   checked against the primary sources they name. Verification supports the answer key; it
   does not change the fact that the question *phrasing* reflects one generator. The
   `curator` value `hand` denotes questions the model wrote during seeding, **not** human
   authorship.
2. **No practising professional has read any question.** Human review by domain experts is
   the priority for v2.
3. **Two categories are provisionally scored.** Category 2 has 2 of 50 answers verified
   against a primary source; Category 8 has 9 of 50.
4. **An option-length cue is present.** The correct option is strictly the longest in 37%
   of multiple-choice questions against a chance rate near 25% — and in **69% of Category
   6**. Part of the Category 6 scores may reflect that cue rather than BREEAM knowledge.
5. **Claude Opus 4.7 wrote the questions and tops the table.** Neutral judging removes the
   marking side of this. The generation side remains.
6. **Two results describe FP8 endpoints** at one provider, not the models at full
   precision.
7. **Decoding is not uniform.** GPT-5 and the Claude Opus 4.x family do not accept a pinned
   temperature, so three of seven models and every judge verdict are sampled rather than
   greedy. Repeat-run variance is measured and reported in the paper.
8. **Per-category n is 30–55**, so single-category comparisons are indicative.
9. **Text only.** Drawings, BIM models and PDF reports are central to this profession and
   are not tested.

## Contamination

These questions have been public since 15 August 2026. Any model trained on a corpus
including GitHub after that date may have seen them.

A **120-question private holdout** exists in four of the same categories, built from
primary sources, never published and never sent to a model. It exists so a contamination
question can be settled by running it rather than argued about.

## Source material and licensing

Dataset and code: **Apache 2.0**.

Questions cite Approved Documents (Crown copyright, Open Government Licence), BREEAM UK
New Construction 2018 (SD5078, BRE copyright), the IFC4 EXPRESS schema (buildingSMART) and
CIBSE guidance. They are original text referencing those sources, not reproductions of
them: across all 536 questions the longest passage shared with any source document is 22
words, and most matches at that length are publication titles.

## Citing

```bibtex
@misc{selvan2026cladbench,
  author       = {Selvan, Ramadoss Tamil},
  title        = {CladBench v1: A Twelve-Category Benchmark for Large Language
                  Models on the UK and EU Built Environment},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.21951911},
  url          = {https://github.com/cladbrain/cladbench}
}
```

## Corrections

If you find an error in the answer key, please open an issue on
[GitHub](https://github.com/cladbrain/cladbench/issues) with the question `id`, what the
reference says, and what the source actually says with its clause reference. The
verification history in the paper exists because errors were found and fixed; that process
does not stop at publication.
