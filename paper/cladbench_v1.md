# CladBench v1: A Twelve-Category Benchmark for Large Language Models on the UK and EU Built Environment

**Ramadoss Tamil Selvan**
Independent researcher, London, United Kingdom
Correspondence: cladbrain@gmail.com

*Results as at 13 August 2026.*

---

## Abstract

CladBench v1 is an open benchmark of 536 questions across twelve categories of UK and EU built-environment practice: Building Regulations, EPC trajectory estimation, IFC entity reasoning, BMS sensor anomaly classification, retrofit prioritisation, BREEAM credit eligibility, thermal comfort diagnosis, CIBSE technical guidance, material and embodied-carbon specification, energy-bill anomaly detection, net-zero pathway reasoning, and regulatory cliff-edge reasoning. Five task formats and five grading methods are used. Seven contemporary models were evaluated: Claude Opus 4.7 and 4.8, GPT-5, Gemini 2.5 Pro, GPT-4o, and two open-weights models served at FP8, Llama 3.3 70B Instruct Turbo and Qwen 2.5 7B Instruct Turbo. All rubric-graded answers were marked by two judges that are not themselves evaluated here.

**The informative variation is across categories, not across models.** Every model scores at least 0.75 on BMS sensor anomaly classification, while on regulatory cliff-edge questions the seven span 0.901 to 0.126 — a range wider than the 0.348 that separates the best model from the worst overall. Two of the four leading models are not statistically separated from each other.

Scores across the full 536 questions range from 0.888 to 0.540. Reference answers are additionally reported by evidential status: 196 verified against the source document itself, 257 resting on agreement between three frontier models, and 83 flagged as unusable as ground truth with a stated reason. Fifty-five questions depend on regulatory positions that can change; these are tagged so the expiring part of the benchmark is identifiable, and we show the tag marks a maintenance property rather than a separate model capability. Coverage is primarily UK practice with selected EU regulatory content. The dataset, evaluation code, and all 3,752 per-question outputs are released.

**Keywords:** evaluation benchmark, large language models, built environment, building regulations, energy performance, retrofit, BIM, IFC, BREEAM, CIBSE, net zero, MEES, embodied carbon

---

## 1. Introduction

Large language models are now used routinely by surveyors, architects, energy assessors, retrofit coordinators and sustainability consultants. The tasks are specific: estimating an EPC band after a retrofit, checking whether a BREEAM credit is achievable, working out what a MEES deadline requires of a particular building.

No open benchmark measures whether models are competent at that work. General suites such as MMLU, BIG-Bench and GPQA reward broad scientific and commonsense knowledge. They do not test UK regulatory granularity, citation discipline, or awareness of policy that changes from one year to the next. Domain benchmarks exist for medicine, law and code. We are not aware of an equivalent for the built environment.

CladBench v1 is a narrow benchmark built to fill that gap. It covers UK practice primarily, with selected EU regulatory content, is graded against citable sources, and is designed so that categories differ in kind rather than only in difficulty. This paper reports its design and the baseline results for seven models. It does not propose a model, and nothing in it depends on one.

---

## 2. Related Work

HELM (Liang et al., 2022) and BIG-Bench (Srivastava et al., 2022) established the methodological norms for multi-task LLM evaluation, and domain-specific benchmarks have followed in medicine (MedQA, MedMCQA), law (LegalBench), code (HumanEval, MBPP) and science (GPQA).

Built-environment machine learning datasets exist but target numerical prediction: energy disaggregation (REDD, UK-DALE), building energy benchmarking (CBECS), BIM object classification. None test natural-language reasoning over regulations or professional practice. Climate benchmarks such as ClimateBert (Webersinke et al., 2022) address policy discourse rather than the regulatory operating layer that practitioners work in.

For open-ended categories we use LLM judges, following Zheng et al. (2023), with one modification described in Section 4.3: the judges are drawn from outside the set of evaluated models.

---

## 3. Benchmark Design

### 3.1 Categories

