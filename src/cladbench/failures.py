"""Classify provider errors so the harness knows whether to retry, or stop dead.

The distinction matters more than it looks. In the first baseline round the
Anthropic judge ran out of credit partway through a run. The harness treated that
like any other exception — wrote a zero, moved on — and kept going for hundreds
more questions, every one of them unscorable for the same reason. The output file
looked complete. The score looked like a model result.

Three classes:

  TRANSIENT  rate limits, overload, timeouts. Back off and retry; the run recovers.
  TERMINAL   auth failure, exhausted credit, revoked key. Retrying cannot help and
             every remaining question will fail identically. STOP THE RUN so a human
             can top up, rather than burning through the rest of the dataset
             manufacturing zeros.
  UNKNOWN    treated as transient for retry, but never silently scored.
"""

from __future__ import annotations

TRANSIENT = "transient"
TERMINAL = "terminal"
UNKNOWN = "unknown"

# Substrings that mean "your account cannot serve this request until a human acts"
_TERMINAL_MARKERS = (
    "credit balance is too low",
    "insufficient_quota",
    "insufficient funds",
    "exceeded your current quota",
    "billing",
    "payment required",
    "invalid_api_key",
    "invalid api key",
    "incorrect api key",
    "authentication_error",
    "unauthorized",
    "permission_denied",
    "account is not active",
    "suspended",
)

_TRANSIENT_MARKERS = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "overloaded",
    "server had an error",
    "service unavailable",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "connection",
    "502",
    "503",
    "504",
)


class TerminalProviderError(RuntimeError):
    """A provider failure no amount of retrying will fix. Stop the run."""


def classify(exc: BaseException) -> str:
    """Return TRANSIENT / TERMINAL / UNKNOWN for a provider exception."""
    text = f"{type(exc).__name__}: {exc}".lower()

    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int):
        if status in (401, 402, 403):
            return TERMINAL
        if status == 400:
            # A malformed request is malformed on every attempt. Retrying one is
            # pure latency: an unsupported parameter once cost 60s per question in
            # backoff before the run was abandoned. Fail immediately instead.
            return TERMINAL
        if status in (408, 409, 429, 500, 502, 503, 504):
            # 429 is ambiguous: a per-minute rate limit is transient, an exhausted
            # quota is terminal. Fall through to the text markers to decide.
            if status == 429 and any(m in text for m in _TERMINAL_MARKERS):
                return TERMINAL
            return TRANSIENT

    if any(m in text for m in _TERMINAL_MARKERS):
        return TERMINAL
    if any(m in text for m in _TRANSIENT_MARKERS):
        return TRANSIENT
    return UNKNOWN


def is_terminal(exc: BaseException) -> bool:
    return classify(exc) == TERMINAL
