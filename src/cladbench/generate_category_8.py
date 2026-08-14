"""Generate additional Category 8 (CIBSE Technical Q&A) examples via Claude.

MCQ format with exact_match grading.
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

CATEGORY_ID = 8
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 6, "focus": "CIBSE Guide A (Environmental Design) — design temperatures, comfort criteria, illuminance, ventilation rates, design conditions for different building types."},
    {"n": 6, "focus": "CIBSE Guide B (HVAC) — B1 heating systems sizing and design, B2 HVAC and refrigeration, B3 air distribution, B4 noise. Pressure drops, flow temps, system selection."},
    {"n": 5, "focus": "CIBSE Guide F (Energy Efficiency) — benchmarks for different building types, energy hierarchy, refurbishment energy strategy."},
    {"n": 5, "focus": "CIBSE TM series 21–54 — TM21 productivity, TM33 acoustics, TM39 metering, TM43 envelope air leakage, TM54 operational energy assessment."},
    {"n": 5, "focus": "CIBSE TM series 55–65 — TM55 refurbishment, TM57 integrated daylight design, TM59 domestic overheating, TM61 operational performance, TM65 embodied carbon."},
    {"n": 5, "focus": "Guide H (Building Controls) and Guide M (Maintenance) — control loop tuning, BMS commissioning, life-cycle maintenance intervals, system handover."},
    {"n": 3, "focus": "Cross-CIBSE practical scenarios — combining multiple guides for design decisions, post-occupancy evaluation methodology, performance gap analysis."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} CIBSE technical Q&A questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "mcq" with exactly 4 options
- question.text MUST be a CIBSE practitioner-level technical question with clear unambiguous correct answer
- answer.choice MUST be A, B, C, or D
- answer.citation MUST cite specific CIBSE Guide section or TM number, e.g. "CIBSE Guide B2, Section 5"
- grading.method MUST be "exact_match" with case_sensitive false
- source.curator = "claude_generated"; review_status = "draft"; reviewed_at = "2026-06-18"
- source.primary should match answer.citation
- difficulty = "practitioner" or "foundation"; tags include "cibse" and a specific guide/TM tag
- IDs cb1-08-public-XXXX starting from {next_id:04d}
- Distribute correct answers across A-D roughly evenly
- Be respectful of CIBSE IP — test concepts and findable methods, not extensive reproduction of guide text

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-08-public-NNNN",
  "category": 8,
  "category_name": "CIBSE Technical Q&A",
  "format": "mcq",
  "split": "public",
  "question": {"text": "...CIBSE technical question...", "options": ["A...", "B...", "C...", "D..."]},
  "answer": {"choice": "B", "citation": "CIBSE Guide X / TM XX, Section Y"},
  "grading": {"method": "exact_match", "case_sensitive": false},
  "source": {"primary": "CIBSE Guide X / TM XX", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["cibse", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-08-public-0001", "cb1-08-public-0006", "cb1-08-public-0010", "cb1-08-public-0014"}
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
            max_tokens=4500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)}")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-08-public-{next_id:04d}"
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
    print(f"Category 8 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