| # | Category | Format | n | Grading |
|---|---|---|---|---|
| 1 | UK Building Regulations Q&A | MCQ | 55 | exact match |
| 2 | EPC Trajectory Prediction | short answer | 50 | band tolerance |
| 3 | IFC Entity Reasoning | MCQ | 40 | exact match |
| 4 | BMS Sensor Anomaly Classification | MCQ | 48 | exact match |
| 5 | Retrofit Prioritisation | ranking | 30 | Spearman + judge |
| 6 | BREEAM Credit Eligibility | MCQ + rationale | 54 | exact match + judge |
| 7 | Thermal Comfort Diagnosis | open answer | 40 | LLM-judge rubric |
| 8 | CIBSE Technical Q&A | MCQ | 50 | exact match |
| 9 | Material and Product Specification | MCQ + rationale | 50 | exact match + judge |
| 10 | Energy Bill Anomaly Detection | short answer | 30 | LLM-judge rubric |
| 11 | Net Zero Pathway Reasoning | open answer | 40 | LLM-judge rubric |
| 12 | Regulatory Cliff-Edge Reasoning | short answer | 49 | LLM-judge rubric |
| | **Total** | | **536** | |

The categories are not twelve samples of one skill. Categories 1, 3, 4, 6 and 8 test recall of documented standards and schemes. Categories 5, 7, 9, 10 and 11 test multi-step reasoning about a described building, including the arithmetic in embodied-carbon specification. Categories 2 and 12 test whether a model knows what the current regulatory position actually is, which is a different thing from knowing the regulations.

### 3.2 Composition

| Dimension | Distribution |
|---|---|
| Task format | mcq 193, short_answer 129, mcq_with_rationale 104, open_answer 80, ranking 30 |
| Grading method | exact_match 193, llm_judge_rubric 159, exact_match_plus_judge 104, band_tolerance 50, spearman_plus_judge 30 |
| Difficulty tag | practitioner 413, expert 97, foundation 26 |
| Question length | median 317 characters, range 58–812 |

### 3.3 Grading methods

**`exact_match`** — case-insensitive match on the canonical answer.

**`exact_match_plus_judge`** — 60% exact match on the headline answer, 40% judge score on the rationale.

**`llm_judge_rubric`** — points per rubric criterion, normalised to the rubric maximum.

**`spearman_plus_judge`** — 70% Spearman rank correlation on the candidate ordering, 30% judge score on the reasoning.

**`band_tolerance`** — used for EPC band prediction. An exact match scores 1.0, an adjacent band 0.5, two or more bands away 0.0. The predicted band after a retrofit depends on assumptions and modelling choices, so the design treats an adjacent band as a partially defensible answer and a two-band error as a wrong one. Section 5.4 shows what this rule costs.

### 3.4 Storage

Each question is a JSONL record validated against a published JSON Schema at load time, carrying the question, options, reference answer, citation, grading method and rubric, difficulty tag, source, and review status.

In the ten categories whose answers are stated in a document, each reference answer carries a specific locator: an Approved Document paragraph, a BREEAM issue, a CIBSE section, an EPBD article or a named UK instrument. Categories 2 and 5 carry a named source but no clause-level citation, because the reference is a modelled EPC band and a recommended ordering respectively, neither of which is a value printed in a standard.

---

## 4. Experimental Setup

### 4.1 Answer key

Reference answers carry one of three evidential statuses, and we report them separately because they are not equivalent.

| Status | n | Warrant |
|---|---|---|
| `primary_source_verified` | **196** | The figure was located in the source document itself, or the calculation re-derived |
| `cross_validated` / `reviewed` | **257** | Three frontier models were asked whether the answer was right, and agreed |
| `unverifiable` | **83** | Checked, and recorded as not usable as ground truth, with a stated reason |

**Cross-validation is the weaker warrant and should be read as such.** On Category 1 it passed all 55 questions, of which 45 subsequently required correction when the Approved Documents were opened — most often citation drift, where a correct value was attributed to the wrong table. Model agreement measures consensus among instruments that share a failure mode; it is not the same as reading the document.

