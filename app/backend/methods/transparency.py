"""Transparency-signals auditor (backlog #44 increment 1, inc 250).

Reads a paper's extracted text and detects whether it *discloses* seven open-science artifacts a reader needs to see
— data availability, code availability, conflict-of-interest, funding, protocol/trial registration, preregistration,
and (as a weak-signal qualifier) an "available upon request" statement. ODDPub / rtransparent-derived, rule-based.
FLAG-not-ADJUDICATE: each check is present / not-found / not-applicable, never a verdict, never a score. "not-found"
means "not detected in the extracted text — check the paper", NEVER "absent" / "concealed" / "no open data"
(silence≠certificate), and never an accusation of the authors. The deterministic sibling of statcheck / the LMM /
meta-analysis auditors. Local, no AI, no egress.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TransparencySignal:
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None
    page: int | None
    note: str | None
    explainer: str
    basis: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TransparencyReport:
    checks: list  # list[TransparencySignal]

    def to_dict(self) -> dict:
        return {"checks": [c.to_dict() for c in self.checks]}


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# Repository-domain list (matched as evidence of data/code deposition).
_REPO_URL = _rx(
    r"osf\.io|zenodo\.org|10\.5281/zenodo|10\.17605/OSF|datadryad\.org|\bdryad\b|figshare\.com|github\.com|"
    r"gitlab\.com|bitbucket\.org|codeocean\.com|openneuro\.org|data\.mendeley\.com|\bdataverse\b|\bre3data\b"
)

_DATA = _rx(
    r"data (are|is|will be)\s+(openly\s+)?(available|accessible|deposited|shared)|data availability|availability of "
    r"data|(all |the )?(raw )?data (and materials )?(are|is)?\s*(openly )?available|supporting data|underlying data|"
    r"data set[s]? (are|is)? (available|deposited)"
)
_CODE = _rx(
    r"(analysis |source |the )?(code|scripts?|software) (are|is|will be)?\s*(openly )?(available|accessible|shared|"
    r"provided|deposited)|code availability|availability of code|reproducib(le|ility) (code|scripts?)|"
    r"\bR (scripts?|code)\b|(Python|MATLAB|Stata|SPSS|Jupyter) (code|scripts?|notebooks?)"
)
_COI = _rx(
    r"conflicts? of interest|competing interests?|(no|declare[sd]?)\b.{0,24}(competing|conflict)|financial "
    r"(disclosure|interest)|declaration of interest|the authors declare"
)
_FUNDING = _rx(
    r"funded by|\bfunding\b|financial support|grants?\s+(from|number|no)|supported (in part )?by|received no "
    r"(specific )?(funding|grant)|no funding was received|award(ed)?\s+(number|by)|\b(NIH|NSF|ERC|Wellcome|MRC|DFG|"
    r"NSFC|NIHR)\b"
)
_REGISTRATION = _rx(
    r"registered (at|on|with|in|under)|registration (number|no|id)|\bNCT\d{6,}\b|PROSPERO|\bCRD\d{6,}\b|"
    r"ClinicalTrials\.gov|\b(ISRCTN|ANZCTR|UMIN|EudraCT)\b|trial registration|study (was )?registered|"
    r"OSF registration|registered report"
)
_TRIAL = _rx(
    r"randomi[sz]ed (controlled )?trial|\bRCT\b|clinical trial|systematic review|meta[-\s]?analysis|study protocol|"
    r"pre[-\s]?registered|preregistration|registered report|\bNCT\d{6,}\b|PROSPERO"
)
_PREREG = _rx(
    r"pre[-\s]?regist(ered|ration)|preregistered|AsPredicted|registered report|(analysis|study) (plan|protocol) "
    r"(was )?(pre[-\s]?)?registered|OSF (pre[-\s]?)?registration|time[-\s]?stamped (analysis|hypothes[ei]s)"
)
_UPON_REQUEST = _rx(
    r"(available|obtained|provided|shared) (from the (corresponding )?author[s]? )?(up)?on (reasonable )?request|"
    r"request(ed)? from the (corresponding )?author|contact the (corresponding )?author"
)


def _chunk_rows(chunks: list) -> list[tuple[str, int | None]]:
    return [(getattr(c, "text", "") or "", getattr(c, "page_start", None)) for c in chunks]


def _snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    lo, hi = max(0, start - pad), min(len(text), end + pad)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()[:200]


def _first(pattern: re.Pattern, rows: list[tuple[str, int | None]]) -> tuple[str, int | None] | None:
    for text, page in rows:
        m = pattern.search(text)
        if m:
            return _snippet(text, m.start(), m.end()), page
    return None


def _has(pattern: re.Pattern, rows: list[tuple[str, int | None]]) -> bool:
    return any(pattern.search(text) for text, _ in rows)


_NOT_DETECTED = "not detected in the extracted text — check the paper"


def _present_or_absent(key, label, patterns, rows, *, basis, missing_note, explainer) -> TransparencySignal:
    """A signal present iff ANY of `patterns` matches (with the first match's evidence), else not-found."""
    for pattern in patterns:
        hit = _first(pattern, rows)
        if hit:
            return TransparencySignal(key, label, "present", hit[0], hit[1], None, explainer, basis)
    return TransparencySignal(
        key, label, "not-found", None, None, f"{missing_note} ({_NOT_DETECTED})", explainer, basis
    )


def detect_transparency(chunks: list) -> TransparencyReport:
    """Rule-based open-science-disclosure detectors over a paper's extracted text. Each check present / not-found /
    not-applicable — never a verdict, never a score, never an accusation. Always returns the 7 checks (no gate)."""
    rows = _chunk_rows(chunks)
    checks: list[TransparencySignal] = []

    checks.append(
        _present_or_absent(
            "data_availability",
            "Data availability",
            (_DATA, _REPO_URL),
            rows,
            basis="ODDPub (Riedel et al. 2020)",
            missing_note="no data-availability statement or data-repository link is detected — the paper may still "
            "share data (in an appendix, a footnote, or the journal's structured metadata)",
            explainer="Whether the paper states where its data live (a statement and/or a repository link such as "
            "OSF, Zenodo, Dryad, or figshare). Detection is text-only — absence here is a prompt to look, not proof.",
        )
    )
    checks.append(
        _present_or_absent(
            "code_availability",
            "Code / software availability",
            (_CODE, _REPO_URL),
            rows,
            basis="ODDPub (Riedel et al. 2020)",
            missing_note="no analysis-code / software-availability statement or code-repository link is detected",
            explainer="Whether the paper shares the analysis code/scripts (a statement and/or a repository such as "
            "GitHub, GitLab, or Code Ocean) — what a reader needs to reproduce the analysis.",
        )
    )
    checks.append(
        _present_or_absent(
            "conflict_of_interest",
            "Conflict-of-interest statement",
            (_COI,),
            rows,
            basis="rtransparent (Serghiou et al. 2021)",
            missing_note="no conflict-of-interest / competing-interests statement is detected",
            explainer="Whether the paper includes a competing-interests / conflict-of-interest declaration — a "
            "standard disclosure a reader looks for. Its absence in the text is not a claim of an undisclosed conflict.",
        )
    )
    checks.append(
        _present_or_absent(
            "funding",
            "Funding statement",
            (_FUNDING,),
            rows,
            basis="rtransparent (Serghiou et al. 2021)",
            missing_note="no funding statement is detected",
            explainer="Whether the paper reports its funding sources (or states it received none) — context for a "
            "reader weighing the work.",
        )
    )

    # Registration — precondition-scoped: n/a unless a trial/registration cue is present.
    reg_explainer = (
        "For a trial or systematic review, whether the protocol/trial was registered (ClinicalTrials.gov, PROSPERO, "
        "OSF Registries) — it lets a reader check the study against its plan."
    )
    reg_basis = "rtransparent (Serghiou et al. 2021); CONSORT / PRISMA"
    if not (_has(_TRIAL, rows) or _has(_REGISTRATION, rows)):
        checks.append(
            TransparencySignal(
                "registration",
                "Protocol / trial registration",
                "not-applicable",
                None,
                None,
                "not a registered/trial design where a registration is expected",
                reg_explainer,
                reg_basis,
            )
        )
    else:
        checks.append(
            _present_or_absent(
                "registration",
                "Protocol / trial registration",
                (_REGISTRATION,),
                rows,
                basis=reg_basis,
                missing_note="a trial/review design is indicated but no registration (a registry ID or a "
                "registration statement) is detected",
                explainer=reg_explainer,
            )
        )

    checks.append(
        _present_or_absent(
            "preregistration",
            "Preregistration",
            (_PREREG,),
            rows,
            basis="Nosek et al. 2018 (preregistration); AsPredicted / OSF Registries",
            missing_note="no preregistration statement is detected",
            explainer="Whether the study's hypotheses/analysis plan were preregistered before data collection "
            "(AsPredicted, OSF) — a signal about confirmatory vs exploratory analysis.",
        )
    )

    # "Available upon request" — a weak-signal qualifier, only shown when the phrase appears.
    ur_explainer = (
        '"Data/code available upon request" is a weaker availability signal than a repository link — the artifact '
        "isn't openly posted. Shown as a legibility note, never an accusation."
    )
    ur_basis = "ODDPub (Riedel et al. 2020) — 'upon request' is a weak availability signal"
    ur_hit = _first(_UPON_REQUEST, rows)
    if ur_hit:
        checks.append(
            TransparencySignal(
                "upon_request",
                '"Available upon request" (weak signal)',
                "present",
                ur_hit[0],
                ur_hit[1],
                'data/code is offered only "upon request" — a weaker signal than an open repository link, not a '
                "concern in itself",
                ur_explainer,
                ur_basis,
            )
        )
    else:
        checks.append(
            TransparencySignal(
                "upon_request",
                '"Available upon request" (weak signal)',
                "not-applicable",
                None,
                None,
                'no "upon request" availability language detected',
                ur_explainer,
                ur_basis,
            )
        )

    return TransparencyReport(checks=checks)
