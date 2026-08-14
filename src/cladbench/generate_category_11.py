"""Generate additional Category 11 (Net Zero Pathway Reasoning) examples via Claude.

open_answer format with llm_judge_rubric grading (5 criteria).
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

CATEGORY_ID = 11
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 4, "focus": "Commercial real-estate portfolios — REITs, pension funds, life-companies. Offices, mixed-use. Various target years (2030, 2035, 2040, 2050)."},
    {"n": 4, "focus": "Residential — build-to-rent, PRS, student accommodation, social housing, council estates. PAS 2035 framing; SHDF funding context."},
    {"n": 4, "focus": "Public-sector estates — local authorities, schools, libraries, leisure centres, prisons, court buildings. PSDS funding; tight capex; political accountability."},
    {"n": 4, "focus": "Industrial / logistics — cold stores, manufacturing, data centres, ports, warehousing. Process heat, refrigeration, grid capacity, ZEV mandate."},
    {"n": 4, "focus": "Healthcare and care — NHS trusts, private hospitals, care home operators, GP estates. Clinical continuity; 24/7 operation; sterilisation; NHS Net Zero standard."},
    {"n": 4, "focus": "Education and university — primary, secondary, FE colleges, HE campuses, MAT trusts. Term-time access; CIF funding; BB101 ventilation; listed estates."},
    {"n": 3, "focus": "Hospitality, leisure, faith buildings — hotels, restaurants chains, churches, mosques, gyms. Heritage constraints; tourism cycles; voluntary targets."},
    {"n": 3, "focus": "Mixed-use developments and master plans — large schemes spanning residential, retail, office. Embodied carbon at design stage; LETI targets; planning conditions."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} Net Zero Pathway questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "open_answer"
- question.text MUST describe a realistic UK building or portfolio scenario with: stock description, current emissions or EPC, target year (e.g. 2030/2035/2040/2050), capex constraint, and end with an instruction to propose a pathway covering interventions, sequencing, dependencies, and regulatory risks
- answer.text MUST be a structured response with: phase-by-phase plan (typically 3 phases by date), key interventions per phase, dependencies, regulatory risks, and finance approach
- answer.citation MUST cite real UK policy / standards: MEES, EPBD recast, UK Net Zero Strategy, PAS 2035, Future Homes Standard, SHDF, PSDS, SBTi, GRESB, NHS Net Zero, DfE Estate, LETI, BBP, etc.
- grading.method MUST be "llm_judge_rubric"
- grading.rubric MUST be exactly 5 criteria each worth 1 point: target alignment, intervention sequencing, capex realism, dependency awareness, regulatory awareness
- source.curator = "claude_generated"; review_status = "draft"; reviewed_at = "2026-06-18"
- difficulty = "expert" (this is portfolio-level strategy); tags include "net-zero-pathway" + a building-type or sector tag
- IDs cb1-11-public-XXXX starting from {next_id:04d}
- Use realistic UK regulatory context and plausible capex figures

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-11-public-NNNN",
  "category": 11,
  "category_name": "Net Zero Pathway Reasoning",
  "format": "open_answer",
  "split": "public",
  "question": {"text": "...portfolio + target + capex + 'Propose pathway...'"},
  "answer": {"text": "2026-2030 — phase 1 interventions. 2030-2035 — phase 2. 2035-2040 — phase 3. Dependencies: ... Regulatory risks: ...", "citation": "MEES Regulations; UK Net Zero Strategy; ..."},
  "grading": {"method": "llm_judge_rubric", "rubric": [{"criterion": "Target alignment", "max_points": 1}, {"criterion": "Intervention sequencing", "max_points": 1}, {"criterion": "Capex realism", "max_points": 1}, {"criterion": "Dependency awareness", "max_points": 1}, {"criterion": "Regulatory awareness", "max_points": 1}]},
  "source": {"primary": "MEES Regulations; UK Net Zero Strategy; ...", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "expert", "tags": ["net-zero-pathway", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-11-public-0001", "cb1-11-public-0003", "cb1-11-public-0006", "cb1-11-public-0009"}
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
            obj["id"] = f"cb1-11-public-{next_id:04d}"
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
    print(f"Category 11 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
