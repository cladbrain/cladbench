"""Output token budgets, by question format.

The governing rule is **non-binding, not merely equal**.

Equal budgets are not sufficient. Give every model 1024 tokens and Claude still
truncates on Cat 12 while GPT-5 does not, because the models differ in how much
they write — so the ceiling still shapes the comparison. A budget only stops
influencing the result once *no model reaches it*. These numbers are therefore
calibrated so the observed truncation rate is 0% for every model in the suite,
and that is re-verified after every run rather than assumed.

The original values (256 for everything except ranking/open_answer at 1024) were
binding for most models on the long-form categories. Combined with a
reasoning-model pad applied inside the same allowance, that produced a 9x output
advantage for one model and invalidated cross-model comparison on Cats 7, 10, 11
and 12. See PHASE_1_CHECKLIST.md, defect 5.

Raising a ceiling never disadvantages a model: one that would have stopped early
still stops early. The cost is tokens, not validity.
"""

from __future__ import annotations

# Calibrated 2026-08-07. Re-run scripts/calibrate_budgets.py if categories,
# prompts, or the model suite change.
#
# Round 1 of calibration FAILED at open_answer=2560: both Opus models truncated on
# cb1-11-public-0038, GPT-5 emitted 3133 output tokens and Gemini 2373. Observed
# worst-case output per format across the probed models, which these values clear
# with margin: mcq 10, mcq_with_rationale 508, short_answer 579, ranking 1220,
# open_answer >3133.
TOKEN_BUDGET: dict[str, int] = {
    "mcq": 512,                 # a letter, but models preamble before it
    # Measured across all 7 models on 302 completed Cat 6/9 answers, the largest output
    # was 687 tokens (Qwen). 32,768 was set to accommodate one pathological Gemini answer
    # on cb1-09-public-0041 and cost far more than it bought: it forced Anthropic into
    # streaming mode, dropping Opus 4.7 from ~47 questions/min to 0.5 — 626 minutes for
    # 297 questions — and made every Cat 6 request to Qwen fail outright on context
    # limits. A single outlier is handled by the per-model clamp in adapters.py, not by
    # raising the ceiling for everyone.
    # 32,768 here is a ceiling, not an expectation. Every model except Gemini finishes
    # these in under 700 tokens; Gemini alone runs past 8,192 on two Cat 9 questions.
    # Each adapter clamps this down to what it can actually accept (adapters.py
    # MAX_OUTPUT_TOKENS), so the generous global value costs the fast models nothing and
    # only Gemini ever draws on it.
    "mcq_with_rationale": 32768,
    "short_answer": 32768,        # Cat 10/12 answers are genuinely multi-part
    "ranking": 4096,            # reasoning plus a trailing RANKING: line
    "open_answer": 8192,        # Cats 7/11 — the long-form planning scenarios
}

DEFAULT_BUDGET = 4096

# Round 3 (2026-08-10): short_answer and mcq_with_rationale raised 2048 -> 4096 after
# the full sweep truncated 6 of 3,752 answers — Gemini x5 (Cats 9, 12) and Opus 4.7 x1
# (Cat 12), all sitting right at the 2048 wall (2,097 and 2,088 tokens used).
#
# The calibration probe missed these because it samples the *longest question* per
# format, assuming the longest question draws the longest answer. It does not: these
# were short questions the model chose to expand on. Question length is not a proxy
# for answer length, and the probe should sample on output, not input.
#
# Only the 6 truncated answers were re-run. Raising a ceiling nobody reached cannot
# change an answer — every other response carried finish_reason == "stop", meaning the
# model stopped because it had finished, not because it ran out of room.


def budget_for(example: dict) -> int:
    """Output token allowance for one example, from its declared format."""
    return TOKEN_BUDGET.get(example.get("format", ""), DEFAULT_BUDGET)
