# CladBench v1 — 12 Category Specifications

> Locked spine of the benchmark. Each category has: **what it tests**, **why it matters**, **format**, **grading methodology**, and **one worked example**.
> 
> Total dataset target: 600–1,200 public examples + 120 private holdout questions across four categories.
>
> Drafted 2026-06-17. Pending Tamil review pass: validate against how the field actually works, mark accepted / edited / rejected.

---

## Category 1 — UK Building Regulations Q&A

- **What it tests**: The model's ability to navigate UK Approved Documents (Parts A through Q) and produce citable clause references for compliance questions. Tests both factual recall and the precision of regulatory citation.
- **Why it matters**: Approved Document compliance is the gating step for every UK building project. A model that confidently invents clause numbers is not just unhelpful — it is dangerous in a regulatory advisory workflow. This is the single most-asked question type in UK building practice.
- **Format**: Multiple choice (4 options + 1 correct answer with clause reference). 70 examples total — 55 public, 15 private.
- **Grading**: Exact match on the letter choice. Optional: penalise hallucinated clause numbers in the reference field.
- **Worked example**:
  > **Q**: For a new dwelling in England, what is the limiting U-value for an external wall under Approved Document L1A (2021)?
  > A) 0.20 W/m²K  
  > B) 0.26 W/m²K  
  > C) 0.30 W/m²K  
  > D) 0.18 W/m²K  
  > **Answer**: B. *Reference: ADL1A 2021, Table 4.1, limiting U-value for external walls in new dwellings.*

---

## Category 2 — EPC Trajectory Prediction

- **What it tests**: Given a current Energy Performance Certificate and a proposed retrofit intervention, the model predicts the resulting EPC band. Tests quantitative reasoning + UK-specific knowledge of SAP/RdSAP scoring rules.
- **Why it matters**: Every MEES compliance discussion hinges on this calculation. Practitioners ask it constantly during pre-investment conversations with landlords.
- **Format**: Short answer — the predicted band (A–G) + a one-sentence justification. 65 examples total — 50 public, 15 private.
- **Grading**: Exact match on the band letter. Justification scored by LLM-judge (Claude) against a reference rubric for partial credit.
- **Worked example**:
  > **Q**: A semi-detached 1960s property currently rated EPC D (54). The owner plans to install loft insulation (to 300mm), upgrade the boiler to a 92% efficiency condensing model, and add cavity wall insulation. What is the most likely resulting EPC band?
  > **Answer**: C. *Justification: combined fabric + heating measures typically lift this housing archetype 12–18 SAP points, placing the property in the high-50s to mid-60s range, comfortably in Band C.*

---

## Category 3 — IFC Entity Reasoning

- **What it tests**: Understanding of the Industry Foundation Classes (IFC) schema used in BIM workflows — entity types, relationships, and inheritance. Tests whether the model can reason about a building model structurally.
- **Why it matters**: BIM is the standard substrate for design and asset management. An AI assistant that cannot reason about IFC entities cannot be embedded in a real BIM workflow.
- **Format**: Multiple choice (4 options). Mix of "which IFC entity represents X" and "what is the relationship between IfcA and IfcB". 50 examples total — 40 public, 10 private.
- **Grading**: Exact match on letter choice.
- **Worked example**:
  > **Q**: In IFC4, which entity is used to represent a physical wall in a building model?
  > A) IfcWallElement  
  > B) IfcWall  
  > C) IfcBuildingElementWall  
  > D) IfcStructuralWall  
  > **Answer**: B. *IfcWall is the canonical entity for both standard and non-standard walls; IfcWallStandardCase is a subtype.*

---

## Category 4 — BMS Sensor Anomaly Classification

- **What it tests**: Given a 24-hour time series of BMS sensor readings (temperature, CO₂, humidity, setpoint, control output), the model identifies what category of issue is present — calibration drift, control loop instability, sensor failure, setpoint change, or normal operation.
- **Why it matters**: Building management systems generate vast time-series data. The cost of failing to spot a fault early can be tens of thousands of pounds in wasted energy or comfort complaints. This is the single highest-value AI application in building operations today.
- **Format**: Multiple choice (5 options including "normal operation"). Each example includes a synthetic but realistic 24-hour trace + textual description. 60 examples — 50 public, 10 private.
- **Grading**: Exact match on category label.
- **Worked example**:
  > **Q**: An AHU supply air temperature sensor reads steady at 21.0°C across a 24-hour period despite outside air swinging from 8°C overnight to 24°C in the afternoon, while control output varies normally. Which category of issue does this most likely indicate?
  > A) Calibration drift  
  > B) Setpoint change  
  > C) Sensor failure (stuck reading)  
  > D) Control loop instability  
  > E) Normal operation  
  > **Answer**: C.

