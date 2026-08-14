"""Load CladBench JSONL datasets and validate against the schema.

Public surface:
- ``load_jsonl(path)`` — yield validated examples from one JSONL file
- ``load_category(category_id, split, data_root)`` — load all examples for a category
- ``load_all(split, data_root)`` — load all categories for a split
- ``validate_example(example)`` — schema + cross-field validation, raises on error
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = PACKAGE_ROOT / "schema.json"
DATA_ROOT_DEFAULT = PACKAGE_ROOT / "data"

CATEGORY_DIRS = {
    1: "01_uk_building_regs",
    2: "02_epc_trajectory",
    3: "03_ifc_entity_reasoning",
    4: "04_bms_sensor_anomaly",
    5: "05_retrofit_prioritisation",
    6: "06_breeam_credit_eligibility",
    7: "07_thermal_comfort_diagnosis",
    8: "08_cibse_technical_qa",
    9: "09_material_product_specification",
    10: "10_energy_bill_anomaly",
    11: "11_net_zero_pathway",
    12: "12_regulatory_cliff_edge",
}

FORMAT_REQUIRED_ANSWER_FIELDS = {
    "mcq": {"choice"},
    "mcq_with_rationale": {"choice", "rationale"},
    "short_answer": {"text"},
    "ranking": {"ranking"},
    "open_answer": {"text"},
}


def _load_validator() -> Draft202012Validator:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


_VALIDATOR: Draft202012Validator | None = None


def _get_validator() -> Draft202012Validator:
    global _VALIDATOR
    if _VALIDATOR is None:
        _VALIDATOR = _load_validator()
    return _VALIDATOR


def validate_example(example: dict) -> None:
    """Raise ``ValueError`` if the example fails schema or cross-field validation."""
    errors = list(_get_validator().iter_errors(example))
    if errors:
        msgs = [f"{'/'.join(map(str, e.absolute_path)) or 'root'}: {e.message}" for e in errors]
        raise ValueError(f"schema errors in {example.get('id', '<no id>')}: {'; '.join(msgs)}")

    fmt = example["format"]
    required = FORMAT_REQUIRED_ANSWER_FIELDS[fmt]
    missing = required - set(example["answer"])
    if missing:
        raise ValueError(
            f"example {example['id']} format={fmt} missing answer fields: {sorted(missing)}"
        )


def load_jsonl(path: Path | str) -> Iterator[dict]:
    """Yield validated examples from a single JSONL file."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                example = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no} invalid JSON: {e}") from e
            validate_example(example)
            yield example


def load_category(
    category_id: int,
    split: str = "public",
    data_root: Path | str = DATA_ROOT_DEFAULT,
) -> list[dict]:
    """Load all examples for one category + split."""
    if category_id not in CATEGORY_DIRS:
        raise ValueError(f"unknown category {category_id}; valid: {sorted(CATEGORY_DIRS)}")
    if split not in {"public", "holdout"}:
        raise ValueError(f"unknown split {split!r}; valid: public|holdout")
    path = Path(data_root) / CATEGORY_DIRS[category_id] / f"{split}.jsonl"
    if not path.exists():
        return []
    return list(load_jsonl(path))


def load_all(
    split: str = "public",
    data_root: Path | str = DATA_ROOT_DEFAULT,
) -> dict[int, list[dict]]:
    """Load every category for the given split. Returns {category_id: [examples]}."""
    return {cat: load_category(cat, split, data_root) for cat in CATEGORY_DIRS}
