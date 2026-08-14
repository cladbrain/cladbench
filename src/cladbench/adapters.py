"""Model adapters. One adapter per model provider.

Adapters expose ``generate_full()``, which returns a :class:`GenerationResult`
carrying the response text *and why generation stopped*. ``generate()`` remains
as a text-only convenience wrapper.

Why the finish reason matters: until 2026-08-07 these adapters returned a bare
string, so a response cut off at the token ceiling was indistinguishable from a
complete one. It was then graded as if the model had chosen to stop, and the
missing content scored zero. On Cat 12 that silently truncated 88% of Claude
Opus 4.7's answers while leaving GPT-5 — which was being given a 9x larger
budget — untouched, and the resulting gap was nearly published as a finding
about regulatory reasoning. Truncation is now surfaced and treated as a failed
call, never as a score.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from cladbench.failures import TERMINAL, classify

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=False)


class TruncatedResponse(RuntimeError):
    """Generation hit the output ceiling. The response is incomplete and unscorable."""


# DETERMINISM — the paper's claim here is not achievable, and must be reworded
# -----------------------------------------------------------------------------
# Paper section 4.1 states "All adapters use temperature 0.0". That was never true, and
# it cannot be made true:
#
#   Together, Gemini      temperature=0.0 accepted        -> greedy
#   HuggingFace           do_sample=False                 -> greedy
#   OpenAI (gpt-4o)       temperature=0.0 accepted        -> greedy
#   OpenAI (gpt-5, o-*)   rejects temperature != 1        -> CANNOT be pinned
#   Anthropic (opus 4.x)  temperature deprecated, 400s    -> CANNOT be pinned
#   The judge (opus 4.7)  same                            -> CANNOT be pinned
#
# So three of the evaluated models and every rubric verdict are sampled, not greedy.
# Run-to-run variance is therefore real rather than hypothetical, and it applies to
# the judge as well as the models. It is measured by scripts/check_determinism.py
# and reported, instead of being claimed away in the methodology section.


@dataclass
class GenerationResult:
    """A model response plus the metadata needed to know whether to trust it."""

    text: str
    finish_reason: str  # normalised: "stop" | "length" | "other"
    raw_finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"

    def require_complete(self, context: str = "") -> str:
        """Return the text, or raise if the response is unusable."""
        if self.truncated:
            raise TruncatedResponse(
                f"response hit the output ceiling ({self.raw_finish_reason!r}) "
                f"and is incomplete{': ' + context if context else ''}"
            )
        if not self.text.strip():
            raise RuntimeError(
                f"model returned an empty response (finish_reason="
                f"{self.raw_finish_reason!r}){': ' + context if context else ''}"
            )
        return self.text


def _normalise_finish(raw: str) -> str:
    """Map provider-specific finish reasons onto stop / length / other."""
    r = (raw or "").lower()
    if r in {"length", "max_tokens", "maxtokens", "max_output_tokens", "model_length"}:
        return "length"
    if r in {"stop", "end_turn", "stop_sequence", "eos", "complete"}:
        return "stop"
    return "other"


class ModelAdapter(ABC):
    """Abstract base class. Subclass per provider."""

    name: str

    MAX_OUTPUT_TOKENS: int = 8192
    """Largest output allowance this model will accept.

    Budgets in `cladbench.budgets` are set by what the most verbose model needs, which
    is not what the smallest model can accept. Raising `mcq_with_rationale` to 32,768 —
    to fit one unusually long Gemini answer — made every Cat 6 request to Qwen 2.5 7B
    fail with `422: inputs tokens + max_new_tokens must be <= model limit`, because that
    model's whole context is 32k. A budget chosen for one model must never make another
    model unrunnable, so each adapter declares its own ceiling and the request is clamped
    to it. `GenerationResult.usage['budget_clamped_from']` records when that happens, so
    a truncation caused by a model's own limit stays visible rather than looking like a
    harness default."""

    def _clamp(self, max_new_tokens: int) -> tuple[int, int | None]:
        if max_new_tokens > self.MAX_OUTPUT_TOKENS:
            return self.MAX_OUTPUT_TOKENS, max_new_tokens
        return max_new_tokens, None

    @abstractmethod
    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        """Return the response plus its finish reason. Deterministic by default."""
        raise NotImplementedError

    def generate(self, prompt: str, *, max_new_tokens: int = 256) -> str:
        """Text-only convenience wrapper. Raises if the response is truncated or empty."""
        return self.generate_full(prompt, max_new_tokens=max_new_tokens).require_complete()


# ============================================================================
# Anthropic
# ============================================================================


class AnthropicAdapter(ModelAdapter):
    """Calls Claude via the Anthropic SDK."""

    # Deliberately at the streaming threshold, not above it. Anything larger forces the
    # SDK into streaming mode, which dropped Opus 4.7 from ~47 questions/min to 0.5 —
    # 626 minutes for 297 questions. No Claude model has ever needed more than 519
    # output tokens on a rubric question, so this ceiling costs nothing and keeps the
    # fast non-streaming path.
    MAX_OUTPUT_TOKENS = 8192

    def __init__(self, model: str = "claude-opus-4-7"):
        from anthropic import Anthropic  # local import to keep import-time light

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment / .env")
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.name = f"anthropic:{model}"

    # Above this ceiling the SDK refuses a non-streaming request ("Streaming is
    # required for operations that may take longer than 10 minutes"), because a
    # large max_tokens could in principle run past the HTTP timeout. Budgets were
    # raised to 32768 to accommodate one pathologically verbose Gemini answer, which
    # silently made every Anthropic call in that format fail until this was added.
    STREAM_ABOVE = 8192

    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        max_new_tokens, clamped_from = self._clamp(max_new_tokens)
        # No temperature: it is deprecated on this model family and the API rejects
        # the parameter outright ("`temperature` is deprecated for this model").
        # See the DETERMINISM note above — decoding here cannot be pinned.
        kwargs = {
            "model": self.model,
            "max_tokens": max_new_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if max_new_tokens > self.STREAM_ABOVE:
            with self.client.messages.stream(**kwargs) as stream:
                msg = stream.get_final_message()
        else:
            msg = self.client.messages.create(**kwargs)
        raw = getattr(msg, "stop_reason", "") or ""
        usage = {}
        if getattr(msg, "usage", None):
            usage = {"input_tokens": getattr(msg.usage, "input_tokens", None),
                     "output_tokens": getattr(msg.usage, "output_tokens", None)}
        return GenerationResult(
            text="".join(block.text for block in msg.content if hasattr(block, "text")),
            finish_reason=_normalise_finish(raw),
            raw_finish_reason=raw,
            usage={**usage, "budget_clamped_from": clamped_from},
        )


# ============================================================================
# OpenAI
# ============================================================================


class OpenAIAdapter(ModelAdapter):
    """Calls GPT models via the OpenAI SDK."""

    MAX_OUTPUT_TOKENS = 32768

    PER_MODEL_MAX: dict[str, int] = {
        # GPT-4o accepts at most 16,384 completion tokens. The provider-level ceiling
        # above is right for gpt-5 and too high here, so a short_answer budget of 32,768
        # is rejected outright with a 400 rather than being silently truncated. That
        # surfaced as an aborted run when Category 2 was re-run in August 2026; the
        # failure classifier correctly called it terminal instead of retrying it five
        # times, but the request should never have been sent. A ceiling is a property of
        # the model, not of the provider.
        "gpt-4o": 16384,
        "gpt-4o-mini": 16384,
        "gpt-4-turbo": 4096,
    }

    def __init__(self, model: str = "gpt-4o"):
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment / .env")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.name = f"openai:{model}"
        limit = self.PER_MODEL_MAX.get(model)
        if limit is not None:
            # Shadow the class attribute for this instance only.
            self.MAX_OUTPUT_TOKENS = limit

    # Reasoning models bill internal reasoning against the same completion budget,
    # so they need headroom *on top of* the shared output allowance. This pad buys
    # room for reasoning only — it must never leave a reasoning model with a larger
    # allowance for visible output than every other model gets, which is exactly
    # the bug that invalidated the first baseline round.
    REASONING_PAD = 4096

    def _is_reasoning_model(self) -> bool:
        return self.model.startswith(("gpt-5", "o1", "o3", "o4"))

    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        max_new_tokens, clamped_from = self._clamp(max_new_tokens)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self._is_reasoning_model():
            kwargs["max_completion_tokens"] = max_new_tokens + self.REASONING_PAD
            kwargs["reasoning_effort"] = "minimal"
            # Reasoning models reject temperature != 1; they cannot be made greedy.
            # This is a real, disclosable limit on reproducibility, not an oversight.
        else:
            kwargs["max_completion_tokens"] = max_new_tokens
            kwargs["temperature"] = 0.0  # was omitted until 2026-08-07
        resp = self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        raw = getattr(choice, "finish_reason", "") or ""
        usage = {}
        if getattr(resp, "usage", None):
            usage = {"prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                     "completion_tokens": getattr(resp.usage, "completion_tokens", None)}
            details = getattr(resp.usage, "completion_tokens_details", None)
            if details is not None:
                usage["reasoning_tokens"] = getattr(details, "reasoning_tokens", None)
        return GenerationResult(
            text=choice.message.content or "",
            finish_reason=_normalise_finish(raw),
            raw_finish_reason=raw,
            usage={**usage, "budget_clamped_from": clamped_from},
        )


# ============================================================================
# Together AI (open-source models via OpenAI-compatible API)
# ============================================================================


class TogetherAdapter(ModelAdapter):
    """Calls open-source models hosted on Together AI via OpenAI-compatible API."""

    # Qwen 2.5 7B Turbo has a 32k total context on Together; asking for 32,768 output
    # tokens leaves no room for the prompt and the request is rejected outright.
    MAX_OUTPUT_TOKENS = 4096

    def __init__(self, model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"):
        from openai import OpenAI

        api_key = os.environ.get("TOGETHER_API_KEY")
        if not api_key:
            raise RuntimeError("TOGETHER_API_KEY not set in environment / .env")
        self.client = OpenAI(api_key=api_key, base_url="https://api.together.xyz/v1")
        self.model = model
        self.name = f"together:{model}"

    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        import time

        max_new_tokens, clamped_from = self._clamp(max_new_tokens)
        last_exc = None
        for attempt in range(4):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_new_tokens,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                choice = resp.choices[0]
                raw = getattr(choice, "finish_reason", "") or ""
                usage = {}
                if getattr(resp, "usage", None):
                    usage = {"prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                             "completion_tokens": getattr(resp.usage, "completion_tokens", None)}
                return GenerationResult(
                    text=choice.message.content or "",
                    finish_reason=_normalise_finish(raw),
                    raw_finish_reason=raw,
                    usage={**usage, "budget_clamped_from": clamped_from},
                )
            except Exception as e:
                last_exc = e
                time.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]


# ============================================================================
# Google Gemini
# ============================================================================


class GeminiAdapter(ModelAdapter):
    """Calls Gemini via the google-genai SDK."""

    MAX_OUTPUT_TOKENS = 32768

    def __init__(self, model: str = "gemini-2.5-pro"):
        from google import genai

        api_key = os.environ.get("GOOGLE_GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_GEMINI_API_KEY not set in environment / .env")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.name = f"google:{model}"

    # Gemini bills internal "thinking" against max_output_tokens. Same rule as the
    # OpenAI reasoning pad: this buys room for thinking, not extra visible output.
    THINKING_BUDGET = 128

    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        import time

        max_new_tokens, clamped_from = self._clamp(max_new_tokens)
        from google.genai import types

        output_budget = max_new_tokens + self.THINKING_BUDGET

        last_exc = None
        for attempt in range(4):
            try:
                resp = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=output_budget,
                        temperature=0.0,
                        thinking_config=types.ThinkingConfig(thinking_budget=self.THINKING_BUDGET),
                    ),
                )
                raw = ""
                cands = getattr(resp, "candidates", None) or []
                if cands:
                    fr = getattr(cands[0], "finish_reason", "")
                    raw = getattr(fr, "name", None) or str(fr or "")
                usage = {}
                um = getattr(resp, "usage_metadata", None)
                if um is not None:
                    usage = {"prompt_tokens": getattr(um, "prompt_token_count", None),
                             "completion_tokens": getattr(um, "candidates_token_count", None),
                             "thinking_tokens": getattr(um, "thoughts_token_count", None)}
                return GenerationResult(
                    text=resp.text or "",
                    finish_reason=_normalise_finish(raw),
                    raw_finish_reason=raw,
                    usage={**usage, "budget_clamped_from": clamped_from},
                )
            except Exception as e:
                last_exc = e
                time.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]


# ============================================================================
# Hugging Face (local / cloud-hosted)
# ============================================================================


class OpenAICompatibleAdapter(ModelAdapter):
    """Any provider exposing an OpenAI-compatible /chat/completions endpoint.

    Used for the two neutral judges. Neither DeepSeek nor Grok is evaluated as a
    model in CladBench, which is the point: the marking is done by systems that
    are not competing in the benchmark they are marking.
    """

    BASE_URL = ""
    ENV_KEY = ""
    PROVIDER = ""

    def __init__(self, model: str):
        from openai import OpenAI

        api_key = os.environ.get(self.ENV_KEY)
        if not api_key:
            raise RuntimeError(f"{self.ENV_KEY} not set in environment / .env")
        self.client = OpenAI(api_key=api_key, base_url=self.BASE_URL)
        self.model = model
        self.name = f"{self.PROVIDER}:{model}"

    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        import time

        max_new_tokens, clamped_from = self._clamp(max_new_tokens)
        last_exc = None
        for attempt in range(4):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_new_tokens,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                choice = resp.choices[0]
                raw = getattr(choice, "finish_reason", "") or ""
                usage = {}
                if getattr(resp, "usage", None):
                    usage = {"prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                             "completion_tokens": getattr(resp.usage, "completion_tokens", None)}
                return GenerationResult(
                    text=choice.message.content or "",
                    finish_reason=_normalise_finish(raw),
                    raw_finish_reason=raw,
                    usage={**usage, "budget_clamped_from": clamped_from},
                )
            except Exception as e:
                last_exc = e
                if classify(e) == TERMINAL:
                    raise
                time.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]


class DeepSeekAdapter(OpenAICompatibleAdapter):
    BASE_URL = "https://api.deepseek.com"
    ENV_KEY = "DEEPSEEK_API_KEY"
    PROVIDER = "deepseek"


class GrokAdapter(OpenAICompatibleAdapter):
    BASE_URL = "https://api.x.ai/v1"
    ENV_KEY = "GROK_API_KEY"
    PROVIDER = "grok"


class HuggingFaceAdapter(ModelAdapter):
    """Runs a HF Transformers model locally. Cache-aware."""

    def __init__(self, model: str = "Qwen/Qwen2.5-0.5B-Instruct"):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_id = model
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(model)
        self.name = f"hf:{model}"

    def generate_full(self, prompt: str, *, max_new_tokens: int = 256) -> GenerationResult:
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt")
        outputs = self.model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False
        )
        response_ids = outputs[0][inputs["input_ids"].shape[1] :]
        # Local generation has no finish_reason; hitting the cap exactly, without an
        # EOS token, is the equivalent signal.
        hit_cap = (
            len(response_ids) >= max_new_tokens
            and response_ids[-1].item() != self.tokenizer.eos_token_id
        )
        return GenerationResult(
            text=self.tokenizer.decode(response_ids, skip_special_tokens=True).strip(),
            finish_reason="length" if hit_cap else "stop",
            raw_finish_reason="length" if hit_cap else "eos",
            usage={"completion_tokens": int(len(response_ids))},
        )


# ============================================================================
# Adapter registry
# ============================================================================


def build_adapter(spec: str) -> ModelAdapter:
    """Parse a model spec string and build the adapter.

    Examples:
    - ``anthropic:claude-opus-4-7``
    - ``openai:gpt-4o``
    - ``hf:Qwen/Qwen2.5-0.5B-Instruct``
    """
    if ":" not in spec:
        raise ValueError(f"model spec must be 'provider:model', got: {spec!r}")
    provider, model = spec.split(":", 1)
    builders = {
        "anthropic": AnthropicAdapter,
        "openai": OpenAIAdapter,
        "google": GeminiAdapter,
        "together": TogetherAdapter,
        "deepseek": DeepSeekAdapter,
        "grok": GrokAdapter,
        "hf": HuggingFaceAdapter,
    }
    if provider not in builders:
        raise ValueError(f"unknown provider {provider!r}; valid: {sorted(builders)}")
    return builders[provider](model=model)


# ============================================================================
# Anthropic-based LLM judge
# ============================================================================


class JudgeError(RuntimeError):
    """The judge failed to return a usable verdict. Never score this as zero."""


def make_judge(spec: str):
    """Build a judge callable for any model spec — not just Anthropic.

    Exists so the benchmark can be marked by models that do not compete in it.
    Until 2026-08-10 the only judge was Claude Opus 4.7, which also wrote every
    question and sat the exam; a neutral marker removes that conflict entirely.

    Returns a ``(response, reference, rubric) -> {criterion: points}`` callable with
    the same contract, and the same refusal to return a partial verdict, as
    :func:`anthropic_judge`.
    """
    adapter = build_adapter(spec)

    def judge(response: str, reference: str, rubric: list[dict]) -> dict[str, int]:
        prompt = _build_judge_prompt(response, reference, rubric)
        last_missing: list[str] = []
        for attempt in (1, 2):
            gen = adapter.generate_full(prompt, max_new_tokens=JUDGE_MAX_TOKENS)
            if gen.truncated:
                if attempt == 2:
                    raise JudgeError(f"{spec} verdict truncated after 2 attempts")
                continue
            awarded = _parse_judge_reply(gen.text)
            last_missing = _unmatched_criteria(awarded, rubric)
            if not last_missing:
                return awarded
        raise JudgeError(
            f"{spec} did not return {len(last_missing)} of {len(rubric)} criteria "
            f"after 2 attempts: {last_missing}. Refusing to award 0 by default."
        )

    judge.name = spec  # type: ignore[attr-defined]
    return judge


def _build_judge_prompt(response: str, reference: str, rubric: list[dict]) -> str:
    rubric_lines = "\n".join(
        f"- {item['criterion']} (max {item['max_points']} points)"
        + (f": {item.get('description', '')}" if item.get("description") else "")
        for item in rubric
    )
    example_lines = "\n".join(
        f"{item['criterion']}: <integer 0 to {item['max_points']}>" for item in rubric
    )
    return (
        "You are scoring a candidate response against a rubric.\n\n"
        f"Reference answer:\n{reference}\n\n"
        f"Candidate response:\n{response}\n\n"
        f"Rubric:\n{rubric_lines}\n\n"
        "Output one line per rubric item. Each line must start with the EXACT "
        "criterion name from the rubric (verbatim, including case and "
        "punctuation), followed by a colon and the integer number of points "
        "awarded. Do not paraphrase the criterion name. Format:\n"
        f"{example_lines}\n\n"
        "Output ONLY these lines. No preamble, no explanation, no markdown."
    )


def _parse_judge_reply(text: str) -> dict[str, int]:
    awarded: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        criterion, _, points = line.partition(":")
        criterion = criterion.strip().lstrip("- ").strip("*` ")
        try:
            awarded[criterion] = int(points.strip().split()[0])
        except (ValueError, IndexError):
            continue
    return awarded


def _unmatched_criteria(parsed: dict[str, int], rubric: list[dict]) -> list[str]:
    """Which rubric criteria did the judge fail to return? Mirrors scorers._lookup."""
    lower = {k.lower(): v for k, v in parsed.items()}
    missing = []
    for item in rubric:
        key = item["criterion"].lower()
        if key in lower:
            continue
        if any(k.startswith(key[: min(20, len(key))]) or key.startswith(k[: min(20, len(k))])
               for k in lower):
            continue
        missing.append(item["criterion"])
    return missing


JUDGE_MODEL = "claude-opus-4-7"
JUDGE_MAX_TOKENS = 1024
"""Was 300. A five-criterion rubric with long criterion names can exceed that, and a
truncated verdict loses its trailing criteria — which `scorers._lookup` then treats as
0 points awarded. That is a silent zero indistinguishable from a genuine judgement, so
the ceiling is now generous and truncation raises instead."""


def anthropic_judge(response: str, reference: str, rubric: list[dict]) -> dict[str, int]:
    """Default LLM judge implementation. Scores response against rubric using Claude.

    Returns ``{criterion: points_awarded}``. Used by scorers.py.

    Raises :class:`JudgeError` rather than returning a partial verdict: a missing
    criterion silently becomes zero points downstream, which is how a billing
    failure and a truncated verdict both once entered published results as scores.
    """
    from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment / .env")
    client = Anthropic(api_key=api_key)

    rubric_lines = "\n".join(
        f"- {item['criterion']} (max {item['max_points']} points)"
        + (f": {item.get('description', '')}" if item.get("description") else "")
        for item in rubric
    )
    example_lines = "\n".join(
        f"{item['criterion']}: <integer 0 to {item['max_points']}>" for item in rubric
    )
    judge_prompt = (
        "You are scoring a candidate response against a rubric.\n\n"
        f"Reference answer:\n{reference}\n\n"
        f"Candidate response:\n{response}\n\n"
        f"Rubric:\n{rubric_lines}\n\n"
        "Output one line per rubric item. Each line must start with the EXACT "
        "criterion name from the rubric (verbatim, including case and "
        "punctuation), followed by a colon and the integer number of points "
        "awarded. Do not paraphrase the criterion name. Format:\n"
        f"{example_lines}\n\n"
        "Output ONLY these lines. No preamble, no explanation, no markdown."
    )
    def _ask() -> tuple[dict[str, int], str, str]:
        # No temperature — deprecated on this model family (see AnthropicAdapter).
        # The judge therefore cannot be pinned either; run-to-run verdict variance
        # is real and is quantified in the determinism check, not assumed away.
        msg = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=JUDGE_MAX_TOKENS,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        raw_stop = getattr(msg, "stop_reason", "") or ""
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))
        parsed: dict[str, int] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            criterion, _, points = line.partition(":")
            criterion = criterion.strip().lstrip("- ")
            try:
                parsed[criterion] = int(points.strip().split()[0])
            except (ValueError, IndexError):
                continue
        return parsed, text, raw_stop

    def _unmatched(parsed: dict[str, int]) -> list[str]:
        """Which rubric criteria did the judge fail to return? Mirrors scorers._lookup."""
        lower = {k.lower(): v for k, v in parsed.items()}
        missing = []
        for item in rubric:
            key = item["criterion"].lower()
            if key in lower:
                continue
            if any(
                k.startswith(key[: min(20, len(key))]) or key.startswith(k[: min(20, len(k))])
                for k in lower
            ):
                continue
            missing.append(item["criterion"])
        return missing

    last_missing: list[str] = []
    for attempt in (1, 2):
        awarded, text, raw_stop = _ask()
        if _normalise_finish(raw_stop) == "length":
            if attempt == 2:
                raise JudgeError(
                    f"judge verdict truncated at {JUDGE_MAX_TOKENS} tokens after 2 attempts"
                )
            continue
        last_missing = _unmatched(awarded)
        if not last_missing:
            return awarded
    raise JudgeError(
        f"judge did not return {len(last_missing)} of {len(rubric)} rubric criteria "
        f"after 2 attempts: {last_missing}. Refusing to award 0 by default."
    )
