# Changelog

All notable changes to CladBench are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

A change to a reference answer changes what the benchmark measures, so answer-key
corrections are listed individually rather than summarised.

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
