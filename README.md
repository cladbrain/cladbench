# CladBench v1

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21951911.svg)](https://doi.org/10.5281/zenodo.21951911)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

An open evaluation benchmark for large language models on the UK and EU built environment.
536 questions across twelve categories, with every model response and score released.

📄 **[Read the paper](paper/cladbench_v1.pdf)** — 12 pages, PDF

*Results as at 13 August 2026.*

---

## What this is

Surveyors, energy assessors, retrofit coordinators and sustainability consultants are
using language models for real work: estimating an EPC band after a retrofit, checking
whether a BREEAM credit is achievable, working out what a MEES deadline requires of a
particular building. General benchmarks do not measure whether a model is any good at
that. CladBench does.

Coverage is primarily UK practice, with selected EU regulatory content.

| # | Category | n | Format | Grading |
|---|---|---|---|---|
| 1 | UK Building Regulations | 55 | MCQ | exact match |
| 2 | EPC Trajectory Prediction | 50 | short answer | band tolerance |
| 3 | IFC Entity Reasoning | 40 | MCQ | exact match |
| 4 | BMS Sensor Anomaly Classification | 48 | MCQ | exact match |
| 5 | Retrofit Prioritisation | 30 | ranking | Spearman + judge |
| 6 | BREEAM Credit Eligibility | 54 | MCQ + rationale | exact match + judge |
| 7 | Thermal Comfort Diagnosis | 40 | open answer | LLM-judge rubric |
| 8 | CIBSE Technical Q&A | 50 | MCQ | exact match |
| 9 | Material and Product Specification | 50 | MCQ + rationale | exact match + judge |
| 10 | Energy Bill Anomaly Detection | 30 | short answer | LLM-judge rubric |
| 11 | Net Zero Pathway Reasoning | 40 | open answer | LLM-judge rubric |
| 12 | Regulatory Cliff-Edge Reasoning | 49 | short answer | LLM-judge rubric |

## Results

Seven models, all rubric-graded answers marked by two judges that are not themselves
evaluated (DeepSeek Chat and Grok 4). 95% confidence intervals from 10,000 bootstrap
resamples.

| Model | Score | 95% CI |
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

The overall number is the least interesting result here. Every model scores at least 0.75
on BMS anomaly classification; on regulatory cliff-edge questions the same seven span
0.901 to 0.126. Which category a task falls in matters more than which model runs it.

## Read the answer key before you use it

Reference answers are not uniform in strength, and the dataset says which is which:

| `source.review_status` | n | What it means |
|---|---|---|
| `primary_source_verified` | 196 | The figure was found in the source document, or the calculation re-derived |
| `cross_validated` / `reviewed` | 257 | Three frontier models agreed the answer was right |
| `unverifiable` | 83 | Checked, and recorded as not usable as ground truth, with a reason |

Cross-validation is the weaker warrant. In Category 1 it passed all 55 questions, 45 of
which needed correction once the Approved Documents were actually opened. Weight it
accordingly, and prefer `primary_source_verified` if you need a strict subset — but note
that subset is concentrated in four categories and is not a balanced sample of the twelve.

Fifty-five questions depend on regulatory positions that can move (`metadata.policy_dependency: live`).
They are valid as at 13 August 2026. Re-verify before reusing them.

## Install

```bash
git clone https://github.com/cladbrain/cladbench
cd cladbench
pip install -e .
```

## Reproduce the published scores without an API key

Every model response is released, so you do not need access to any evaluated model to
check the numbers:

```bash
python -m cladbench score --input results/responses/full_opus47.jsonl
```

This recomputes 243 of the 536 rows — every row graded by a deterministic method — and
reproduces all 243 stored scores exactly. The remaining 293 are rubric-graded; add
`--judge anthropic` (and an `ANTHROPIC_API_KEY`) to re-judge those too.

## Evaluate your own model

```bash
echo "ANTHROPIC_API_KEY=<your-key>" >> .env      # whichever providers you need
python -m cladbench evaluate --model anthropic:claude-opus-4-7 \
       --split public --output my_run.jsonl
```

Model specs take the form `provider:model`, with providers `anthropic`, `openai`,
`google`, `together` and `hf`. Every run writes a manifest recording the dataset hash,
harness version and token usage.

## Known limitations

Please read these before quoting a number.

1. **The questions were model-generated**, then checked against the primary sources they
   name. The answer key is what the verification supports; the phrasing reflects a single
   generator.
2. **Two categories are provisionally scored.** Category 2 has 2 of 50 answers verified
   against a primary source, Category 8 has 9 of 50. CIBSE material is licensed and no
   lawful copy was obtained, so 29 of those answers have not been checked against a source.
3. **An option-length cue is present.** The correct option is the longest in 37% of
   multiple-choice questions against a chance rate near 25%, and in 69% of Category 6.
   Part of the Category 6 result may be that cue rather than BREEAM knowledge.
4. **Two open-weights results describe FP8 endpoints** at one provider, not the models at
   full precision.
5. **Decoding is not uniform.** GPT-5 and the Claude Opus 4.x family do not accept a
   pinned temperature, so three of seven models and every judge verdict are sampled rather
   than greedy. Repeat-run variance is measured and reported in the paper.
6. **Text only.** Drawings, BIM models and PDF reports are not tested.
7. **Per-category n is 30–55**, so single-category comparisons are indicative.

## What is not in this repository

A 120-question private holdout exists and is deliberately not published. It has never been
sent to any model, and exists so that a contamination question about the public set can be
settled by running it rather than argued about. Its generators are withheld too, because a
seeded generator is the questions.

## Repository layout

```
src/cladbench/        the package: CLI, scorers, adapters, schema.json
src/cladbench/data/   the 536 questions, one JSONL per category
results/responses/    every model response and score, one file per model
results/judges/       the two neutral judges' marks, per answer
results/manifests/    dataset hash, harness version and token usage per run
docs/                 schema reference, category specifications, ledger, result tables
paper/                the paper as PDF, Markdown and LaTeX
```

## Citing

Selvan, R. T. (2026). *CladBench v1: A Twelve-Category Benchmark for Large Language Models
on the UK and EU Built Environment.* https://doi.org/10.5281/zenodo.21951911

That DOI always resolves to the latest version. To cite this specific release, use
`10.5281/zenodo.21951912`. Machine-readable metadata is in `CITATION.cff`.

## Licence and source material

Code and dataset: Apache 2.0.

Questions cite Approved Documents (Crown copyright, Open Government Licence), BREEAM UK
New Construction 2018 (SD5078, BRE copyright), the IFC4 EXPRESS schema (buildingSMART) and
CIBSE guidance. They are original text referencing those sources, not reproductions of
them: across all 536 questions the longest passage shared with any source document is 22
words, and most of the matches at that length are publication titles.

## Corrections

If you find an error in the answer key, please open an issue. The verification history in
the paper exists because errors were found and fixed; that process does not stop at
publication.
