"""Generate additional Category 12 (Regulatory Cliff-Edge Reasoning) examples via Claude.

short_answer format with exact_match_plus_judge grading.
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

CATEGORY_ID = 12
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 5, "focus": "MEES (Minimum Energy Efficiency Standards) — domestic and non-domestic, England/Wales, current rules and proposed tightening pathway, exemptions, enforcement, penalties."},
    {"n": 5, "focus": "Building Regulations Part L and Future Homes Standard — Approved Documents L 2010/2013/2021/2025, FHS transition, Part F ventilation, Part O overheating, Part S electric-vehicle charging."},
    {"n": 5, "focus": "Building Safety Act 2022 — HRBs, Gateway 1/2/3, Principal Designer/Contractor competence, golden thread, Building Safety Regulator, Safety Case Reports for occupied HRBs."},
    {"n": 5, "focus": "Reporting and disclosure regimes — SECR, ESOS Phase 3/4/5, TCFD/IFRS S2, CSRD applicability to UK groups with EU subsidiaries, Mandatory Climate Disclosures."},
    {"n": 5, "focus": "Energy Performance Certificates — England/Wales/Scotland/NI variants, EPC validity, MEES exemption registrations, DEC, Air-Con TM44, EPB Notification database."},
    {"n": 5, "focus": "Heat networks and F-Gas — Heat Network (Market Framework) Bill 2024, Ofgem heat-network regulation, F-Gas refrigerant phase-down dates and GWPs, HFC quota."},
    {"n": 5, "focus": "Devolved nations — Scotland Section 63, Wales Future Generations Act + EPC trajectory, Northern Ireland EPB regime, planning differences across UK jurisdictions."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} UK regulatory cliff-edge questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "short_answer"
- question.text MUST describe a realistic UK regulatory scenario and ask a specific question about: dates, thresholds, penalties, mechanisms, or applicability
- answer.text MUST give a precise, structured answer with specific dates, numbers, and regulatory citations. Where rules are proposed but not yet enacted, NOTE this explicitly (do not pretend they are law).
- answer.citation MUST cite the specific Act / Regulation / Approved Document by name and year
- grading.method MUST be "llm_judge_rubric"
- grading.rubric MUST be exactly 3 criteria each worth 1 point: factual date/threshold correct, mechanism or scope correct, caveat or trajectory awareness
- source.curator = "claude_generated"; review_status = "draft"; reviewed_at = "2026-06-18"
- difficulty = "practitioner" or "foundation" or "expert"; tags include "regulatory" + a specific regime tag (e.g. "mees", "part-l", "esos")
- IDs cb1-12-public-XXXX starting from {next_id:04d}
- Be carefully accurate about UK regulation status as of June 2026. Many policies are proposed not enacted — flag this. Do NOT invent dates.

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-12-public-NNNN",
  "category": 12,
  "category_name": "Regulatory Cliff-Edge Reasoning",
  "format": "short_answer",
  "split": "public",
  "question": {"text": "...regulatory scenario + specific question..."},
  "answer": {"text": "Specific date / threshold / penalty + mechanism + caveat", "citation": "Specific Act/Regulation/AD with year"},
  "grading": {"method": "llm_judge_rubric", "rubric": [{"criterion": "Factual date/threshold correct", "max_points": 1}, {"criterion": "Mechanism or scope correct", "max_points": 1}, {"criterion": "Caveat or trajectory awareness", "max_points": 1}]},
  "source": {"primary": "Specific Act/Regulation/AD", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["regulatory", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-12-public-0001", "cb1-12-public-0006", "cb1-12-public-0008", "cb1-12-public-0012"}
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
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))

        parsed = parse_jsonl_response(text)
        print(f"  parsed {len(parsed)}")

        batch_accepted: list[dict] = []
        for obj in parsed:
            obj["id"] = f"cb1-12-public-{next_id:04d}"
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
    print(f"Category 12 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
