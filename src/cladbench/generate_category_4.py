"""Generate additional Category 4 (BMS Sensor Anomaly Classification) examples.

Same shape as generate_category_1.py but with the standardised 5-option set:
A) Sensor failure (stuck or non-responsive reading)
B) Calibration drift (sensor reads consistently offset)
C) Setpoint change (operational, not a fault)
D) Control loop instability (oscillation or hunting)
E) Normal operation

Usage:
    PYTHONPATH=backend backend/.venv/Scripts/python.exe \
        backend/cladbench/generate_category_4.py
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

CATEGORY_ID = 4
CATEGORY_PATH = DATA_ROOT_DEFAULT / CATEGORY_DIRS[CATEGORY_ID] / "public.jsonl"
MODEL = "claude-opus-4-7"

STANDARD_OPTIONS = [
    "Sensor failure (stuck or non-responsive reading)",
    "Calibration drift (sensor reads consistently offset)",
    "Setpoint change (operational, not a fault)",
    "Control loop instability (oscillation or hunting)",
    "Normal operation",
]

BATCHES = [
    {
        "n": 5,
        "focus": "AHU (air handling unit) faults — supply/return temp sensors, mixing damper actuators, chilled water valves, fan VFDs, filter pressure differentials. Realistic 24-hour or weekly observation profiles.",
    },
    {
        "n": 5,
        "focus": "Boiler and chiller plant — supply/return temperature sensors, flow meters, compressor cycling, boiler firing rate, condenser water loops. Both fault cases and normal-operation cases.",
    },
    {
        "n": 5,
        "focus": "Zone-level control — VAV box airflow oscillation, fan-coil unit valve hunting, chilled beam heating/cooling alternation, electric trim heater stuck on, zone temperature sensor faults.",
    },
    {
        "n": 5,
        "focus": "Indoor air quality (IAQ) — CO2 sensor faults, humidity sensor calibration, VOC sensor saturation, occupancy-driven ventilation behaviour (normal vs faulty demand-controlled ventilation).",
    },
    {
        "n": 5,
        "focus": "Energy metering — gas meter sudden step changes (could be tariff change OR fault), electricity submeter constant readings, water meter zero flow during occupied hours, half-hourly data anomalies.",
    },
    {
        "n": 5,
        "focus": "Specialist applications — data centre CRAC overcooling, kitchen extract fan continuous operation overnight, laboratory fume cupboard pressure sensor faults, swimming pool plantroom dewpoint sensors.",
    },
    {
        "n": 5,
        "focus": "Mixed scenarios with realistic operator confusion — setpoint changes that LOOK like faults, calibration drift gradually emerging, normal operation during atypical weather, holiday-period unusual patterns.",
    },
]

GENERATION_PROMPT = """You are helping curate CladBench v1, an open evaluation benchmark for AI on the UK and EU built environment.

Your task: generate exactly {n} BMS sensor anomaly classification questions covering this focus area:

  {focus}

Each question must be a valid JSON object on a SINGLE LINE matching this exact schema:

{schema_block}

Every question MUST use this EXACT set of 5 options, in this order:
1. "Sensor failure (stuck or non-responsive reading)"
2. "Calibration drift (sensor reads consistently offset)"
3. "Setpoint change (operational, not a fault)"
4. "Control loop instability (oscillation or hunting)"
5. "Normal operation"

answer.choice MUST be A, B, C, D, or E.

Reference examples (DO NOT DUPLICATE):

{few_shot_block}

Hard constraints:
- format MUST be "mcq" with EXACTLY the 5 standard options above
- question.text MUST describe a realistic 24-hour or multi-day BMS observation
- answer.citation MUST cite CIBSE Guide H, Guide B, Guide F, or a similar relevant CIBSE/BSRIA reference
- source.curator MUST be "claude_generated"
- source.review_status MUST be "draft"
- source.reviewed_at MUST be "2026-06-18"
- metadata.difficulty MUST be "practitioner"
- metadata.tags MUST include 3-5 relevant tags including "bms"
- IDs MUST follow cb1-04-public-XXXX starting from {next_id:04d}
- Distribute the correct answers across A-E in roughly equal proportions over the batch — do not over-pick a single category

Output: exactly {n} JSON objects, one per line. NO markdown fences. NO preamble."""


def load_schema_block() -> str:
    return """{
  "id": "cb1-04-public-NNNN",
  "category": 4,
  "category_name": "BMS Sensor Anomaly Classification",
  "format": "mcq",
  "split": "public",
  "question": {"text": "...scenario describing 24h+ BMS observation...", "options": ["Sensor failure (stuck or non-responsive reading)", "Calibration drift (sensor reads consistently offset)", "Setpoint change (operational, not a fault)", "Control loop instability (oscillation or hunting)", "Normal operation"]},
  "answer": {"choice": "A", "citation": "CIBSE Guide H — ..."},
  "grading": {"method": "exact_match", "case_sensitive": false},
  "source": {"primary": "CIBSE Guide H", "curator": "claude_generated", "review_status": "draft", "reviewed_at": "2026-06-18"},
  "metadata": {"difficulty": "practitioner", "tags": ["bms", "..."]}
}"""


def few_shot_block(seed_examples: list[dict]) -> str:
    chosen_ids = {"cb1-04-public-0001", "cb1-04-public-0005", "cb1-04-public-0008", "cb1-04-public-0012"}
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
            obj["id"] = f"cb1-04-public-{next_id:04d}"
            if obj["id"] in existing_ids:
                continue
            # Enforce standard options regardless of what Claude returned
            obj["question"]["options"] = STANDARD_OPTIONS
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
    print(f"Category 4 now has {len(seed_examples) + total_accepted} total examples")


if __name__ == "__main__":
    main()
