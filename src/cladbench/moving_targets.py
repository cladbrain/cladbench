"""Policy positions the dataset depends on that can move, and what is currently true.

This module exists because of a specific failure. On 2026-08-06 the Future Homes
Standard commencement was corrected from 2025 to 24 March 2027 — in the two Category 12
questions being looked at that day. Nothing checked the rest of the dataset for the same
claim, so eight further questions across Categories 11 and 12 kept the superseded date
for another week, and Category 12 was reported complete when it was not.

The unit of correction was wrong. A moving target is a property of the *dataset*, not of
the question that happens to surface it, so it has to be swept dataset-wide or it comes
back.

Two things live here:

  TARGETS   each policy position the dataset relies on, the pattern that matches the
            superseded wording, what is true now, and the evidence for that. Adding a
            target here makes `check()` sweep all 536 questions for it.

  check()   run over the dataset by `audit_moving_targets.py`. It fails when a stale
            pattern reappears anywhere, which is the regression this module is for.

What it can and cannot do, stated plainly so nobody trusts it further than it deserves:
it catches a *known* target drifting back into the data. It cannot catch a policy change
nobody has noticed yet. That gap is why questions carry a `policy_dependency` tag and an
`as_at` date rather than being presented as durable — see `tag_policy_dependency.py`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

AS_AT = "2026-08-13"
"""The date the positions below were last established. Any score computed against a
question tagged `live` is only valid as at this date."""


@dataclass(frozen=True)
class Target:
    key: str
    name: str
    stale: str
    """Regex matching the superseded wording. Must not match the corrected wording —
    `check()` would then fail forever and get switched off, which is worse than no check."""
    current: str
    evidence: str
    established: str
    keywords: tuple[str, ...] = field(default=())
    """Terms that mark a question as depending on this target even once corrected."""
    exempt: tuple[str, ...] = field(default=())
    """Phrasings that mean a nearby year is part of the CORRECTED wording, not a stale
    claim. Without these the checks self-trigger: "Building Circular 01/2026" contains
    2026, and "the EPC C by 2027 milestone was dropped" contains the very string the
    stale pattern hunts for. A check that fires on its own fix gets muted, so the
    exemption is load-bearing, not cosmetic."""


TARGETS: tuple[Target, ...] = (
    Target(
        key="fhs_commencement",
        name="Future Homes Standard commencement",
        stale=r"(?:Future Homes Standard|FHS)[^.;]{0,60}\b202[456]\b"
              r"|\b202[456]\b[^.;]{0,40}(?:Future Homes Standard|FHS)"
              r"|post-2025[^.;]{0,30}(?:Future Homes|FHS)"
              r"|Future Buildings Standard[^.;]{0,30}\(2025\)",
        current="Comes into force 24 March 2027. Transitional provisions: work is not "
                "caught where a building notice, initial notice or full plans application "
                "was given before 24 March 2027 AND the work commenced before 24 March "
                "2028. Roughly 75-80% CO2 reduction against the Part L 2013 baseline.",
        evidence="gov.uk, The Future Homes and Buildings Standards: Building Circular "
                 "01/2026; Approved Document L Volume 1 (2025 edition)",
        established="2026-08-06",
        keywords=("Future Homes Standard", "FHS", "Future Buildings Standard"),
        exempt=(r"Building Circular 01/2026", r"in force 24 March 2027",
                r"24 March 2028", r"comes into force 24 March 2027",
                r"Welsh Government consultation 2024"),
    ),
    Target(
        key="mees_nondom",
        name="Non-domestic MEES trajectory",
        stale=r"(?:MEES|EPC)[^.;]{0,80}(?:C by 2027|2027 commercial|Band C 2027|"
              r"C by April 2027|B by 2030|Band B 2030|Band B by 2030|C by 2027)"
              r"|(?:C by 2027|B by 2030)[^.;]{0,60}MEES"
              r"|Band C by 2027",
        current="NOT law. The minimum remains EPC E, in force for all commercial lets "
                "since 1 April 2023. The June 2026 DESNZ interim response to the "
                "non-domestic MEES consultation confirmed the proposed EPC C by 2027 "
                "interim milestone will NOT be taken forward, and replaced the "
                "C-2027/B-2030 trajectory with a single proposed standard of EPC B by "
                "2031, limited to privately-let buildings over 1,000 m2, applied only "
                "where cost-effective, and still subject to secondary legislation.",
        evidence="DESNZ interim response to the non-domestic MEES consultation, June 2026",
        established="2026-08-13",
        keywords=("MEES", "minimum energy efficiency standard"),
        exempt=(r"EPC C by 2027 milestone was dropped",
                r"EPC C by 2027 interim milestone",
                r"by 2031", r"not yet law"),
    ),
    Target(
        key="mees_domestic",
        name="Domestic MEES (PRS) trajectory",
        stale=r"MEES[^.;]{0,80}(?:residential|domestic|PRS)[^.;]{0,60}"
              r"(?:C from 202\d|EPC C by 202\d)"
              r"|proposed EPC C from 202\d"
              r"|EPC C by 2028/2030",
        current="The minimum remains EPC E. An EPC C requirement for the private rented "
                "sector has been consulted on repeatedly but is not in force: the 2020 "
                "proposal was withdrawn in September 2023 and re-consulted from 2025. Any "
                "date must be described as proposed, not enacted.",
        evidence="DESNZ PRS minimum energy efficiency consultations; September 2023 withdrawal",
        established="2026-08-13",
        # Deliberately NOT bare "MEES": the domestic and non-domestic regimes have
        # separate trajectories, and matching the shared acronym made every commercial
        # question claim a domestic dependency it does not have.
        keywords=("PRS", "private rented", "domestic MEES", "MEES residential",
                  "MEES (Domestic)", "MEES extension to social"),
    ),
)

BY_KEY = {t.key: t for t in TARGETS}


def _answer_blob(example: dict) -> str:
    return json.dumps(example.get("answer", {}), ensure_ascii=False)


WINDOW = 140
"""How far either side of a match to look for an exemption. Wide enough to catch
"... EPC B by 2031 ... the EPC C by 2027 milestone was dropped ..." as one corrected
sentence; narrow enough that an exemption elsewhere in a long answer does not excuse a
genuinely stale claim."""


def stale_hits(example: dict) -> list[tuple[str, str]]:
    """Return (target key, matched text) for every superseded claim in one example.

    A match sitting inside corrected wording is not a finding — see `Target.exempt`.
    """
    blob = _answer_blob(example)
    out: list[tuple[str, str]] = []
    for t in TARGETS:
        for m in re.finditer(t.stale, blob, re.I):
            ctx = blob[max(0, m.start() - WINDOW):m.end() + WINDOW]
            if any(re.search(x, ctx, re.I) for x in t.exempt):
                continue
            out.append((t.key, re.sub(r"\s+", " ", m.group(0)).strip()))
    return out


def depends_on(example: dict) -> list[str]:
    """Target keys this example depends on, whether or not its wording is current.

    A corrected answer still depends on the policy — that is the point of the `live`
    tag. Matching on keywords rather than on the stale pattern is what keeps a question
    tagged after it has been fixed.
    """
    blob = _answer_blob(example)
    return [t.key for t in TARGETS
            if any(re.search(re.escape(k), blob, re.I) for k in t.keywords)]


def check(data_root: Path, split: str = "public") -> list[tuple[str, str, str]]:
    """Sweep the dataset. Returns (question id, target key, matched text) for each
    superseded claim still present. Empty list means clean."""
    findings: list[tuple[str, str, str]] = []
    for d in sorted(Path(data_root).iterdir()):
        f = d / f"{split}.jsonl"
        if not f.is_file():
            continue
        for line in f.open(encoding="utf-8"):
            if not line.strip():
                continue
            ex = json.loads(line)
            for key, text in stale_hits(ex):
                findings.append((ex["id"], key, text))
    return findings
