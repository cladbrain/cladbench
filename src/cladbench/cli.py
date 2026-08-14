"""Command-line interface for CladBench.

Three subcommands:
- ``evaluate``  : run a model against the benchmark and report per-category scores
- ``score``     : recompute scores from saved responses, without calling any model
- ``validate``  : check a JSONL dataset file against schema.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cladbench.adapters import JUDGE_MODEL, build_adapter, anthropic_judge
from cladbench.budgets import budget_for
from cladbench.provenance import build_manifest, write_manifest
from cladbench.loaders import (
    CATEGORY_DIRS,
    DATA_ROOT_DEFAULT,
    load_category,
    load_jsonl,
)
from cladbench.scorers import score


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cladbench",
        description="Open evaluation benchmark for AI on the UK and EU built environment.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # === evaluate ===
    eval_p = subparsers.add_parser("evaluate", help="Score a model on the benchmark.")
    eval_p.add_argument(
        "--model",
        required=True,
        help="Model spec, e.g. 'anthropic:claude-opus-4-7', 'openai:gpt-4o', 'hf:Qwen/Qwen2.5-0.5B-Instruct'.",
    )
    eval_p.add_argument(
        "--categories",
        default="all",
        help="Comma-separated category IDs, or 'all'. Default: all.",
    )
    eval_p.add_argument(
        "--split",
        default="public",
        choices=["public", "holdout"],
        help="Dataset split to evaluate against. Default: public.",
    )
    eval_p.add_argument(
        "--data-root",
        type=Path,
        default=DATA_ROOT_DEFAULT,
        help="Override data directory (default: backend/cladbench/data/).",
    )
    eval_p.add_argument(
        "--output",
        type=Path,
        help="Write per-example raw outputs + scores to this JSONL file.",
    )
    eval_p.add_argument(
        "--limit",
        type=int,
        help="Limit each category to N examples (for smoke testing).",
    )

    # === score ===
    # Re-scores a saved outputs file. The point is that reproducing the published
    # numbers must not require API access to the seven evaluated models: their
    # responses are released, so anyone can recompute the scores from them.
    score_p = subparsers.add_parser(
        "score",
        help="Re-score a saved outputs JSONL without calling any evaluated model.",
    )
    score_p.add_argument(
        "--input", type=Path, required=True,
        help="Outputs JSONL written by `evaluate` (id, response, status per row).",
    )
    score_p.add_argument(
        "--data-root", type=Path, default=DATA_ROOT_DEFAULT,
        help="Dataset directory holding the reference answers.",
    )
    score_p.add_argument(
        "--split", default="public", choices=["public", "holdout"],
        help="Split the outputs were produced against. Default: public.",
    )
    score_p.add_argument(
        "--judge", default="none", choices=["none", "anthropic"],
        help="Judge for rubric-graded rows. 'none' (default) recomputes only the "
             "deterministic methods and reports rubric rows as needing a judge; "
             "'anthropic' re-judges them and requires ANTHROPIC_API_KEY.",
    )
    score_p.add_argument(
        "--output", type=Path,
        help="Write the recomputed per-row scores to this JSONL file.",
    )

    # === validate ===
    val_p = subparsers.add_parser(
        "validate", help="Validate a JSONL dataset file against the schema."
    )
    val_p.add_argument("path", type=Path, help="Path to JSONL file to validate.")

    args = parser.parse_args(argv)

    if args.command == "evaluate":
        return _cmd_evaluate(args)
    if args.command == "score":
        return _cmd_score(args)
    if args.command == "validate":
        return _cmd_validate(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def _parse_category_arg(spec: str) -> list[int]:
    if spec == "all":
        return sorted(CATEGORY_DIRS)
    out = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            cat = int(token)
        except ValueError as e:
            raise SystemExit(f"invalid category id: {token!r}") from e
        if cat not in CATEGORY_DIRS:
            raise SystemExit(f"unknown category id: {cat}")
        out.append(cat)
    return out


JUDGE_METHODS = {"llm_judge_rubric", "exact_match_plus_judge", "spearman_plus_judge"}


def _cmd_score(args) -> int:
    """Recompute scores from saved model responses.

    Deterministic methods (exact_match, band_tolerance) are recomputed from scratch and
    compared against the stored score, so a reader can confirm the published figures
    without an API key of any kind. Rubric-graded rows need a judge; without one they are
    reported as unrecomputed rather than silently carried over from the stored value,
    because passing through a stored score and calling it a recomputation would make this
    command a formality instead of a check.
    """
    rows = [json.loads(line) for line in args.input.open(encoding="utf-8") if line.strip()]

    examples: dict[str, dict] = {}
    for cat in sorted(CATEGORY_DIRS):
        for ex in load_category(cat, args.split, args.data_root):
            examples[ex["id"]] = ex

    judge = None
    if args.judge == "anthropic":
        judge = anthropic_judge
        print(f"Re-judging rubric rows with {JUDGE_MODEL}")

    agree = disagree = skipped = unrecomputed = 0
    deltas: list[tuple[str, float, float]] = []
    out_lines: list[str] = []

    for row in rows:
        ex = examples.get(row["id"])
        if ex is None or row.get("status") != "ok" or row.get("response") is None:
            skipped += 1
            continue
        method = ex["grading"]["method"]
        if method in JUDGE_METHODS and judge is None:
            unrecomputed += 1
            continue
        try:
            result = score(ex, row.get("response", ""), judge_client=judge)
        except Exception as e:                      # a broken row must not stop the pass
            print(f"  [error] {row['id']}: {type(e).__name__}: {e}")
            skipped += 1
            continue
        stored = row.get("score")
        if stored is not None and abs(result.score - stored) > 1e-9:
            disagree += 1
            deltas.append((row["id"], stored, result.score))
        else:
            agree += 1
        out_lines.append(json.dumps(
            {"id": row["id"], "method": result.method, "score": result.score,
             "stored_score": stored, "breakdown": result.breakdown},
            ensure_ascii=False))

    print(f"\n  rows in file            {len(rows)}")
    print(f"  recomputed              {agree + disagree}")
    print(f"  matched stored score    {agree}")
    print(f"  DIFFERED                {disagree}")
    if judge is None:
        print(f"  need a judge to redo    {unrecomputed}   (pass --judge anthropic)")
    print(f"  skipped (not ok/known)  {skipped}")
    for qid, stored, got in deltas[:10]:
        print(f"    {qid}: stored {stored:.4f} -> recomputed {got:.4f}")

    if args.output:
        args.output.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"\n  wrote {args.output}")
    return 1 if disagree else 0


def _cmd_evaluate(args) -> int:
    categories = _parse_category_arg(args.categories)
    print(f"Building adapter: {args.model}")
    adapter = build_adapter(args.model)

    out_lines: list[str] = []
    per_category_scores: dict[int, list[float]] = {cat: [] for cat in categories}
    failures: dict[int, list[str]] = {cat: [] for cat in categories}

    for cat in categories:
        examples = load_category(cat, args.split, args.data_root)
        if args.limit:
            examples = examples[: args.limit]
        if not examples:
            print(f"  [skip] category {cat:02d}: no examples at {args.data_root}")
            continue
        print(f"  category {cat:02d}: {len(examples)} examples")
        for ex in examples:
            prompt = _build_prompt(ex)
            max_tokens = budget_for(ex)
            record: dict = {
                "id": ex["id"],
                "model": adapter.name,
                "max_new_tokens": max_tokens,
            }
            try:
                gen = adapter.generate_full(prompt, max_new_tokens=max_tokens)
                record["finish_reason"] = gen.finish_reason
                record["raw_finish_reason"] = gen.raw_finish_reason
                record["usage"] = gen.usage
                # Raises on truncation or an empty body — an incomplete response is
                # not evidence about the model, so it must never be scored.
                response = gen.require_complete(context=ex["id"])
                result = score(ex, response, judge_client=anthropic_judge)
                record.update(
                    {
                        "status": "ok",
                        "response": response,
                        "score": result.score,
                        "method": result.method,
                        "breakdown": result.breakdown,
                    }
                )
                per_category_scores[cat].append(result.score)
            except Exception as e:
                # Record the failure. Do NOT write a score — a 0.0 here is
                # indistinguishable from a genuine zero and silently depresses the
                # aggregate by an amount that depends on infrastructure, not ability.
                print(f"  [FAILED] {ex['id']}: {type(e).__name__}: {e}")
                record.update(
                    {
                        "status": "failed",
                        "response": locals().get("gen").text if locals().get("gen") else "",
                        "score": None,
                        "method": None,
                        "error": f"{type(e).__name__}: {e}",
                    }
                )
                failures[cat].append(ex["id"])
            if args.output:
                out_lines.append(json.dumps(record, ensure_ascii=False))

    print("\n=== Per-category scores ===")
    for cat, scores in per_category_scores.items():
        if not scores and not failures[cat]:
            continue
        n_fail = len(failures[cat])
        mean = sum(scores) / len(scores) if scores else float("nan")
        flag = f"   [{n_fail} FAILED — excluded]" if n_fail else ""
        print(f"  {cat:02d} {CATEGORY_DIRS[cat]:<40} {mean:.3f}  (n={len(scores)}){flag}")

    overall = [s for scores in per_category_scores.values() for s in scores]
    total_failed = sum(len(v) for v in failures.values())
    if overall:
        print(f"\nOVERALL: {sum(overall)/len(overall):.3f}  (scored n={len(overall)})")
    if total_failed:
        print(
            f"\n!! {total_failed} question(s) FAILED and are excluded from the means above.\n"
            "   This run is INCOMPLETE. Resolve the failures and re-run them before\n"
            "   treating any of these numbers as a result."
        )

    if args.output and out_lines:
        args.output.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"\nWrote raw results to {args.output}")
        manifest = build_manifest(
            model=adapter.name,
            data_root=args.data_root,
            split=args.split,
            categories=categories,
            judge_model=JUDGE_MODEL,
        )
        mpath = write_manifest(args.output, manifest)
        print(f"Wrote run manifest to {mpath.name}")
        print(f"  harness {manifest['harness_version']}  dataset {manifest['dataset_hash'][:12]}")
    return 1 if total_failed else 0


def _build_prompt(example: dict) -> str:
    """Render an example into the prompt format models will see."""
    q = example["question"]
    parts = []
    if "context" in q:
        parts.append(q["context"])
    parts.append(q["text"])
    if example["format"] in {"mcq", "mcq_with_rationale"}:
        for i, opt in enumerate(q["options"]):
            parts.append(f"{chr(ord('A') + i)}) {opt}")
        parts.append(
            "Answer with the single letter only (A, B, C...)."
            if example["format"] == "mcq"
            else "Answer with the letter, then on a new line a brief rationale."
        )
    elif example["format"] == "ranking":
        for i, c in enumerate(q["candidates"]):
            parts.append(f"{chr(ord('a') + i)}) {c}")
        parts.append(
            "You may explain your reasoning. END YOUR RESPONSE with a single "
            "line in the exact form:\n"
            "RANKING: a, b, c, d, e, f\n"
            "where the letters are the candidates in your best-first ranking. "
            "This RANKING line is how your answer will be scored — make sure "
            "it is the very last line of your response."
        )
    return "\n\n".join(parts)


def _cmd_validate(args) -> int:
    path: Path = args.path
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 1
    try:
        examples = list(load_jsonl(path))
    except ValueError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        return 1
    seen_ids: set[str] = set()
    for ex in examples:
        if ex["id"] in seen_ids:
            print(f"duplicate id: {ex['id']}", file=sys.stderr)
            return 1
        seen_ids.add(ex["id"])
    print(f"OK: {len(examples)} examples validated in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