Primary-source verification used the sources directly: Approved Document pages, the IFC4 EXPRESS schema, BREEAM SD5078, and for the embodied-carbon category, re-derivation of the stated arithmetic (99 equations recomputed, no errors found). Coverage is uneven by category and is limited by what a source can settle. The EXPRESS schema declares entity structure but carries no definitions, so it settles 14 of 40 Category 3 questions and cannot adjudicate the rest, where all four options name real entities and the question turns on meaning. Categories 5, 7, 10 and 11 pose scenario judgements with no single citable figure and remain cross-validated in full.

The 83 unverifiable questions fall into four groups. **48 EPC bands** (Category 2) whose reference requires SAP modelling that has not been run. **29 CIBSE values** (Category 8), for which no lawful copy of the Guide was obtained and unauthorised copies circulating online were deliberately not used — these answers were generated from the model's own knowledge of CIBSE material and have not been checked against the source. **4 policy questions** (Category 12) turning on a position not yet decided.

And **2 BREEAM questions** (Category 6) whose reference answers the primary-source pass found to contradict SD5078: one conditions Pol 01 eligibility on a refrigerant GWP threshold of 2500 that the manual does not contain — Pol 01 awards credits on direct effect life cycle emissions or on GWP ≤ 10 — and one asserts that Ene 01 is assessed against Part L 2021, where the manual specifies Part L2A, 2013 edition with 2016 amendments. Neither is repairable by re-keying, because in the first case no option states the manual's position. They are retained in the scored set so that the released results remain complete and reproducible, flagged so they cannot be read as ground truth, and listed for rewrite in v2.

Section 5.4 reports scores by verification status.

### 4.2 Harness

Evaluation runs through the `cladbench` package (harness 2.0.0) against dataset hash `e4695eb32bcbab13`, with per-model output ceilings. A response terminated by a token limit is recorded as an error rather than scored as a wrong answer, and provider errors are classified terminal or transient rather than written as zeros. Every run emits a manifest recording dataset hash, harness version, model identifiers and token usage.

**Decoding is not uniform across providers, and cannot be made so.** Gemini 2.5 Pro, GPT-4o and the two Together AI endpoints accept `temperature=0.0` and were run greedily. GPT-5 rejects any temperature other than 1, and the Claude Opus 4.x family has deprecated the parameter and returns an error when it is set. Three of the seven evaluated models, and every judge verdict, are therefore sampled rather than greedy. Run-to-run variance is measured and reported in Section 4.4 rather than assumed away.

### 4.3 Judging

Rubric-graded answers were marked by **DeepSeek Chat** and **Grok 4**, neither of which is evaluated in this benchmark. Each judge scored every one of the 2,051 rubric-graded answers independently, from the same rubric text, without sight of the other's verdict. The reported score is the unweighted mean of the two. There was no adjudication step and no calibration round: where the judges disagree, the disagreement is carried into the score rather than resolved. Mean spread between judges was 0.109 and the median 0.000; they differed by 0.5 or more on 65 answers (3.2%). Both judges produce the same model ranking, and so does a third marking pass by Claude Opus 4.7, retained in the release for comparison. Substituting the neutral panel for that Claude pass moves Anthropic models 0.008 less than the other models, which is smaller than any confidence interval reported here.

### 4.4 Repeat runs

Because sampling cannot be switched off for part of the panel, repeat runs were measured directly. Thirty judge-graded items re-marked three times returned identical scores on 24 of 30, with run means of 0.933, 0.956 and 0.933. Category 3 re-run three times end to end returned identical scores on 39 of 40 items, with run means of 1.000, 0.975 and 1.000.

Residual variance is therefore roughly one to two points at category level, and category-level differences below that should not be interpreted. The overall scores in Section 5.1 are means over 536 questions, where this variance largely averages out; the per-category figures in Section 5.3 carry it in full.

### 4.5 Statistics

Confidence intervals are percentile bootstrap over questions, 10,000 resamples, seed 42. Overall scores are n-weighted means across categories. Pairwise model comparisons use a paired bootstrap on the same questions.

### 4.6 Models

Throughout, "frontier proprietary" labels the four highest-scoring proprietary models in *this* evaluation. It is not a claim about the global state of the art.

