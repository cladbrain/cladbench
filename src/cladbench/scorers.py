"""Score a model's response against the reference answer.

Public surface:
- ``score(example, response, judge_client=None) -> ScoreResult``
  dispatches on ``example["grading"]["method"]`` and returns a structured score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from scipy.stats import spearmanr

# ============================================================================
# Result object
# ============================================================================


@dataclass
class ScoreResult:
    """Structured scoring result. Always normalised to 0.0–1.0 in ``score``."""

    score: float
    breakdown: dict[str, Any]
    method: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score {self.score} out of range")


# ============================================================================
# Method dispatch
# ============================================================================


JudgeClient = Callable[[str, str, list[dict]], dict]
"""A judge client takes (response, reference, rubric) and returns {criterion: points}.

The default implementation calls Claude via the Anthropic API and asks it to
score the response against the rubric. Tests can substitute a deterministic
client for reproducibility.
"""


def score(
    example: dict,
    response: str,
    *,
    judge_client: JudgeClient | None = None,
) -> ScoreResult:
    """Score one (example, response) pair."""
    method = example["grading"]["method"]
    dispatcher = {
        "exact_match": _score_exact_match,
        "exact_match_plus_judge": _score_exact_match_plus_judge,
        "llm_judge_rubric": _score_llm_judge_rubric,
        "spearman_plus_judge": _score_spearman_plus_judge,
        "band_tolerance": _score_band_tolerance,
    }
    if method not in dispatcher:
        raise ValueError(f"unknown grading method: {method!r}")
    return dispatcher[method](example, response, judge_client=judge_client)


# ============================================================================
# Band tolerance (for judgement categories like EPC band prediction)
# ============================================================================


def _score_band_tolerance(
    example: dict,
    response: str,
    *,
    judge_client: JudgeClient | None = None,
) -> ScoreResult:
    """Score an EPC-band-style answer with tolerance for adjacent bands.

    Used for Cat 2 (EPC Trajectory) where multiple expert-defensible answers
    exist within a +-1 band of the reference. Scoring:
      - exact match (same band): 1.0
      - +-1 band (adjacent): 0.5
      - >=2 bands away: 0.0

    Expected answer is a single letter A-G; response is extracted using the
    same single-letter extractor as exact_match.
    """
    expected = example["answer"]["text"].strip().upper()
    if len(expected) != 1 or expected not in "ABCDEFG":
        # Fall back to exact match if answer is not a clean band letter
        return _score_exact_match(example, response, judge_client=judge_client)

    actual = _extract_single_letter(response, valid="ABCDEFG").upper()

    bands = "ABCDEFG"
    if actual not in bands:
        return ScoreResult(
            score=0.0,
            breakdown={"expected": expected, "actual": actual, "distance": None},
            method="band_tolerance",
        )

    distance = abs(bands.index(actual) - bands.index(expected))
    if distance == 0:
        score_val = 1.0
    elif distance == 1:
        score_val = 0.5
    else:
        score_val = 0.0

    return ScoreResult(
        score=score_val,
        breakdown={
            "expected": expected,
            "actual": actual,
            "distance": distance,
        },
        method="band_tolerance",
    )


# ============================================================================
# Exact match
# ============================================================================


def _normalise(text: str, *, case_sensitive: bool) -> str:
    text = text.strip()
    return text if case_sensitive else text.lower()


def _score_exact_match(
    example: dict,
    response: str,
    *,
    judge_client: JudgeClient | None = None,
) -> ScoreResult:
    case_sensitive = example["grading"].get("case_sensitive", False)
    fmt = example["format"]

    if fmt in {"mcq", "mcq_with_rationale"}:
        expected = example["answer"]["choice"]
        actual = _extract_mcq_choice(response)
    elif fmt == "short_answer":
        expected = example["answer"]["text"]
        expected_clean = expected.strip()
        # Single-letter answers (e.g. EPC bands A-G) need letter extraction
        # because models tend to wrap the letter in "Band C..." or "C\nBecause..."
        if len(expected_clean) == 1 and expected_clean.upper() in "ABCDEFG":
            actual = _extract_single_letter(response, valid="ABCDEFG")
        else:
            actual = response.strip()
    else:
        raise ValueError(f"exact_match not valid for format {fmt}")

    match = _normalise(actual, case_sensitive=case_sensitive) == _normalise(
        expected, case_sensitive=case_sensitive
    )
    return ScoreResult(
        score=1.0 if match else 0.0,
        breakdown={"expected": expected, "actual": actual, "match": match},
        method="exact_match",
    )


def _extract_single_letter(response: str, *, valid: str) -> str:
    """Extract the first single-letter answer (from ``valid``) in the response.

    Used for short-answer questions whose expected answer is a single letter,
    e.g. EPC bands A-G. Strategy mirrors _extract_mcq_choice but with a
    configurable valid set.
    """
    head = response[:200].upper()
    valid_up = valid.upper()
    for i, ch in enumerate(head):
        if ch in valid_up:
            if i == 0 or not head[i - 1].isalnum():
                if i == len(head) - 1 or not head[i + 1].isalnum():
                    return ch
    return response.strip()[:1].upper()


def _extract_mcq_choice(response: str) -> str:
    """Extract a single-letter MCQ choice from a free-form response.

    Strategy: look for an isolated A/B/C/.../H in the first 200 chars. If
    multiple appear, return the first. If none, return the stripped response
    truncated to one character (giving exact_match a chance to fail cleanly).
    """
    head = response[:200].upper()
    for i, ch in enumerate(head):
        if ch in "ABCDEFGH":
            if i == 0 or not head[i - 1].isalnum():
                if i == len(head) - 1 or not head[i + 1].isalnum():
                    return ch
    return response.strip()[:1].upper()


# ============================================================================
# Exact match + judge
# ============================================================================


def _score_exact_match_plus_judge(
    example: dict,
    response: str,
    *,
    judge_client: JudgeClient | None = None,
) -> ScoreResult:
    """Exact-match on the headline answer plus rubric-graded rationale.

    Final score weights exact-match at 60% and rubric at 40%.
    """
    em = _score_exact_match(example, response, judge_client=judge_client)
    rubric_part = _score_llm_judge_rubric(example, response, judge_client=judge_client)
    combined = 0.6 * em.score + 0.4 * rubric_part.score
    return ScoreResult(
        score=combined,
        breakdown={"exact_match": em.breakdown, "rubric": rubric_part.breakdown},
        method="exact_match_plus_judge",
    )


# ============================================================================
# LLM judge rubric
# ============================================================================


def _score_llm_judge_rubric(
    example: dict,
    response: str,
    *,
    judge_client: JudgeClient | None = None,
) -> ScoreResult:
    rubric = example["grading"].get("rubric")
    if not rubric:
        raise ValueError(f"example {example['id']} method=llm_judge_rubric requires rubric")
    if judge_client is None:
        raise NotImplementedError(
            "LLM judge client not provided. Pass a judge_client to score(). "
            "Default Anthropic client is wired up in adapters.AnthropicJudge."
        )
    reference = example["answer"].get("text") or example["answer"].get("rationale") or ""
    # Include reference rationale alongside answer.text so judge sees the full ground truth.
    if example["answer"].get("text") and example["answer"].get("rationale"):
        reference = f"Answer: {example['answer']['text']}\nReference rationale: {example['answer']['rationale']}"
    awarded = judge_client(response, reference, rubric)
    max_total = sum(item["max_points"] for item in rubric)

    # Tolerant lookup — judges sometimes return slightly different casing or
    # truncate the criterion name. Match each rubric item against the
    # awarded keys case-insensitively, taking the closest prefix match.
    awarded_lower = {k.lower(): v for k, v in awarded.items()}

    def _lookup(criterion: str) -> int:
        key = criterion.lower()
        if key in awarded_lower:
            return awarded_lower[key]
        # Try prefix match (judge sometimes shortens)
        for k, v in awarded_lower.items():
            if k.startswith(key[: min(20, len(key))]) or key.startswith(k[: min(20, len(k))]):
                return v
        return 0

    actual_total = sum(min(_lookup(item["criterion"]), item["max_points"]) for item in rubric)
    return ScoreResult(
        score=actual_total / max_total if max_total else 0.0,
        breakdown={"awarded": awarded, "max_total": max_total, "actual_total": actual_total},
        method="llm_judge_rubric",
    )


# ============================================================================
# Spearman + judge (ranking)
# ============================================================================


def _score_spearman_plus_judge(
    example: dict,
    response: str,
    *,
    judge_client: JudgeClient | None = None,
) -> ScoreResult:
    """For ranking: 70% Spearman rank correlation, 30% rubric (sequencing logic)."""
    expected = example["answer"]["ranking"]
    actual = _extract_ranking(response, n=len(expected))
    if len(actual) != len(expected):
        spearman = 0.0
    else:
        order_expected = [expected.index(c) for c in expected]
        order_actual = [expected.index(c) if c in expected else -1 for c in actual]
        if -1 in order_actual:
            spearman = 0.0
        else:
            rho, _ = spearmanr(order_expected, order_actual)
            spearman = max(0.0, float(rho))  # clamp negative correlation to 0

    if example["grading"].get("rubric") and judge_client is not None:
        rubric_part = _score_llm_judge_rubric(example, response, judge_client=judge_client)
        rubric_score = rubric_part.score
    else:
        rubric_score = 0.0
    combined = 0.7 * spearman + 0.3 * rubric_score
    return ScoreResult(
        score=combined,
        breakdown={"spearman": spearman, "rubric": rubric_score, "expected": expected, "actual": actual},
        method="spearman_plus_judge",
    )


def _extract_ranking(response: str, *, n: int) -> list[str]:
    """Pull an ordered list of single-letter labels from the response.

    Strategy:
    1. Look for an explicit ``RANKING:`` line (the prompt asks the model to
       end with one). If present, take its letters.
    2. Otherwise, look at the LAST line that contains at least n unique
       letters from a-h with comma/space/arrow separators.
    3. Fall back to a global scan that takes the first n unique letters,
       but only from substrings that look like ranking sequences (letters
       separated by commas, spaces, or arrows — not letters embedded in
       words).
    """
    import re

    valid = "abcdefgh"

    # Strategy 1: explicit RANKING: tag
    for line in reversed(response.splitlines()):
        m = re.search(r"RANKING\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        if m:
            letters = re.findall(r"[a-h]", m.group(1).lower())
            seen: list[str] = []
            for c in letters:
                if c not in seen:
                    seen.append(c)
                if len(seen) >= n:
                    break
            if len(seen) >= n:
                return seen[:n]

    # Strategy 2: last line with N unique letters separated by ranking-style
    # punctuation (comma, semicolon, arrow, gt-sign, space).
    for line in reversed(response.splitlines()):
        tokens = re.findall(r"(?<![a-zA-Z])([a-h])(?![a-zA-Z])", line.lower())
        seen = []
        for c in tokens:
            if c not in seen:
                seen.append(c)
        if len(seen) >= n:
            return seen[:n]

    # Strategy 3: global scan of standalone letters only
    tokens = re.findall(r"(?<![a-zA-Z])([a-h])(?![a-zA-Z])", response.lower())
    seen = []
    for c in tokens:
        if c not in seen:
            seen.append(c)
        if len(seen) >= n:
            break
    return seen
