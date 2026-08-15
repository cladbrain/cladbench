"""Generate additional Category 1 (UK Building Regs MCQ) examples using Claude.

Workflow:
1. Load existing examples from data/01_uk_building_regs/public.jsonl as few-shot seeds.
2. For each of 8 focus areas (covering all main Approved Documents), call Claude
   to generate 4-5 new MCQs.
3. Validate each generated example against schema.json.
4. Append valid ones to public.jsonl with curator="claude_generated".

Usage:
    PYTHONPATH=backend backend/.venv/Scripts/python.exe \
        backend/cladbench/generate_category_1.py

Re-runnable: skips IDs that already exist in the file.
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

CATEGORY_ID = 1
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {
        "n": 5,
        "focus": "Approved Document L1A 2021 — heating system efficiency, heating controls, hot water cylinders, smart meter readiness, and renewable energy generation in NEW domestic dwellings",
        "tag_seed": "heating",
    },
    {
        "n": 4,
        "focus": "Approved Document L2A 2021 — energy efficiency compliance for NEW NON-DOMESTIC buildings (offices, retail, education). Notional building, BER, TPER for non-domestic, lighting power density, HVAC efficiency",
        "tag_seed": "non-domestic",
    },
    {
        "n": 5,
        "focus": "Approved Document B Volumes 1 and 2 — fire resistance ratings, compartmentation, external wall fire performance (Reg 7), means of escape, fire alarm system requirements",
        "tag_seed": "fire-safety",
    },
    {
        "n": 4,
        "focus": "Approved Document F Volumes 1 and 2 — MVHR efficiency, IAQ monitoring in non-domestic spaces, continuous extract rates for wet rooms, ductwork airtightness",
        "tag_seed": "ventilation",
    },
    {
        "n": 4,
        "focus": "Approved Documents C and E — site preparation against contaminants, radon protection (Class 1 vs Class 2 areas), separating-floor impact sound performance, separating-floor airborne performance",
        "tag_seed": "moisture-acoustics",
    },
    {
        "n": 4,
        "focus": "Approved Documents G and H — hot water cylinder safety devices, scald-risk temperature controls, rainwater drainage gradients, foul drainage adoption requirements",
        "tag_seed": "sanitation-drainage",
    },
    {
        "n": 4,
        "focus": "Approved Documents K and M — guarding (balcony, stair) heights, ramp gradients, M4(1) visitable dwellings requirements, M4(2) accessible-and-adaptable dwellings doorway widths",
        "tag_seed": "safety-accessibility",
    },
    {
        "n": 5,
        "focus": "Approved Documents O, P, Q, S, T (one or two questions each) — overheating risk areas, electrical safety zones in wet areas, window security testing, EV charging in non-domestic buildings, water-closet provision for non-domestic occupancies",
        "tag_seed": "miscellaneous",
    },
]

GENERATION_PROMPT = """You are helping curate CladBench v1, an open evaluation benchmark for AI on the UK and EU built environment.

Your task: generate exactly {n} multiple-choice questions covering this focus area:

  {focus}

Each question must be a valid JSON object on a SINGLE LINE matching this exact schema:

{schema_block}

Reference examples (DO NOT DUPLICATE — your job is to extend coverage with NEW questions):

{few_shot_block}

Hard constraints:
- format MUST be "mcq" with exactly 4 options
- options MUST be 4 plausible distractors with 1 clearly correct answer based on the cited Approved Document
- answer.choice MUST be a single uppercase letter A, B, C, or D
- answer.citation MUST cite a specific document + section + table reference (e.g., "Approved Document L1A 2021, Table 4.1" or "Approved Document B Volume 2 (2019), Section 5.3")
- source.curator MUST be "claude_generated"
- source.review_status MUST be "draft"
- source.curated_at MUST be "2026-06-18"
- source.primary should match answer.citation
- metadata.difficulty MUST be "practitioner"
- metadata.tags MUST include 3-5 relevant tags including a part-X tag (e.g. "part-l")
- IDs MUST follow pattern cb1-01-public-XXXX starting from {next_id:04d} and incrementing
- Use British English in question text ("colour", "metre", "centred", etc.)
- Do NOT generate questions on topics that appear in the reference examples (those are taken)

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble. NO commentary. Just {n} lines of JSON."""


def load_schema_block() -> str:
    """Compact schema-relevant excerpt for the prompt (saves tokens)."""
    return """{
  "id": "cb1-01-public-NNNN",
  "category": 1,
  "category_name": "UK Building Regulations Q&A",
  "format": "mcq",
  "split": "public",
  "question": {"text": "...", "options": ["A...", "B...", "C...", "D..."]},
  "answer": {"choice": "B", "citation": "Approved Document X, Table Y"},
  "grading": {"method": "exact_match", "case_sensitive": false},
  "source": {"primary": "Approved Document X, Table Y", "curator": "claude_generated", "review_status": "draft", "curated_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["...", "...", "part-X"]}
}"""


def few_shot_block(seed_examples: list[dict], k: int = 3) -> str:
    """Pick k diverse seed examples to show Claude the expected style."""
    chosen = [seed_examples[0], seed_examples[8], seed_examples[15]] if len(seed_examples) >= 16 else seed_examples[:k]
    return "\n".join(json.dumps(ex, ensure_ascii=False) for ex in chosen)


def parse_jsonl_response(text: str) -> list[dict]:
    """Extract JSON objects from Claude's response, handling stray prose if any."""
    objects: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip code fences if Claude added them despite instructions
        if line.startswith("```"):
            continue
        try:
            obj = json.loads(line)
            objects.append(obj)
        except json.JSONDecodeError:
            # Try to find a {...} block on the line
            m = re.search(r"\{.*\}", line)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    objects.append(obj)
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
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)} JSON objects from response")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-01-public-{next_id:04d}"
            if obj["id"] in existing_ids:
                print(f"  [skip] {obj['id']} already exists")
                continue
            try:
                validate_example(obj)
            except ValueError as e:
                print(f"  [skip] schema error in {obj['id']}: {e}")
                continue
            existing_ids.add(obj["id"])
            batch_accepted.append(obj)
            next_id += 1
        # Write the batch immediately so a later crash cannot lose this work.
        write_batch(batch_accepted)
        total_accepted += len(batch_accepted)
        print(f"  accepted {len(batch_accepted)}/{batch['n']} from this batch (written)")

    print(f"\nTotal new examples accepted: {total_accepted}")
    print(f"Category 1 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