| Model | Access | Class |
|---|---|---|
| Claude Opus 4.7 | Anthropic API | frontier proprietary |
| Claude Opus 4.8 | Anthropic API | frontier proprietary |
| GPT-5 | OpenAI API | frontier proprietary |
| Gemini 2.5 Pro | Google API | frontier proprietary |
| GPT-4o | OpenAI API | previous-generation proprietary |
| Llama 3.3 70B Instruct Turbo | Together AI, FP8 | open weights |
| Qwen 2.5 7B Instruct Turbo | Together AI, FP8 | open weights |

The two open-weights models were served at FP8 quantisation by a third-party provider. Their results describe those endpoints, not the models at full precision.

---

## 5. Results

### 5.1 Overall

| Rank | Model | Score | 95% CI |
|---|---|---|---|
| 1 | Claude Opus 4.7 | **0.888** | [0.867, 0.908] |
| 2 | Claude Opus 4.8 | **0.869** | [0.847, 0.890] |
| 3 | Gemini 2.5 Pro | **0.831** | [0.808, 0.854] |
| 4 | GPT-5 | **0.823** | [0.795, 0.848] |
| 5 | GPT-4o | **0.691** | [0.660, 0.722] |
| 6 | Llama 3.3 70B Instruct Turbo (FP8) | **0.655** | [0.622, 0.688] |
| 7 | Qwen 2.5 7B Instruct Turbo (FP8) | **0.540** | [0.504, 0.575] |

Four frontier models occupy a band of 0.065. The GPT-4o and Llama 3.3 70B intervals overlap; every other adjacent pair below the frontier is separated on the marginal intervals as well as the paired test in Section 5.2.

### 5.2 Which models are actually distinguishable

| Comparison | Difference | 95% CI | Separated? |
|---|---|---|---|
| Opus 4.7 − Opus 4.8 | +0.019 | [+0.000, +0.038] | marginal |
| Opus 4.8 − Gemini 2.5 Pro | +0.038 | [+0.010, +0.065] | yes |
| Gemini 2.5 Pro − GPT-5 | +0.009 | [−0.022, +0.039] | **no** |
| GPT-5 − GPT-4o | +0.131 | [+0.100, +0.161] | yes |
| GPT-4o − Llama 3.3 70B | +0.036 | [+0.006, +0.067] | yes |
| Llama 3.3 70B − Qwen 2.5 7B | +0.115 | [+0.084, +0.147] | yes |

Gemini 2.5 Pro and GPT-5 are not separated by this benchmark and should be described as comparable rather than ranked. The interval on the two Opus versions touches zero at its lower bound; the ordering is real but the margin is thin.

### 5.3 Per category

| Cat | Opus 4.7 | Opus 4.8 | Gemini 2.5 | GPT-5 | GPT-4o | Llama 70B | Qwen 7B |
|---|---|---|---|---|---|---|---|
| 01 UK Building Regs | 0.855 | 0.818 | 0.927 | 0.691 | 0.709 | 0.636 | 0.527 |
| 02 EPC Trajectory † | 0.830 | 0.760 | 0.860 | 0.890 | 0.850 | 0.860 | 0.510 |
| 03 IFC Entity Reasoning | 0.925 | 0.875 | 0.875 | 0.800 | 0.800 | 0.700 | 0.725 |
| 04 BMS Sensor Anomaly | 0.958 | 0.958 | 0.958 | 0.979 | 0.938 | 0.917 | 0.750 |
| 05 Retrofit Prioritisation | 0.755 | 0.853 | 0.848 | 0.890 | 0.910 | 0.910 | 0.646 |
| 06 BREEAM Credit Eligibility ‡ | 0.887 | 0.869 | 0.833 | 0.811 | 0.807 | 0.827 | 0.775 |
| 07 Thermal Comfort | 0.943 | 0.927 | 0.835 | 0.945 | 0.630 | 0.665 | 0.550 |
| 08 CIBSE Technical Q&A † | 0.900 | 0.940 | 0.920 | 0.820 | 0.840 | 0.680 | 0.680 |
| 09 Material/Product Spec | 0.794 | 0.802 | 0.695 | 0.628 | 0.652 | 0.580 | 0.523 |
| 10 Energy Bill Anomaly | 0.956 | 0.917 | 0.756 | 0.850 | 0.400 | 0.461 | 0.372 |
| 11 Net Zero Pathway | 0.970 | 0.905 | 0.745 | 0.963 | 0.265 | 0.283 | 0.227 |
| 12 Regulatory Cliff-Edge | 0.901 | 0.844 | 0.684 | 0.707 | 0.384 | 0.296 | 0.126 |
| **Overall** | **0.888** | **0.869** | **0.831** | **0.823** | **0.691** | **0.655** | **0.540** |

