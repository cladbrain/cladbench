"""Multi-AI cross-review of CladBench questions.

Sends each question to three frontier reviewers (Claude Opus 4.7, GPT-5,
Gemini 2.5 Pro) and asks each to return a structured JSON verdict on
correctness, citation, and ambiguity.

Outputs:
- backend/cladbench/data/cross_review_results.jsonl  — per-question per-reviewer raw verdicts
- docs/cladbench_review/flagged_questions.csv         — summary of items needing human spot-check
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)

DATA_ROOT = REPO_ROOT / "backend" / "cladbench" / "data"
RESULTS_PATH = DATA_ROOT / "cross_review_results.jsonl"
FLAGGED_PATH = REPO_ROOT / "docs" / "cladbench_review" / "flagged_questions.csv"

REVIEW_PROMPT = """You are a domain reviewer for an open evaluation benchmark on the UK and EU built environment.

Below is a single benchmark question along with the stored reference answer and citation. Your job is to independently verify it. Be sceptical: assume the question may be wrong. Read it carefully against your knowledge of UK regulations, CIBSE guidance, BREEAM, EPC methodology, IFC, BMS, embodied carbon, and net-zero policy.

CATEGORY: {category_name}
FORMAT: {format}
GRADING METHOD: {grading_method}

QUESTION:
{question_text}

{options_block}{candidates_block}REFERENCE ANSWER:
{reference_answer}

CITATION CLAIMED:
{citation}

