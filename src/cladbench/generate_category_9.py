"""Generate additional Category 9 (Material and Product Specification) examples via Claude.

mcq_with_rationale format with exact_match_plus_judge grading.
"""

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

CATEGORY_ID = 9
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 5, "focus": "Concrete and cement substitution — CEM I vs CEM II vs CEM III/A vs CEM III/B; GGBS vs flyash vs limestone calcined clay (LC3) substitution effects on A1-A3."},
    {"n": 5, "focus": "Insulation comparison — PIR vs phenolic vs EPS vs XPS vs mineral wool vs cellulose vs wood fibre vs hemp; lambda values, density, and A1-A3 trade-offs."},
    {"n": 5, "focus": "Structural timber vs steel vs concrete frames — CLT, glulam, LVL, hybrid timber-concrete vs steel section vs RC frame; whole-life with biogenic reversal."},
    {"n": 5, "focus": "Glazing and curtain wall — IGU configurations, frame materials (aluminium, timber, hybrid, uPVC), spacer types, gas fills; embodied vs operational trade-off."},
    {"n": 5, "focus": "Cladding and rainscreen — terracotta, fibre cement, ACM (post-Grenfell A1-fire-rated only), timber rainscreen, stone, brick slip; embodied carbon range."},
    {"n": 5, "focus": "Internal finishes — plasterboard, ceiling tiles, paint (low-VOC EPDs), floor coverings; B4 replacement frequency dominance over A1-A3."},
    {"n": 5, "focus": "MEP and building services materials — copper vs plastic pipe, ductwork material, refrigerant GWP, PV panels, batteries; TM65 methodology."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} Material and Product Specification questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "mcq_with_rationale" with exactly 4 options
- question.text MUST present a realistic UK material-selection scenario with concrete numbers (kgCO2e/kg or kgCO2e/m3, densities, thicknesses, areas, EPD data) and a clear question
- answer.choice MUST be A, B, C, or D
- answer.rationale MUST show the calculation explicitly (per-m2 or per-kg as relevant) and reference EPD/EN 15804 framing where appropriate
- answer.citation MUST cite EN 15804, EN 15978, EPD registry, IStructE How to calculate embodied carbon, CIBSE TM65, manufacturer EPDs, or similar
- grading.method MUST be "exact_match_plus_judge"
- grading.rubric MUST be exactly: [{{"criterion": "Correct qualification choice", "max_points": 3}}, {{"criterion": "Calculation shown in rationale", "max_points": 1}}, {{"criterion": "Rationale references methodology / caveat", "max_points": 1}}]
- source.curator = "claude_generated"; review_status = "draft"; reviewed_at = "2026-06-18"
- difficulty = "practitioner" or "expert"; tags include "material" and "embodied-carbon" + a topic tag
- IDs cb1-09-public-XXXX starting from {next_id:04d}
- Distribute correct answers across A-D roughly evenly across the batch
- Use realistic UK material market data and plausible EPD numbers

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-09-public-NNNN",
  "category": 9,
  "category_name": "Material and Product Specification",
  "format": "mcq_with_rationale",
  "split": "public",
  "question": {"text": "...material scenario + question with numbers...", "options": ["A...", "B...", "C...", "D..."]},
  "answer": {"choice": "B", "rationale": "Calculation: ... Conclusion: ... Caveat: ...", "citation": "EN 15804+A2; ..."},
  "grading": {"method": "exact_match_plus_judge", "rubric": [{"criterion": "Correct qualification choice", "max_points": 3}, {"criterion": "Calculation shown in rationale", "max_points": 1}, {"criterion": "Rationale references methodology / caveat", "max_points": 1}]},
  "source": {"primary": "EN 15804+A2; ...", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["material", "embodied-carbon", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-09-public-0001", "cb1-09-public-0003", "cb1-09-public-0010", "cb1-09-public-0013"}
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
            obj["id"] = f"cb1-09-public-{next_id:04d}"
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
        print(f"  accepted {len(batch_accepted)}/{batch['n']} (written)")

    print(f"\nTotal new examples accepted: {total_accepted}")
    print(f"Category 9 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