† Provisional. Category 2 has 2 of 50 reference answers verified against a primary source and 48 recorded as unverifiable; Category 8 has 9 of 50 verified and 29 unverifiable (Section 4.1). These two category scores rest on the weakest evidence in the benchmark.

‡ Category 6 is affected by an option-length cue: its correct option is the longest in 37 of 54 questions (69%), against a chance rate near 25% (Section 7). Part of the Category 6 column may reflect that cue rather than BREEAM knowledge, and the category should be read as provisional until distractor lengths are rebalanced in v2. Two of its 54 questions also carry reference answers that contradict SD5078 and are flagged unverifiable (Section 4.1).

For the four lower-scoring models, the spread across categories exceeds the 0.348 spread between models overall: 0.673 for GPT-4o, 0.649 for Qwen 2.5 7B, 0.634 for Llama 3.3 70B and 0.351 for GPT-5. GPT-4o scores 0.938 on BMS anomaly classification and 0.265 on net-zero pathway reasoning; Qwen 2.5 7B scores 0.775 on BREEAM and 0.126 on regulatory questions. The three strongest models are flatter, ranging 0.198 to 0.274 across categories.

Which category a task falls in therefore matters more than which model runs it, but only below the frontier. At the top of the table the choice of model and the choice of task matter about equally.

### 5.4 Performance by answer-key evidential status

| Model | All (n=536) | Primary-source (n=196) | Cross-validated (n=257) | Unverifiable (n=83) |
|---|---|---|---|---|
| Claude Opus 4.7 | 0.888 | **0.863** | 0.924 | 0.839 |
| Claude Opus 4.8 | 0.869 | **0.835** | 0.912 | 0.815 |
| Gemini 2.5 Pro | 0.831 | **0.801** | 0.850 | 0.843 |
| GPT-5 | 0.823 | **0.727** | 0.886 | 0.852 |
| GPT-4o | 0.691 | **0.627** | 0.689 | 0.853 |
| Llama 3.3 70B (FP8) | 0.655 | **0.565** | 0.696 | 0.741 |
| Qwen 2.5 7B (FP8) | 0.540 | **0.490** | 0.572 | 0.558 |

**This table is a robustness diagnostic, not an alternative headline, and the reason is composition.** The 196 primary-source questions are not a scaled-down copy of the benchmark: 164 of them (84%) come from four categories, and Categories 4, 5 and 11 contribute none at all. What a source document can settle is not evenly distributed across the twelve categories — a threshold printed in an Approved Document can be located, a recommended retrofit ordering cannot. Reading the primary-source column as "the benchmark, done properly" would silently drop a quarter of the categories, including BMS anomaly classification, where every model scores near 0.95, and net-zero pathway reasoning, where the spread is widest. The 536-question figure remains the benchmark result.

Two effects are nonetheless visible in the table. First, the cross-validated subset produces the highest scores of the three for six of seven models. That is what one would expect if questions retained on the strength of model agreement are, on average, questions models find easy: the selection criterion and the thing being measured are not independent.

Second, part of the primary-source drop survives a control for category. Restricting the comparison to the six categories that contain both kinds of question:

| Model | Primary-source (n=140) | Cross-validated (n=129) | Difference |
|---|---|---|---|
| GPT-5 | 0.714 | 0.842 | −0.128 |
| Claude Opus 4.7 | 0.843 | 0.930 | −0.088 |
| Claude Opus 4.8 | 0.820 | 0.905 | −0.085 |
| Llama 3.3 70B (FP8) | 0.620 | 0.700 | −0.079 |
| GPT-4o | 0.681 | 0.691 | −0.010 |
| Qwen 2.5 7B (FP8) | 0.590 | 0.593 | −0.003 |
| Gemini 2.5 Pro | 0.825 | 0.824 | +0.001 |

The effect is real but not uniform: three models lose 0.08 or more, three are unchanged, and one is flat. We report it rather than interpret it; distinguishing an easier-question effect from a genuine answer-key effect would need a category-balanced verified subset, which is v2 work.

The unverifiable column runs the other way for the weaker models: GPT-4o scores 0.853 there against 0.681 on primary-source questions in the controlled comparison. Forty-eight of those 83 are EPC band predictions graded by `band_tolerance`, which awards half marks for an adjacent band, so a model that is reliably one band out does well without ever being right.

### 5.5 Settled and live regulatory positions

Some correct answers have a shelf life. Fifty-five questions turn on a position that is not yet in force, is under consultation, or commences after the evaluation date, and are tagged `live`. The other 481 rest on published values that do not move.

| Model | Settled (n=481) | 95% CI | Live (n=55) |
|---|---|---|---|
| Claude Opus 4.7 | **0.883** | [0.859, 0.905] | 0.938 |
| Claude Opus 4.8 | **0.867** | [0.843, 0.891] | 0.884 |
| Gemini 2.5 Pro | **0.845** | [0.820, 0.869] | 0.707 |
| GPT-5 | **0.821** | [0.791, 0.850] | 0.836 |
| GPT-4o | **0.733** | [0.701, 0.765] | 0.324 |
| Llama 3.3 70B (FP8) | **0.695** | [0.661, 0.729] | 0.305 |
| Qwen 2.5 7B (FP8) | **0.578** | [0.541, 0.616] | 0.202 |

Marking is identical across both columns. This is a reporting cut over one set of scores, not a second evaluation, and the tag is assigned from the content of the reference answer rather than from any model's performance.

The two columns look very different: the seven models span 0.31 on settled material and 0.74 on live. That difference is composition, not capability, and should not be read as a finding about currency of regulatory knowledge.

Fifty-four of the 55 live questions fall in Categories 11 and 12, which are the two hardest categories for the lower-scoring models irrespective of policy dependency. Restricting the comparison to those two categories removes the confound:

| Model | Live (n=54) | Settled (n=35) | Difference |
|---|---|---|---|
| Claude Opus 4.7 | 0.946 | 0.910 | +0.036 |
| Claude Opus 4.8 | 0.891 | 0.840 | +0.051 |
| Gemini 2.5 Pro | 0.711 | 0.711 | 0.000 |
| GPT-5 | 0.843 | 0.790 | +0.052 |
| GPT-4o | 0.321 | 0.346 | −0.025 |
| Llama 3.3 70B (FP8) | 0.301 | 0.272 | +0.029 |
| Qwen 2.5 7B (FP8) | 0.206 | 0.118 | +0.088 |

Within the same categories the two subsets score alike, with differences between −0.025 and +0.088 and no consistent direction. Models are not measurably worse on questions whose answer depends on a position still in motion.

The tag earns its place for a different reason. The settled subset rests on published values that do not move and will reproduce indefinitely. The live subset is valid as at 13 August 2026: its scores remain reproducible, because the dataset is content-hashed and every response is stored, but its ground truth expires, and a model evaluated against it later may be marked wrong for holding a more current position than the reference. The tag tells a future user which 55 questions to re-verify before reuse. That is a maintenance property of the benchmark, not a property of the models.

---

## 6. Discussion

**Model choice matters at the hard end, not the easy end.** On the structured-recall categories the gap between GPT-4o and the category leader is 0.041 on BMS anomalies, 0.100 on CIBSE and 0.125 on IFC entities. On Categories 10, 11 and 12 the same comparison gives 0.556, 0.705 and 0.517. A buyer comparing models on structured recall alone will not see the difference that determines whether a tool is safe to deploy.