---

## Category 5 — Retrofit Prioritisation

- **What it tests**: Given a building scenario and a list of 5–8 candidate retrofit measures (each with capex, predicted carbon saving, expected lifespan), the model ranks them by carbon-per-pound saved while accounting for any sequencing constraints (e.g. fabric-first ordering).
- **Why it matters**: This is the consulting workflow itself — the question every retrofit advisor is asked by every client. A model that gets this right unlocks scaled retrofit decision support.
- **Format**: Ranking — produce an ordered list of the measures. 40 examples — 30 public, 10 private.
- **Grading**: Rank correlation (Spearman) against a reference ranking, plus a rubric-based LLM-judge check for inclusion of sequencing logic.
- **Worked example**:
  > **Q**: A 1930s semi-detached owner-occupier property in Bristol. Budget £25,000. Candidate measures: (a) external wall insulation £14k, 1.8 tCO₂e/yr; (b) ASHP replacing gas boiler £12k, 1.2 tCO₂e/yr; (c) double-glazed windows £6k, 0.4 tCO₂e/yr; (d) loft insulation top-up £400, 0.3 tCO₂e/yr; (e) PV array 4kWp £6k, 0.9 tCO₂e/yr; (f) MVHR system £5k, 0.2 tCO₂e/yr. Rank by carbon-per-pound, applying fabric-first sequencing.
  > **Answer**: d, a, c, e, b, f. *Loft top-up has by far the best £/tCO₂e ratio (~£1,333/tCO₂e/yr); EWI next (~£7,778) and double glazing after (~£15,000) within the fabric-first group; then PV (~£6,667), ASHP (~£10,000), and MVHR last (~£25,000) within the active-systems group. Active systems sequenced after fabric to avoid oversizing the ASHP.*

---

## Category 6 — BREEAM Credit Eligibility

- **What it tests**: For a given building scheme description, determine whether it qualifies for a specific BREEAM credit in a given category (e.g. Hea 02 indoor air quality, Ene 04 low-carbon design, Mat 03 responsible sourcing).
- **Why it matters**: BREEAM scoring is one of the most precision-demanding tasks in UK building practice. A wrong credit assessment can cost a project its target rating. A model that gets this wrong is worse than no model.
- **Format**: Multiple choice with rationale (does it qualify? if not, what's missing?). 70 examples — 55 public, 15 private. Drawn from BREEAM NC 2018 (and v7 once published).
- **Grading**: Exact match on Yes/No qualification + LLM-judge on the rationale paragraph.
- **Worked example**:
  > **Q**: A new-build office in central Manchester targets Hea 02 (Indoor Air Quality). The design specifies mechanical ventilation with heat recovery (MVHR) at 12 L/s per person, low-VOC paints meeting BS EN 16516, and an indoor air quality plan documented at RIBA Stage 4. Does this scheme qualify for the first credit under Hea 02?
  > A) Yes — meets ventilation, low-emission materials, and plan requirements  
  > B) No — fresh air rate insufficient; minimum 10 L/s per person required only when CO₂ sensors are installed and the IAQ plan is at RIBA Stage 3 or earlier  
  > **Answer**: A.

---

## Category 7 — Thermal Comfort Diagnosis

- **What it tests**: Given a description of occupant comfort complaints in a UK office or residential building, the model produces a structured diagnosis identifying likely causes against CIBSE TM52 methodology and recommends investigation steps.
- **Why it matters**: Thermal comfort is the #1 source of occupant complaints in offices. Diagnosis requires combining building physics knowledge with CIBSE-specific methodology.
- **Format**: Open answer with structured response — diagnosis, primary cause, secondary causes, recommended actions. 50 examples — 40 public, 10 private.
- **Grading**: LLM-judge (Claude) against a 5-point rubric: identifies methodology, primary cause correctness, secondary cause coverage, action recommendations, citation quality.
- **Worked example**:
  > **Q**: Open-plan office in Cambridge, 80 occupants, complaints concentrated in the west-facing zone from 14:00–17:00 during July–August. Building has fixed external blinds set to 60° and a VAV cooling system. Diagnose the likely overheating issue under CIBSE TM52.
  > **Answer**: *Likely a combination of solar gain through the unshaded portion of west-facing fenestration and inadequate VAV box throw in the west zone. Apply TM52 Criterion 1 (Hours of Exceedance) — modelling will likely show >3% of occupied hours above the upper acceptable limit. Primary cause: blind angle insufficient for late-afternoon sun azimuth. Recommended actions: (1) CFD or zonal modelling to confirm VAV airflow distribution; (2) trial dynamic blind control or internal blinds for late-afternoon; (3) consider increasing AHU supply temperature differential to recover capacity.*

