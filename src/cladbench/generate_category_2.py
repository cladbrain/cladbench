"""Generate additional Category 2 (EPC Trajectory) examples using Claude.

Same shape as generate_category_1.py but for short-answer format with
exact_match_plus_judge grading.

Workflow:
1. Load existing examples from data/02_epc_trajectory/public.jsonl as few-shot.
2. For each of 7 focus areas (covering UK housing stock + measure types), call
   Claude to generate 4-6 new EPC trajectory scenarios.
3. Validate each generated example against schema.json.
4. Append valid ones to public.jsonl with curator="claude_generated".

Usage:
    PYTHONPATH=backend backend/.venv/Scripts/python.exe \
        backend/cladbench/generate_category_2.py
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

CATEGORY_ID = 2
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {
        "n": 5,
        "focus": "Pre-1919 housing stock — Victorian and Edwardian terraces and semis. Starting EPC bands F or G. Mix of fabric-only and full retrofit scenarios. Solid wall insulation, sash window replacement, ASHP, MVHR.",
    },
    {
        "n": 5,
        "focus": "Interwar housing (1919-1944) — 1920s and 1930s semis and detacheds. Mostly cavity walls. Starting EPC bands D or E. Mix of cavity wall insulation, loft, boiler swap, controls upgrades.",
    },
    {
        "n": 5,
        "focus": "Post-war housing (1945-1980) — 1950s, 60s, 70s semis, terraces, bungalows. Cavity wall (often unfilled) plus loft. Starting bands D or E. Heat pump retrofits, fabric upgrades, MEES-driven works.",
    },
    {
        "n": 5,
        "focus": "Late 20th-century housing (1980-1999) — already cavity insulated, modest insulation levels. Starting bands C or D. Renewable additions (PV, battery, EV chargers don't count for SAP), heating decarbonisation.",
    },
    {
        "n": 4,
        "focus": "Modern housing (2000-2010) — well-insulated, already EPC C or B. Marginal works: loft top-up, glazing replacement, smart controls, PV addition.",
    },
    {
        "n": 5,
        "focus": "Flats and apartments — mid-rise and high-rise, mix of eras. Includes electric heating to ASHP scenarios, district heating connections, single-aspect heat-loss considerations.",
    },
    {
        "n": 6,
        "focus": "Single-measure scenarios — questions that test a model's understanding of WHICH measure delivers WHICH SAP uplift in isolation. Loft only, glazing only, boiler swap only, PV only, IWI only, EWI only.",
    },
]

GENERATION_PROMPT = """You are helping curate CladBench v1, an open evaluation benchmark for AI on the UK and EU built environment.

Your task: generate exactly {n} EPC trajectory prediction questions covering this focus area:

  {focus}

Each question must be a valid JSON object on a SINGLE LINE matching this exact schema:

{schema_block}

Reference examples (DO NOT DUPLICATE — your job is to extend coverage with NEW scenarios):

{few_shot_block}

Hard constraints:
- format MUST be "short_answer"
- question.text MUST describe a building scenario (era, type, location optional, current EPC band + SAP), proposed retrofit measure(s), and end with: "What is the most likely resulting EPC band? Answer with the band letter (A-G) on the first line, followed by a one-sentence justification."
- answer.text MUST be a SINGLE LETTER A through G (the predicted band)
- answer.rationale MUST be one sentence explaining the SAP point uplift and resulting band
- grading.method MUST be "exact_match_plus_judge"
- grading.rubric MUST include exactly three criteria: "Correct band identified" (max 3), "References specific measures applied" (max 1), "Shows quantitative reasoning" (max 1)
- source.curator MUST be "claude_generated"
- source.review_status MUST be "draft"
- source.reviewed_at MUST be "2026-06-18"
- source.primary should be "SAP 10.2 methodology" or "RdSAP 2012 conventions"
- metadata.difficulty MUST be "practitioner"
- metadata.tags MUST include 3-5 relevant tags
- IDs MUST follow pattern cb1-02-public-XXXX starting from {next_id:04d} and incrementing
- Be realistic about SAP uplifts: typical retrofit measure deliveries are: loft top-up 3-7 pts, cavity wall fill 5-10 pts, IWI 8-12 pts, EWI 10-14 pts, boiler swap 4-7 pts, gas-to-ASHP 8-15 pts (depends on COP), 4kWp PV 8-12 pts, 3 kWh battery 1-2 pts, MVHR + airtightness 5-9 pts, electric storage to ASHP 20-30 pts.
- SAP band cutoffs: A 92+, B 81-91, C 69-80, D 55-68, E 39-54, F 21-38, G 1-20
- Use British English

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble. NO commentary. Just {n} lines of JSON."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-02-public-NNNN",
  "category": 2,
  "category_name": "EPC Trajectory Prediction",
  "format": "short_answer",
  "split": "public",
  "question": {"text": "...scenario... What is the most likely resulting EPC band? Answer with the band letter (A-G) on the first line, followed by a one-sentence justification."},
  "answer": {"text": "C", "rationale": "..."},
  "grading": {"method": "exact_match_plus_judge", "rubric": [{"criterion": "Correct band identified", "max_points": 3}, {"criterion": "References specific measures applied", "max_points": 1}, {"criterion": "Shows quantitative reasoning", "max_points": 1}]},
  "source": {"primary": "SAP 10.2 methodology", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["epc", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-02-public-0001", "cb1-02-public-0005", "cb1-02-public-0008", "cb1-02-public-0011"}
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
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)} JSON objects from response")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-02-public-{next_id:04d}"
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
    print(f"Category 2 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
