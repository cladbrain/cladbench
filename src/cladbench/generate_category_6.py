"""Generate additional Category 6 (BREEAM Credit Eligibility) examples via Claude."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from cladbench.loaders import (
    CATEGORY_DIRS,
    DATA_ROOT_DEFAULT,
    load_jsonl,
    validate_example,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=False)

CATEGORY_ID = 6
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 6, "focus": "BREEAM Management (Man) credits — Man 01 Project Brief & Design, Man 02 Life Cycle Cost, Man 03 Responsible Construction Practices, Man 04 Commissioning & Handover, Man 05 Aftercare. Realistic scheme scenarios + clear Yes/No qualification."},
    {"n": 7, "focus": "BREEAM Health & Wellbeing (Hea) credits — Hea 01 Visual Comfort (daylight, glare), Hea 02 Indoor Air Quality (covered in seeds, ADD NEW SCENARIOS), Hea 04 Thermal Comfort, Hea 05 Acoustic Performance, Hea 07 Safe Access."},
    {"n": 7, "focus": "BREEAM Energy (Ene) credits — Ene 02a Energy Monitoring, Ene 03 External Lighting, Ene 05 Energy Efficient Cold Storage, Ene 06 Energy Efficient Transportation Systems, Ene 07 Energy Efficient Laboratory Systems, Ene 08 Energy Efficient Equipment."},
    {"n": 5, "focus": "BREEAM Transport (Tra) — Tra 01 Public Transport Accessibility, Tra 02 Proximity to Amenities, Tra 04 Maximum Car Parking Capacity, Tra 05 Travel Plan. Scenarios with measurable distances and frequencies."},
    {"n": 5, "focus": "BREEAM Water (Wat) — Wat 02 Water Monitoring, Wat 03 Water Leak Detection, Wat 04 Water Efficient Equipment. Plus more Wat 01 Water Consumption scenarios with different uses (residential, healthcare)."},
    {"n": 7, "focus": "BREEAM Materials (Mat) — Mat 01 LCA, Mat 02 Hard Landscaping, Mat 04 Insulation, Mat 05 Designing for Durability and Resilience, Mat 06 Material Efficiency, plus more Mat 03 scenarios with different material mixes."},
    {"n": 6, "focus": "BREEAM Waste, Land Use, Pollution — Wst 02 Recycled Aggregates, Wst 03 Operational Waste, Wst 05 Adaptation to Climate Change, LE 02 Ecological Value of Site, LE 03 Minimising Impact on Existing Ecology, Pol 01 Impact of Refrigerants, Pol 02 NOx Emissions, Pol 03 Surface Water Run-off."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} BREEAM Credit Eligibility questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "mcq_with_rationale" with exactly 4 options
- question.text MUST describe a realistic UK building scheme + the BREEAM credit being targeted, ending with a Yes/No qualification question
- answer.choice MUST be A, B, C, or D
- answer.rationale MUST briefly justify the choice with reference to the specific BREEAM credit criteria
- answer.citation MUST cite BREEAM NC 2018 (SD5078), BREEAM RFO 2014, or BREEAM In-Use as appropriate
- grading.method MUST be "exact_match_plus_judge"
- grading.rubric MUST be exactly: [{{"criterion": "Correct qualification choice", "max_points": 3}}, {{"criterion": "Rationale references specific BREEAM requirement", "max_points": 1}}, {{"criterion": "Rationale shows understanding of credit criteria", "max_points": 1}}]
- source.curator = "claude_generated"; review_status = "draft"; curated_at = "2026-06-18"
- difficulty = "practitioner"; tags include "breeam" + the specific credit code (e.g. "man-01")
- IDs cb1-06-public-XXXX starting from {next_id:04d}
- Distribute correct answers across A-D roughly evenly across the batch
- Use realistic UK contexts (cities, schemes, professional roles)

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-06-public-NNNN",
  "category": 6,
  "category_name": "BREEAM Credit Eligibility",
  "format": "mcq_with_rationale",
  "split": "public",
  "question": {"text": "...scheme + credit + qualification question...", "options": ["A...", "B...", "C...", "D..."]},
  "answer": {"choice": "A", "rationale": "...", "citation": "BREEAM NC 2018 (SD5078), ..."},
  "grading": {"method": "exact_match_plus_judge", "rubric": [{"criterion": "Correct qualification choice", "max_points": 3}, {"criterion": "Rationale references specific BREEAM requirement", "max_points": 1}, {"criterion": "Rationale shows understanding of credit criteria", "max_points": 1}]},
  "source": {"primary": "BREEAM NC 2018 SD5078, ...", "curator": "claude_generated", "review_status": "draft", "curated_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["breeam", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-06-public-0001", "cb1-06-public-0004", "cb1-06-public-0009"}
    chosen = [ex for ex in seed_examples if ex["id"] in chosen_ids]
    return "\n".join(json.dumps(ex, ensure_ascii=False) for ex in chosen)


def parse_jsonl_response(text: str) -> list[dict]:
    objects: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", line)
            if m:
                try:
                    objects.append(json.loads(m.group(0)))
                except json.JSONDecodeError:
                    pass
    return objects


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)

    seed_examples = list(load_jsonl(CATEGORY_PATH))
    print(f"Loaded {len(seed_examples)} seed examples from {CATEGORY_PATH}")

    existing_ids = {ex["id"] for ex in seed_examples}
    next_id = max((int(eid.split("-")[-1]) for eid in existing_ids), default=0) + 1

    schema_block = load_schema_block()
    few_shot = few_shot_block(seed_examples)

    total_accepted = 0

    def write_batch(items: list[dict]) -> None:
        with CATEGORY_PATH.open("a", encoding="utf-8") as f:
            for ex in items:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    for batch_i, batch in enumerate(BATCHES, start=1):
        prompt = GENERATION_PROMPT.format(
            n=batch["n"],
            focus=batch["focus"],
            schema_block=schema_block,
            few_shot_block=few_shot,
            next_id=next_id,
        )
        print(f"\n[batch {batch_i}/{len(BATCHES)}] requesting {batch['n']}")

        msg = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)}")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-06-public-{next_id:04d}"
            if obj["id"] in existing_ids:
                continue
            try:
                validate_example(obj)
            except ValueError as e:
                print(f"  [skip] {obj['id']}: {e}")
                continue
            existing_ids.add(obj["id"])
            batch_accepted.append(obj)
            next_id += 1
        write_batch(batch_accepted)
        total_accepted += len(batch_accepted)
        print(f"  accepted {len(batch_accepted)}/{batch['n']} from this batch (written)")

    print(f"\nTotal new examples accepted: {total_accepted}")
    print(f"Category 6 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