Respond with EXACTLY one JSON object, no prose before or after, with these fields:
{{
  "answer_correct": true | false,
  "proposed_answer": "string — if answer_correct is false, what you believe the correct answer is. Otherwise empty string.",
  "citation_valid": true | false,
  "citation_notes": "string — brief reason if invalid, otherwise empty",
  "ambiguity": "low" | "medium" | "high",
  "ambiguity_notes": "string — brief reason if medium/high, otherwise empty",
  "overall_notes": "string — anything else a reviewer should see, otherwise empty"
}}"""


def format_options(q: dict, fmt: str) -> str:
    if fmt in {"mcq", "mcq_with_rationale"}:
        opts = q.get("options", [])
        lines = ["OPTIONS:"]
        for i, opt in enumerate(opts):
            lines.append(f"  {chr(ord('A') + i)}) {opt}")
        return "\n".join(lines) + "\n\n"
    return ""


def format_candidates(q: dict, fmt: str) -> str:
    if fmt == "ranking":
        cands = q.get("candidates", [])
        lines = ["RANKING CANDIDATES (best-first order is the reference answer):"]
        for i, c in enumerate(cands):
            lines.append(f"  {chr(ord('a') + i)}) {c}")
        return "\n".join(lines) + "\n\n"
    return ""


def reference_answer_str(ex: dict) -> str:
    fmt = ex["format"]
    ans = ex["answer"]
    if fmt in {"mcq", "mcq_with_rationale"}:
        s = f"choice: {ans.get('choice', '?')}"
        if ans.get("rationale"):
            s += f"\nrationale: {ans['rationale']}"
        return s
    if fmt == "ranking":
        return f"ranking (best-first): {', '.join(ans.get('ranking', []))}"
    return ans.get("text", "")


def build_prompt(ex: dict) -> str:
    return REVIEW_PROMPT.format(
        category_name=ex["category_name"],
        format=ex["format"],
        grading_method=ex["grading"]["method"],
        question_text=ex["question"]["text"],
        options_block=format_options(ex["question"], ex["format"]),
        candidates_block=format_candidates(ex["question"], ex["format"]),
        reference_answer=reference_answer_str(ex),
        citation=ex["answer"].get("citation", "(no citation provided)"),
    )


def parse_verdict(text: str) -> dict | None:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    # Normalise booleans (some models return strings)
    for k in ("answer_correct", "citation_valid"):
        if isinstance(v.get(k), str):
            v[k] = v[k].strip().lower() in ("true", "yes", "1")
    return v


# ----------------------------- Reviewers ---------------------------------- #

def review_anthropic(prompt: str, model: str = "claude-opus-4-7") -> dict | None:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=model, max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if hasattr(b, "text"))
            return parse_verdict(text)
        except Exception:
            time.sleep(2 ** attempt)
    return None


def review_openai(prompt: str, model: str = "gpt-5") -> dict | None:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=model,
                max_completion_tokens=2048,
                reasoning_effort="minimal",
                messages=[{"role": "user", "content": prompt}],
            )
            return parse_verdict(r.choices[0].message.content or "")
        except Exception:
            time.sleep(2 ** attempt)
    return None


def review_gemini(prompt: str, model: str = "gemini-2.5-pro") -> dict | None:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GOOGLE_GEMINI_API_KEY"])
    for attempt in range(3):
        try:
            r = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=900, temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=128),
                ),
            )
            return parse_verdict(r.text or "")
        except Exception:
            time.sleep(2 ** attempt)
    return None


REVIEWERS = [
    ("anthropic:claude-opus-4-7", review_anthropic),
    ("openai:gpt-5", review_openai),
    ("google:gemini-2.5-pro", review_gemini),
]


# ----------------------------- Main pipeline ------------------------------ #

def iter_examples():
    for cat_dir in sorted(DATA_ROOT.iterdir()):
        if not cat_dir.is_dir():
            continue
        jsonl = cat_dir / "public.jsonl"
        if not jsonl.exists():
            continue
        for line in jsonl.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def decide_flag(verdicts_by_reviewer: dict[str, dict | None]) -> dict:
    valid = [v for v in verdicts_by_reviewer.values() if v is not None]
    n = len(valid)
    if n == 0:
        return {"flag": True, "reason": "all_reviewers_failed"}
    correct = sum(1 for v in valid if v.get("answer_correct"))
    cite = sum(1 for v in valid if v.get("citation_valid"))
    high_amb = sum(1 for v in valid if v.get("ambiguity") == "high")
    reasons = []
    if correct < n:
        reasons.append(f"answer_disagreement_{correct}of{n}")
    if cite < (n - 1):
        reasons.append(f"citation_invalid_{cite}of{n}")
    if high_amb >= 2:
        reasons.append("high_ambiguity")
    if not reasons:
        return {"flag": False, "reason": "passed"}
    return {"flag": True, "reason": ";".join(reasons)}


def review_one(ex: dict) -> dict:
    """Run all 3 reviewers in parallel for a single question."""
    from concurrent.futures import ThreadPoolExecutor

    prompt = build_prompt(ex)
    verdicts: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=3) as inner:
        futs = {inner.submit(fn, prompt): name for name, fn in REVIEWERS}
        for fut in futs:
            verdicts[futs[fut]] = fut.result()
    decision = decide_flag(verdicts)
    return {
        "id": ex["id"],
        "category": ex["category"],
        "format": ex["format"],
        "verdicts": verdicts,
        "decision": decision,
    }


def main() -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    # Resume support: read already-completed IDs from results file
    done_ids: set[str] = set()
    if RESULTS_PATH.exists():
        with RESULTS_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    done_ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
        print(f"Resuming — {len(done_ids)} examples already cross-reviewed")

    examples = [ex for ex in iter_examples() if ex["id"] not in done_ids]
    total = len(examples)
    print(f"To process: {total} examples (8 concurrent questions x 3 parallel reviewers each)")

    write_lock = Lock()
    out = RESULTS_PATH.open("a", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=8) as outer:
        futs = {outer.submit(review_one, ex): ex for ex in examples}
        i = 0
        for fut in as_completed(futs):
            i += 1
            record = fut.result()
            with write_lock:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
            tag = "FLAG" if record["decision"]["flag"] else "PASS"
            print(f"[{i:>3}/{total}] {record['id']}  {tag}  {record['decision']['reason']}", flush=True)
    out.close()

    # Build flagged CSV summary
    flagged_rows: list[dict] = []
    with RESULTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not r["decision"]["flag"]:
                continue
            # Find a proposed answer from any disagreeing reviewer
            proposed = ""
            for vname, v in r["verdicts"].items():
                if v and not v.get("answer_correct") and v.get("proposed_answer"):
                    proposed = f"{vname}: {v['proposed_answer']}"
                    break
            flagged_rows.append({
                "id": r["id"],
                "category": r["category"],
                "format": r["format"],
                "reason": r["decision"]["reason"],
                "proposed_answer_first": proposed,
                "verdicts_summary": json.dumps({
                    k: {kk: vv.get(kk) for kk in ("answer_correct", "citation_valid", "ambiguity") if vv}
                    for k, vv in r["verdicts"].items()
                    if vv is not None
                }, ensure_ascii=False),
            })

    FLAGGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FLAGGED_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "format", "reason", "proposed_answer_first", "verdicts_summary"])
        writer.writeheader()
        writer.writerows(flagged_rows)
    print(f"\nFlagged: {len(flagged_rows)} of {sum(1 for _ in RESULTS_PATH.open(encoding='utf-8'))} reviewed")
    print(f"Wrote {FLAGGED_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
