"""Generate additional Category 3 (IFC Entity Reasoning) examples using Claude.

MCQ format, exact_match grading — same shape as generate_category_1.py.

Usage:
    PYTHONPATH=backend backend/.venv/Scripts/python.exe \
        backend/cladbench/generate_category_3.py
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

CATEGORY_ID = 3
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {
        "n": 4,
        "focus": "Basic IFC4 entity identification — beams (IfcBeam), columns (IfcColumn), slabs (IfcSlab), stairs (IfcStair), ramps (IfcRamp), railings (IfcRailing), curtain walls (IfcCurtainWall), roofs (IfcRoof). One question per entity. Test recognition of canonical entity names.",
    },
    {
        "n": 4,
        "focus": "IFC4 inheritance hierarchies — what entity is the parent of IfcDoor, IfcWindow, IfcSlab, IfcColumn etc.? Tests understanding of IfcBuildingElement subtypes and the supertype chain up through IfcElement → IfcProduct → IfcObject → IfcRoot.",
    },
    {
        "n": 4,
        "focus": "IFC4 objectified relationships — IfcRelConnectsElements (connecting wall to wall), IfcRelAssociatesClassification (linking to Uniclass/Omniclass), IfcRelDefinesByProperties (attaching Pset), IfcRelSpaceBoundary (space-to-element boundary).",
    },
    {
        "n": 4,
        "focus": "IFC4 standardised property sets (Psets) — what properties are in Pset_DoorCommon, Pset_WindowCommon, Pset_SpaceCommon, Pset_ColumnCommon? Test recognition of standardised Pset contents.",
    },
    {
        "n": 4,
        "focus": "IFC4 enumerations — IfcWallTypeEnum (STANDARD, PARTITIONING, ELEMENTEDWALL, SHEAR, etc.), IfcWindowTypeOperationEnum, IfcColumnTypeEnum, IfcRailingTypeEnum. Test recognition of valid enum values.",
    },
    {
        "n": 3,
        "focus": "IFC4 MEP entities — IfcAirTerminal, IfcSpaceHeater, IfcPipeFitting, IfcCableSegment, IfcSwitchingDevice. Test recognition of MEP entity names and their typed enumerations.",
    },
    {
        "n": 2,
        "focus": "IFC versions and exchange formats — IFC4 vs IFC2x3 differences, ifcXML vs ifcJSON vs STEP file format, the role of MVDs (Model View Definitions) and IDM (Information Delivery Manuals).",
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
- options MUST be 4 plausible distractors with 1 clearly correct answer
- answer.choice MUST be a single uppercase letter A, B, C, or D
- answer.citation MUST cite a specific IFC entity / relationship / Pset / Qto / enum, e.g. "buildingSMART IFC4 specification, IfcDoor entity"
- source.curator MUST be "claude_generated"
- source.review_status MUST be "draft"
- source.reviewed_at MUST be "2026-06-18"
- source.primary should match answer.citation
- metadata.difficulty MUST be "practitioner" (or "foundation" for basic entity recognition)
- metadata.tags MUST include 3-5 relevant tags including "ifc" and "ifc4"
- IDs MUST follow pattern cb1-03-public-XXXX starting from {next_id:04d} and incrementing
- IFC entity names follow CamelCase prefix "Ifc" (e.g. IfcWall, IfcBeam, IfcRelAggregates). Get these EXACTLY right.
- Do NOT generate questions on topics that appear in the reference examples

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble. NO commentary. Just {n} lines of JSON."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-03-public-NNNN",
  "category": 3,
  "category_name": "IFC Entity Reasoning",
  "format": "mcq",
  "split": "public",
  "question": {"text": "...", "options": ["A...", "B...", "C...", "D..."]},
  "answer": {"choice": "B", "citation": "buildingSMART IFC4 specification, ..."},
  "grading": {"method": "exact_match", "case_sensitive": false},
  "source": {"primary": "buildingSMART IFC4 specification, ...", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["ifc", "ifc4", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-03-public-0001", "cb1-03-public-0007", "cb1-03-public-0012", "cb1-03-public-0013"}
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
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)} JSON objects from response")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-03-public-{next_id:04d}"
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
    print(f"Category 3 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
