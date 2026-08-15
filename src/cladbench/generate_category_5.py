"""Generate additional Category 5 (Retrofit Prioritisation) examples via Claude.

Ranking format with spearman_plus_judge grading.

Usage:
    PYTHONPATH=backend backend/.venv/Scripts/python.exe \
        backend/cladbench/generate_category_5.py
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

CATEGORY_ID = 5
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {
        "n": 4,
        "focus": "Pre-1919 housing (Victorian, Edwardian) — solid-wall scenarios. Mix of EWI, IWI, ASHP, MVHR, sash window replacement, loft, airtightness.",
    },
    {
        "n": 4,
        "focus": "Interwar housing (1919-1944) — cavity wall (often unfilled), pitched roof. Loft, cavity fill, glazing, boiler swap, ASHP, smart controls, PV.",
    },
    {
        "n": 4,
        "focus": "Post-war housing (1945-1980) — concrete frame, system-built, cavity walls. Loft top-up, ASHP, PV+battery, MVHR, smart controls.",
    },
    {
        "n": 4,
        "focus": "Commercial property (1985-2010 offices, retail, small industrial) — LED, BMS optimisation, AHU heat recovery, roof insulation, PV at scale, ASHP/GSHP plant replacement.",
    },
    {
        "n": 4,
        "focus": "Public sector buildings (schools, care homes, libraries) — fabric upgrades, BMS, ground source heat pumps, controls and demand-side management.",
    },
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} retrofit-prioritisation ranking questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "ranking" with 6 candidates (one per measure)
- question.text MUST describe building context (era, type, location optional, EPC band) + budget + the ranking instruction "Rank measures by lifetime carbon-per-pound saved, applying fabric-first sequencing"
- question.candidates MUST be a list of 6 strings of the form "<measure> £<capex>, saves <X> tCO₂e/yr, <Y>-yr life"
- answer.ranking MUST be a list of 6 lowercase letters a-f representing the ranking, best first
- answer.rationale MUST briefly justify the ranking
- grading.method MUST be "spearman_plus_judge"
- grading.rubric MUST be exactly: [{{"criterion": "Spearman rank correlation with reference >= 0.7", "max_points": 3}}, {{"criterion": "Fabric-first sequencing applied", "max_points": 2}}]
- source.curator = "claude_generated"; review_status = "draft"; curated_at = "2026-06-18"
- source.primary should reference PAS 2035:2023 or relevant CIBSE guidance
- difficulty = "practitioner"; tags include "retrofit", "ranking"
- IDs cb1-05-public-XXXX starting from {next_id:04d}
- Realistic costs and carbon savings — see reference examples for plausible ranges
- Verify your ranking is genuinely best-first by lifetime £/tCO₂e considering both £/tCO₂e/yr × life and fabric-first ordering

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-05-public-NNNN",
  "category": 5,
  "category_name": "Retrofit Prioritisation",
  "format": "ranking",
  "split": "public",
  "question": {"text": "...scenario + ranking instruction...", "candidates": ["measure a £X, saves Y tCO₂e/yr, Z-yr life", ...]},
  "answer": {"ranking": ["a","b","c","d","e","f"], "rationale": "..."},
  "grading": {"method": "spearman_plus_judge", "rubric": [{"criterion": "Spearman rank correlation with reference >= 0.7", "max_points": 3}, {"criterion": "Fabric-first sequencing applied", "max_points": 2}]},
  "source": {"primary": "PAS 2035:2023", "curator": "claude_generated", "review_status": "draft", "curated_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["retrofit", "ranking", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-05-public-0001", "cb1-05-public-0004", "cb1-05-public-0009"}
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
        print(
            f"\n[batch {batch_i}/{len(BATCHES)}] requesting {batch['n']} for: {batch['focus'][:60]}..."
        )

        msg = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)} JSON objects from response")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-05-public-{next_id:04d}"
            if obj["id"] in existing_ids:
                continue
            try:
                validate_example(obj)
            except ValueError as e:
                print(f"  [skip] schema error in {obj['id']}: {e}")
                continue
            existing_ids.add(obj["id"])
            batch_accepted.append(obj)
            next_id += 1
        write_batch(batch_accepted)
        total_accepted += len(batch_accepted)
        print(f"  accepted {len(batch_accepted)}/{batch['n']} from this batch (written)")

    print(f"\nTotal new examples accepted: {total_accepted}")
    print(f"Category 5 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