Category 1 is the exception among the recall categories, at a gap of 0.218. Building Regulations questions turn on which edition and which table applies, which makes them closer in kind to the policy categories than their format suggests.

**The hard categories are hard for a reason that is not policy currency.** Categories 10, 11 and 12 produce the widest spreads in the benchmark, and it is tempting to attribute this to models being out of date on UK policy. The within-category comparison in Section 5.5 does not support that reading: on the two categories where both kinds of question appear, models score the same whether or not the answer depends on a position still in motion. The results are therefore consistent with the hypothesis that the multi-step reasoning these questions demand, rather than regulatory recency alone, drives much of the observed difficulty. The benchmark measures performance and not mechanism, so it constrains that explanation without establishing it.

**The two open-weights endpoints tested perform far better on structured classification than on policy reasoning.** Llama 3.3 70B reaches 0.917 on BMS anomaly classification and 0.296 on regulatory cliff-edge questions. That asymmetry, rather than the overall score, defines where these endpoints can be deployed. A pipeline using a small open model for routine classification and a frontier model for anything policy-dependent is a defensible architecture on these numbers. Two models at one provider's FP8 endpoints do not establish anything about open-weights models generally.

**The observed error rates indicate that none of the evaluated models should be assumed reliable for unsupervised date-specific or band-specific compliance advice.** The best overall result is 0.888 — roughly one answer in nine wrong — and 0.863 on the subset whose answers were checked against their source documents, or about one in seven. On Category 12, where a wrong answer is a wrong compliance date, the best result is 0.901 and three of the seven models score below 0.40.

---

## 7. Limitations

1. **Sample size.** Per-category n of 30 to 55 gives category-level intervals appreciably wider than the overall intervals. Single-category comparisons should be treated as indicative.
2. **Two categories are provisionally scored.** Category 2 and Category 8 reference answers are largely unverified against primary sources (Section 4.1). CIBSE material is licensed, which limits what any open benchmark can verify.
3. **Live questions expire.** Fifty-five questions are valid as at 13 August 2026. They remain reproducible, but their ground truth does not remain correct.
4. **Question provenance.** The 536 public questions were model-generated and then checked against the primary sources they name. Verification supports the answer key, but the distribution of question phrasing reflects a single generator. Human-authored questions from practising professionals are planned for v2. The holdout described in Section 8 was produced differently, by deterministic extraction from source documents.
5. **Option-length bias.** In the multiple-choice categories the correct option is the longest in 37% of questions against a chance rate near 25%, and in 69% of Category 6 questions. Some part of the Category 6 scores is attributable to option length rather than domain knowledge.
6. **Quantised endpoints.** Two results describe FP8 serverless endpoints rather than the underlying models.
7. **UK skew.** Categories 1, 2, 6, 8, 9 and 12 are UK-specific. EU coverage is real but shallow.
8. **Text only.** Drawings, BIM models and PDF reports are central to this profession and are not tested.

---

## 8. Future Work

A private holdout of 120 questions in four categories has been built and independently verified. Ninety-five are templated directly from primary sources — Approved Documents, the IFC4 EXPRESS schema and BREEAM SD5078 — by deterministic extraction scripts, so the wording is the source document's rather than a model's. The remaining 25 are self-contained arithmetic questions requiring no external source, decidable by re-deriving the calculation from figures given in the question. No model has been asked to answer any of them, and they have not been published. The set exists to provide a contamination check once the public split is in circulation, and will be run and reported with its date.

Planned for v2: human-authored questions from practising UK professionals; distractor rebalancing to remove the option-length effect; SAP modelling to settle the Category 2 references; a category-balanced primary-source-verified subset, so that verification status and category are not confounded as they are in Section 5.4; multimodal categories covering drawings and PDF reports; deeper EU coverage.

---

## 9. Conclusion

CladBench v1 measures large language models on twelve categories of UK and EU built-environment practice. Across seven models, scores range from 0.888 to 0.540, and the four leading models sit within a 0.065 band in which two are statistically indistinguishable.

The useful signal is not that ranking. Three findings sit behind it.

