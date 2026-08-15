"""Generate additional Category 10 (Energy Bill Anomaly Detection) examples via Claude.

short_answer format with llm_judge_rubric grading (3-criterion rubric).
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

CATEGORY_ID = 10
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

BATCHES = [
    {"n": 4, "focus": "Office buildings — step-changes in load, BMS schedule overrides, weekend creep, IT/server room growth, sub-metering investigation."},
    {"n": 4, "focus": "Retail and hospitality — extended trading hours impact, refrigeration anomalies in shops, restaurant kitchen extraction left on, heatwave cooling spikes in hotels."},
    {"n": 4, "focus": "Educational and healthcare — schools with summer base load, university lecture halls overcooled, hospitals with chiller faults, care homes with hot water cylinder issues."},
    {"n": 4, "focus": "Industrial/manufacturing — compressed-air leaks, parasitic loads, process-equipment changes, refrigerated warehouse anomalies, machine-tool spindle losses."},
    {"n": 4, "focus": "Commercial / billing anomalies — estimated readings, out-of-contract rates, meter swap errors, half-hourly vs profile-class billing, tenant misallocation, supplier data lag."},
]

GENERATION_PROMPT = """You are helping curate CladBench v1.

Generate exactly {n} energy bill anomaly questions for: {focus}

Schema (one JSON object per line):

{schema_block}

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "short_answer"
- question.text MUST describe a realistic UK building energy scenario with specific numbers (kWh/month, occupancy, weather, time pattern) and end with an instruction to identify the cause + recommend a diagnostic/remediation step
- question.context (optional) MUST be a one-line description of the anomaly pattern (e.g. "Step-change anomaly in electricity only")
- answer.text MUST be a structured response identifying: primary cause hypothesis, supporting evidence in the data, and concrete recommendation (sub-meter, BMS audit, weather-normalisation, contract check, etc.)
- answer.citation MUST cite CIBSE TM22, TM39, TM41, TM44, TM65, Carbon Trust guides, Ofgem rules, or similar
- grading.method MUST be "llm_judge_rubric"
- grading.rubric MUST be exactly 3 criteria each worth 1 point: cause identification, supporting reasoning or rule-out, diagnostic/remediation recommendation
- source.curator = "claude_generated"; review_status = "draft"; curated_at = "2026-06-18"
- difficulty = "practitioner" or "expert" or "foundation"; tags include "energy-anomaly" + a building-type tag
- IDs cb1-10-public-XXXX starting from {next_id:04d}
- Use realistic numbers (kWh/m2/yr ranges that match CIBSE Guide F benchmarks)

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-10-public-NNNN",
  "category": 10,
  "category_name": "Energy Bill Anomaly Detection",
  "format": "short_answer",
  "split": "public",
  "question": {"text": "...scenario + numbers + 'identify cause and recommend action'", "context": "One-line anomaly pattern"},
  "answer": {"text": "Primary cause: ... Evidence: ... Diagnostic: ...", "citation": "CIBSE TM39; ..."},
  "grading": {"method": "llm_judge_rubric", "rubric": [{"criterion": "Identifies primary cause", "max_points": 1}, {"criterion": "Supports reasoning or rules out alternatives", "max_points": 1}, {"criterion": "Recommends diagnostic or remediation step", "max_points": 1}]},
  "source": {"primary": "CIBSE TM39 / ...", "curator": "claude_generated", "review_status": "draft", "curated_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["energy-anomaly", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-10-public-0001", "cb1-10-public-0004", "cb1-10-public-0007", "cb1-10-public-0009"}
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
            obj["id"] = f"cb1-10-public-{next_id:04d}"
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
    print(f"Category 10 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
