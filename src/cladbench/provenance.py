"""Run provenance: what produced a set of scores, and against which dataset.

Defect 3 in the first baseline round was that fourteen answers were corrected in
the dataset during cross-review and the baselines were never re-scored, so every
model stayed graded against superseded ground truth. Nothing in the output files
recorded which version of the dataset they had been scored against, so the drift
was invisible until someone diffed the data by hand.

Every run now writes a manifest beside its JSONL naming the dataset content hash,
the harness version, the token budgets and the judge model. `audit_scoring.py`
compares the recorded hash against the live dataset and fails when they diverge.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from cladbench.budgets import TOKEN_BUDGET

HARNESS_VERSION = "2.0.0"
"""2.0.0 (2026-08-07) — finish_reason surfaced and truncation treated as failure;
non-binding token budgets; failed calls recorded as failures rather than zeros;
judge refuses to return partial verdicts. Results produced by 1.x are not
comparable with 2.x and must not be mixed in one table."""


def dataset_hash(data_root: Path, split: str = "public") -> str:
    """Content hash of the dataset split — stable under file ordering and formatting.

    Hashes the canonical JSON of every example, sorted by id, so a reordered or
    reformatted file with identical content hashes the same, while any change to a
    question, answer, rubric or grading method changes the hash.
    """
    examples = []
    for d in sorted(Path(data_root).iterdir()):
        f = d / f"{split}.jsonl"
        if f.is_file():
            for line in f.open(encoding="utf-8"):
                if line.strip():
                    examples.append(json.loads(line))
    examples.sort(key=lambda e: e["id"])
    h = hashlib.sha256()
    for ex in examples:
        h.update(json.dumps(ex, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def build_manifest(*, model: str, data_root: Path, split: str, categories: list[int],
                   judge_model: str) -> dict:
    return {
        "harness_version": HARNESS_VERSION,
        "dataset_hash": dataset_hash(data_root, split),
        "dataset_split": split,
        "categories": categories,
        "model": model,
        "judge_model": judge_model,
        "token_budgets": dict(TOKEN_BUDGET),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }


def write_manifest(output_path: Path, manifest: dict) -> Path:
    """Write the manifest beside its JSONL, merging with any manifest already there.

    A partial re-run must never erase the provenance of the full run. Before this
    merge existed, running `--categories 1` to repair a handful of questions rewrote
    the manifest wholesale, so a file holding 536 answers across 12 categories ended
    up claiming `categories: [1]` with that repair's token usage as its total. Seven
    manifests were flattened to `categories: [3]` that way before it was noticed, and
    the original usage totals were unrecoverable from the manifests themselves.

    So the merge keeps the union of categories ever run, keeps the earliest
    `generated_at` as the run's origin, and appends each invocation to a `runs` list
    rather than overwriting. Top-level `usage` becomes the sum across runs, which is
    what a reader wants when asking what this file cost to produce.
    """
    path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    merged = dict(manifest)

    if path.exists():
        prev = json.loads(path.read_text(encoding="utf-8"))
        runs = list(prev.get("runs", []))
        if not runs:
            # First merge for a manifest written before this behaviour existed:
            # fold what it recorded into the history so it is not lost.
            runs.append({k: prev.get(k) for k in
                         ("generated_at", "categories", "usage", "harness_version")})
        runs.append({k: manifest.get(k) for k in
                     ("generated_at", "categories", "usage", "harness_version")})

        cats = sorted({c for r in runs for c in (r.get("categories") or [])})
        total: dict[str, float] = {}
        for r in runs:
            for k, v in (r.get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    total[k] = total.get(k, 0) + v

        # Carry forward keys an earlier pass added that this run does not produce
        # (restamp notes, correction records) so a re-run never drops them.
        for k, v in prev.items():
            merged.setdefault(k, v)

        merged.update({
            "categories": cats,
            "runs": runs,
            "usage": total,
            "generated_at": min(r["generated_at"] for r in runs if r.get("generated_at")),
            "last_run_at": manifest.get("generated_at"),
        })

    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return path