**The overall score compresses large capability differences.** Every model tested scores at least 0.75 on BMS anomaly classification and at least 0.70 on IFC entity reasoning; on regulatory cliff-edge questions the same seven span 0.901 to 0.126. A single aggregate number is an inadequate basis for choosing a model for professional built-environment work, because it averages away the categories on which the choice turns.

**Below the frontier, task type matters more than model choice.** For GPT-4o, Qwen 2.5 7B and Llama 3.3 70B, the spread across categories (0.63 to 0.67) exceeds the 0.348 spread between the best and worst models overall. The three strongest models are flatter, at 0.198 to 0.274.

**Regulatory currency does not explain the hardest categories.** Live-policy questions appear far harder than settled ones until category composition is controlled, at which point the difference largely disappears. The results are consistent with the hypothesis that what these categories demand is multi-step reasoning over a described building, rather than recency of regulatory knowledge alone — though this benchmark measures performance, not mechanism, and cannot settle the point.

The dataset, evaluation code, and all 3,752 per-question outputs are released for reuse and re-scoring.

---

## References

Bommasani, R. et al. (2021). *On the Opportunities and Risks of Foundation Models.* arXiv:2108.07258.

Liang, P. et al. (2022). *Holistic Evaluation of Language Models.* arXiv:2211.09110.

Srivastava, A. et al. (2022). *Beyond the Imitation Game: Quantifying and Extrapolating the Capabilities of Language Models.* arXiv:2206.04615.

Webersinke, N. et al. (2022). *ClimateBert: A Pretrained Language Model for Climate-Related Text.* arXiv:2110.12010.

Zheng, L. et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685.

Building Research Establishment (2018). *BREEAM UK New Construction SD5078*, Issue 3.0.

CIBSE (2021). *Guide A: Environmental Design.*

CIBSE (2016). *Guide B: Heating, Ventilating, Air Conditioning and Refrigeration.*

HM Government (2021). *Approved Document L (England), Volume 1: Dwellings.*

HM Government (2015). *The Energy Efficiency (Private Rented Property) (England and Wales) Regulations.*

European Union (2024). *Directive (EU) 2024/1275 on the energy performance of buildings (recast).*

buildingSMART International. *IFC4 EXPRESS schema specification.*

---

## Appendix A — Reproduction

```bash
git clone https://github.com/cladbrain/cladbench
cd cladbench
pip install -e .

# Provider keys for whichever models are to be evaluated
echo "ANTHROPIC_API_KEY=<your-key>"     >> .env
echo "OPENAI_API_KEY=<your-key>"        >> .env
echo "GOOGLE_GEMINI_API_KEY=<your-key>" >> .env
echo "TOGETHER_API_KEY=<your-key>"      >> .env

# Evaluate one model
python -m cladbench evaluate --model anthropic:claude-opus-4-7 \
       --split public --output my_run.jsonl

# Recompute scores from the released responses, calling no model at all
python -m cladbench score --input results/responses/full_opus47.jsonl

# Re-judge the rubric-graded rows as well (needs ANTHROPIC_API_KEY)
python -m cladbench score --input results/responses/full_opus47.jsonl \
       --judge anthropic
```

The `score` command requires no API key and no access to any evaluated model. Run against the released Claude Opus 4.7 outputs it recomputes 243 of the 536 rows — every row graded by a deterministic method — and reproduces all 243 stored scores exactly. The remaining 293 rows are rubric-graded and are reported as needing a judge rather than being carried over from the stored value.

## Appendix B — Released artefacts

| Artefact | Contents |
|---|---|
| Dataset | 536 questions with reference answers, citations, rubrics and review status |
| Schema | JSON Schema plus human-readable field documentation |
| Category specifications | What each category tests, why it matters, and a worked example |
| Per-question outputs | 3,752 records: model response, score and per-criterion breakdown |
| Judge marks | Both neutral judges and the Claude comparison pass, per answer |
| Run manifests | Dataset hash, harness version, model identifiers, token usage per run |

Any third party can re-score or re-judge any subset from the released outputs without API access to the evaluated models.