---

## Category 8 — CIBSE Technical Q&A

- **What it tests**: Recall and application of UK building services engineering knowledge from CIBSE Guides A (Environmental Design), B (Heating, Ventilating, Air Conditioning and Refrigeration), F (Energy Efficiency), and the TM series.
- **Why it matters**: CIBSE Guides are the canonical reference for UK building services engineering. Every practitioner uses them daily. A model that handles them at the level of a chartered engineer is immediately useful.
- **Format**: Multiple choice (4 options). 65 examples — 50 public, 15 private. Be respectful of CIBSE IP — questions test concepts and findable methods, not extensive reproduction of guide text.
- **Grading**: Exact match.
- **Worked example**:
  > **Q**: According to CIBSE Guide A, the recommended design winter dry resultant temperature for a single office occupied by sedentary clerical workers is approximately:
  > A) 18–20°C  
  > B) 21–23°C  
  > C) 24–26°C  
  > D) 16–18°C  
  > **Answer**: B.

---

## Category 9 — Material and Product Specification

- **What it tests**: Interpretation of Environmental Product Declarations (EPDs), embodied carbon lookups, and manufacturer data. Tests whether the model can advise on material selection against carbon and performance criteria.
- **Why it matters**: Embodied carbon now matters as much as operational carbon for low-energy buildings. Material selection decisions made at concept stage lock in emissions for the building's lifetime.
- **Format**: Multiple choice + short answer. 65 examples — 50 public, 15 private. Sourced from the EPD International registry and published manufacturer datasheets.
- **Grading**: Exact match on the multiple choice; LLM-judge on short answer rationale.
- **Worked example**:
  > **Q**: Comparing two cement-based plasters at 12mm thickness applied to internal masonry: Product A — gypsum-based, EPD declared 0.30 kgCO₂e/kg, density 1100 kg/m³; Product B — lime-based, EPD declared 0.18 kgCO₂e/kg, density 1400 kg/m³. Which has the lower embodied carbon per m² of wall area?
  > **Answer**: Product B. *Calculation: A = 0.012 × 1100 × 0.30 = 3.96 kgCO₂e/m²; B = 0.012 × 1400 × 0.18 = 3.02 kgCO₂e/m². Although B is denser, its lower carbon intensity per kg outweighs the density difference — a result naive intuition often gets wrong.*

---

## Category 10 — Energy Bill Anomaly Detection

- **What it tests**: Given 12 months of metered energy data (electricity + gas) for a building, identify and classify anomalies — base load drift, occupancy schedule shifts, billing errors, control malfunctions.
- **Why it matters**: Energy bill review is a regular consulting task and a leading indicator of operational issues. Anomaly detection in bill data is a perfect AI application — pattern-recognition with clear ground truth.
- **Format**: Short answer — describe the anomaly and likely cause. 40 examples — 30 public, 10 private. Synthetic but realistic 12-month profiles.
- **Grading**: LLM-judge against reference description (anomaly identified, cause classified, magnitude reasonable).
- **Worked example**:
  > **Q**: A medium-sized office (3,000 m²) shows electricity consumption stable at ~45,000 kWh/month for nine months, then a step change to ~62,000 kWh/month for the last three months. Gas consumption shows a normal seasonal pattern. What is the most likely cause?
  > **Answer**: *Most likely an additional electric load (e.g. new server room, supplementary cooling, or kitchen equipment) commissioned three months ago. Less likely but worth checking: a control system change causing a primary HVAC system to operate longer hours, or a meter calibration shift. Diagnostic step: cross-reference billing dates against any IT or M&E project completions in the same window.*

---

## Category 11 — Net Zero Pathway Reasoning

