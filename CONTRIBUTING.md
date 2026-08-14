# Contributing to CladBench

The most useful contribution is a correction.

## Reporting an error in the answer key

This is the contribution we most want. The benchmark's verification history exists because
errors were found and fixed; that process does not stop at publication.

Open an issue with:

- the question `id` (e.g. `cb1-06-public-0054`)
- what the reference answer says
- what the source actually says, with the document, edition and clause or paragraph

A citation to a primary source is what makes a report actionable. "This looks wrong" is
hard to act on; "SD5078 Pol 01 awards credits on DELC thresholds, not a GWP ceiling" is a
fix.

Please check `source.review_status` first. If it is `unverifiable`, we already know that
answer is not usable as ground truth and the reason is recorded in the data.

## Adding results for another model

We are glad to link third-party evaluations. To make them comparable, please:

1. Use the released harness (`python -m cladbench evaluate`) rather than a reimplementation.
2. Report the dataset hash from the run manifest, so it is clear which version was used.
3. State the exact endpoint, including quantisation. `Llama 3.3 70B` and
   `Llama 3.3 70B at FP8 on a serverless endpoint` are different measurements.
4. Say which judge marked the rubric categories. A different judge is a different
   experiment, not a different score.

Open an issue with the results and a link to the raw outputs.

## Proposing new questions

Human-authored questions from practising professionals are the priority for v2. If you
work in UK building control, energy assessment, retrofit, BREEAM assessment or building
services, we would rather have twenty questions from you than two hundred generated ones.

A usable question needs:

- a scenario a practitioner could actually meet
- one defensible answer
- a citation to a specific clause, table or article
- three distractors that are plausible and wrong, and **not** shorter than the correct
  option (see the option-length limitation in the README)

## Development

```bash
pip install -e ".[all]"
python -m cladbench validate src/cladbench/data/01_uk_building_regs/public.jsonl
python -m cladbench score --input results/responses/full_opus47.jsonl
```

Every question must validate against `src/cladbench/schema.json`.

## What we will not merge

- Changes to a published reference answer without a primary-source citation.
- Removal of a question because a model scores badly on it.
- Edits to `source.reviewed_at`, which records human review by the maintainer.

## Conduct

Be straightforward and assume good faith. Disagreements about a regulation are settled by
reading the regulation.
