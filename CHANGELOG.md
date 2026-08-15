# Changelog

All notable changes to CladBench are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A change to a reference answer changes what the benchmark measures, so answer-key
corrections are listed individually rather than summarised.

## [1.0.3] — 2026-08-15

### Fixed

- Four tables in the compiled paper ran off the right edge, losing content: the
  composition table, the evidential-status warrants table, the results-by-evidential-status
  table, and the released-artefacts table. Every column was set to a non-wrapping type and
  the scaling rule only applied at six columns or more, which none of the four reached.
  Tables with a prose column now wrap it; tables that are numeric but too wide are scaled.
  The PDF is replaced.

No question text, reference answer or score changed.

## [1.0.2] — 2026-08-15

### Added

- `paper/cladbench_v1.pdf` — the compiled paper. Previous releases shipped only Markdown
  and LaTeX, so reading the paper meant compiling it. 12 pages.
- DOI. The concept DOI `10.5281/zenodo.21951911` resolves to the latest version;
  `10.5281/zenodo.21951912` pins v1.0.1. Recorded in `CITATION.cff` and the README.

## [1.0.1] — 2026-08-15

Provenance and typesetting corrections. No question text, reference answer or score
changed, so all published results stand unaltered.

### Changed

- `source.reviewed_at` renamed to `source.curated_at`. The field was documented as the
  date the maintainer last reviewed the example. It did not record that: 516 of the 536
  questions carried the identical date across all twelve categories, which is a curation
  script writing a timestamp, not a person reading 516 questions in a day. The dates are
  retained under a name that describes them.
- `SCHEMA.md` now documents the provenance fields, and states plainly that no question in
  v1 has been read and approved by a domain professional, and that no field asserts
  otherwise.
- `LICENSE` replaced with the full Apache 2.0 text. It had been a fifteen-line summary
  pointing at apache.org, which GitHub could not identify, so the repository reported no
  licence.
- `paper/cladbench_v1.tex`: the Abstract was typesetting as numbered section 1, shifting
  every later section by one and misdirecting all fourteen "Section 5.4"-style
  cross-references in the prose. Abstract and References are now unnumbered and appendices
  are lettered.

## [1.0.0] — 2026-08-14

First public release. 536 questions across twelve categories, seven evaluated models,
3,752 per-question outputs.

### Dataset

- 536 public questions across 12 categories, five task formats, five grading methods.
- Reference answers labelled by evidential status: 196 `primary_source_verified`,
  257 `cross_validated` / `reviewed`, 83 `unverifiable`.
- 55 questions tagged `policy_dependency: live`, valid as at 2026-08-13, with a stated
  as-at date. The other 481 are `settled`.
- Four questions removed during curation (540 → 536): two Category 4 items describing
  mechanical actuator failures outside the sensor-anomaly taxonomy, one internally
  contradictory Category 6 Wst 02 item, and one Category 12 item pairing a VRF system
  with an incompatible refrigerant.

### Answer-key corrections

- Category 1: 45 of 55 questions corrected against the Approved Documents — wrong tables,
  wrong paragraph numbers, and in a minority of cases wrong values.
- Category 6: 15 questions corrected, including a Wat 01 item whose stated four-credit
  threshold was 40% where the manual specifies 50%.
- Categories 2, 7, 8, 10, 11, 12: 42 further corrections.
- `cb1-06-public-0054` and `cb1-06-public-0002` marked `unverifiable`: their reference
  answers contradict SD5078 (a GWP ≤ 2500 threshold that Pol 01 does not contain, and a
  Part L 2021 baseline where the manual specifies Part L2A 2013). Neither is repairable
  by re-keying, and both are scheduled for rewrite.

### Evaluation

- Seven models evaluated. All rubric-graded answers marked by two judges that do not
  compete in the benchmark (DeepSeek Chat, Grok 4); the incumbent Claude marks are
  retained for comparison.
- Confidence intervals by percentile bootstrap, 10,000 resamples, seed 42.
- Repeat-run variance measured rather than assumed: 30 judge-graded items re-marked three
  times, and Category 3 re-run end to end three times.

### Known limitations

Recorded in full in the README and the paper. In brief: the questions are model-generated
and verified rather than human-authored; Categories 2 and 8 are largely unverified against
primary sources; an option-length cue is present, strongest in Category 6; two results
describe FP8 endpoints; decoding cannot be pinned for three of the seven models.

### Planned for 1.1 / 2.0

- Human-authored questions from practising UK professionals.
- Distractor rebalancing to remove the option-length cue.
- SAP modelling to settle the Category 2 references.
- A category-balanced primary-source-verified subset.
- Multimodal categories, and deeper EU coverage.