- **What it tests**: Given a building portfolio description (mix of property types, current performance, capex constraints), the model produces a coherent decarbonisation pathway aligned with UK or EU 2030/2050 targets.
- **Why it matters**: This is the strategic conversation every property owner needs to have. A model that can hold this conversation responsibly accelerates climate planning.
- **Format**: Open answer with structured response — proposed pathway, milestone year by year, dependency identification, risk flags. 50 examples — 40 public, 10 private.
- **Grading**: LLM-judge against a 5-point rubric: target alignment, intervention sequencing, capex realism, dependency awareness, regulatory awareness.
- **Worked example**:
  > **Q**: A UK pension fund holds 40 office buildings (mix of 1970s, 1990s, 2010s stock), total 250,000 m² floor area. Current portfolio EPC average is D. Owner targets net zero operational carbon by 2040 with 2% real annual capex allocation. Propose a high-level pathway.
  > **Answer**: *2026–2030: prioritise the worst-performing 25% of stock (likely the 1970s tranche) for fabric upgrade + heating decarbonisation, targeting EPC C by 2027 and EPC B by 2030 to meet proposed MEES tightening. 2030–2035: heat pump rollout across the 1990s portfolio, paired with PV where roof structure permits. 2035–2040: residual emissions addressed via green tariff procurement and final building-fabric upgrades. Dependencies: grid decarbonisation timeline, MEES enforcement clarity, tenant cooperation for major refurbishment.*

---

## Category 12 — Regulatory Cliff-Edge Reasoning

- **What it tests**: Awareness of UK and EU regulatory deadlines and the financial/legal implications of missing them — MEES tightening schedule, Future Homes Standard, EPBD recast deadlines.
- **Why it matters**: Asset-level investment decisions hinge on knowing exactly which property will be illegal to let on which date and at what cost. This category specifically tests dates and consequences.
- **Format**: Short answer. 65 examples — 50 public, 15 private.
- **Grading**: Exact match on dates and bands; LLM-judge on consequence reasoning.
- **Worked example**:
  > **Q**: A landlord owns a non-domestic rented property in England currently at EPC Band D. Under the government's proposed MEES tightening (2021 BEIS consultation), assuming the regulations are laid as proposed, on what date does the property first become illegal to let, and what is the minimum EPC improvement required to re-let?
  > **Answer**: *1 April 2027. Property must reach at least EPC Band C to be legally let from that date. Subsequent tightening to Band B by 1 April 2030. Note: as of June 2026 these regulations remain proposed; the government's formal response to the 2021 consultation has not yet been published.*

---

## Summary

| # | Category | Format | Total | Public | Private | Grading |
|---|---|---|---|---|---|---|
| 1 | UK Building Regs | MCQ | 70 | 55 | 15 | Exact match |
| 2 | EPC Trajectory | Short answer | 65 | 50 | 15 | Exact + LLM-judge |
| 3 | IFC Entity Reasoning | MCQ | 50 | 40 | 10 | Exact match |
| 4 | BMS Sensor Anomaly | MCQ | 60 | 50 | 10 | Exact match |
| 5 | Retrofit Prioritisation | Ranking | 40 | 30 | 10 | Spearman + LLM-judge |
| 6 | BREEAM Credit Eligibility | MCQ + rationale | 70 | 55 | 15 | Exact + LLM-judge |
| 7 | Thermal Comfort Diagnosis | Open | 50 | 40 | 10 | LLM-judge (rubric) |
| 8 | CIBSE Technical Q&A | MCQ | 65 | 50 | 15 | Exact match |
| 9 | Material / Product Spec | MCQ + short | 65 | 50 | 15 | Exact + LLM-judge |
| 10 | Energy Bill Anomaly | Short answer | 40 | 30 | 10 | LLM-judge |
| 11 | Net Zero Pathway | Open | 50 | 40 | 10 | LLM-judge (rubric) |
| 12 | Regulatory Cliff-Edge | Short answer | 65 | 50 | 15 | Exact + LLM-judge |
| | **Total** | | **690** | **540** | **150** | |

Targets the plan's 600–1,200 public + ~150 private. Sits at the lower-curation-effort end of the range, leaves room to expand any category we find under-spec.

---

## Tamil's review pass — what to check

1. **Are the formats right** for how the field actually works? E.g. is "ranking" the right format for retrofit prioritisation, or should it be open-answer with scoring?
2. **Are the categories complete**? Have I missed a category that practitioners would want? Or over-specified one?
3. **Are the worked examples plausible**? Anywhere the example feels artificial or the answer is wrong, flag it.
4. **Are the grading methodologies appropriate**? LLM-judge is expensive at scale; exact-match is rigid. Tell me where I've got the balance wrong.
5. **Are the public/private splits right**? Currently ~80/20. The plan specifies 50–70 public + 10–15 private per category, which I've followed.

When you've reviewed, mark each category as `accepted`, `edited`, or `rejected` and tell me. I'll then lock the specs and we move to Layer 2 (JSON schema).
