"""Generate additional Category 7 (Thermal Comfort Diagnosis) examples via Claude.

Open-answer format with llm_judge_rubric grading.
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

CATEGORY_ID = 7
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 5, "focus": "Office thermal comfort issues — perimeter heating problems, ceiling cassette mismatch, fan-coil zoning, displacement supply, mixed-mode ventilation transitions. UK cities."},
    {"n": 5, "focus": "Domestic overheating under TM59 — new-build flats, retrofit homes, terraced houses with poor purge, top-floor mansards. Mix of orientations and constructions."},
    {"n": 4, "focus": "Educational buildings — primary classrooms (BB101 compliance), university lecture theatres, libraries, mixed-mode school strategies."},
    {"n": 4, "focus": "Healthcare — hospital wards (HTM 03-01 considerations), care homes for elderly, GP surgery waiting rooms. Comfort needs vary by occupant population."},
    {"n": 4, "focus": "Retail and atrium spaces — large glazed shopfronts, double-height retail, multi-storey atrium stack effects, restaurant kitchens spillover."},
    {"n": 3, "focus": "Specialist scenarios — laboratories with fume cupboards, swimming pools (dewpoint and comfort), data centres with overcooling, server rooms inside office floors."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} thermal comfort diagnosis questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "open_answer"
- question.text MUST describe a realistic UK building scenario with comfort complaint, location, building details, system in use, and end with the instruction to diagnose under TM52 (or related CIBSE methodology) and recommend remediation
- answer.text MUST be a structured paragraph response identifying: methodology applied, primary cause, secondary causes, recommended investigation/remediation steps
- answer.citation MUST cite CIBSE TM52, TM59, Guide A, Guide B, Guide H, ISO 7730, BB101, HTM 03-01 or other relevant CIBSE/UK guidance as appropriate
- grading.method MUST be "llm_judge_rubric"
- grading.rubric MUST be exactly 5 criteria each worth 1 point: methodology reference, primary cause identification, secondary cause identification, measurement/investigation recommendation, remediation action recommendation
- source.curator = "claude_generated"; review_status = "draft"; reviewed_at = "2026-06-18"
- difficulty = "practitioner" or "expert"; tags include "thermal-comfort"
- IDs cb1-07-public-XXXX starting from {next_id:04d}
- Use realistic UK locations, real CIBSE methodologies, plausible temperatures and complaints

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-07-public-NNNN",
  "category": 7,
  "category_name": "Thermal Comfort Diagnosis",
  "format": "open_answer",
  "split": "public",
  "question": {"text": "...scenario + 'Diagnose under TM52 and recommend...' instruction..."},
  "answer": {"text": "Methodology... Primary cause... Secondary causes... Recommended: (1)... (2)... (3)...", "citation": "CIBSE TM52 (2013); ..."},
  "grading": {"method": "llm_judge_rubric", "rubric": [{"criterion": "References TM52 methodology by name", "max_points": 1}, {"criterion": "Identifies primary cause correctly", "max_points": 1}, {"criterion": "Identifies secondary cause", "max_points": 1}, {"criterion": "Recommends measurement or modelling step", "max_points": 1}, {"criterion": "Recommends remediation action", "max_points": 1}]},
  "source": {"primary": "CIBSE TM52, ...", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["thermal-comfort", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-07-public-0001", "cb1-07-public-0006", "cb1-07-public-0011"}
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
            obj["id"] = f"cb1-07-public-{next_id:04d}"
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
    print(f"Category 7 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
