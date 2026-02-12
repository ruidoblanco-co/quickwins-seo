"""
Result validation — runs before any data is displayed or exported.

Catches HTML leaks, Quick Win / detail mismatches, duplicate URLs,
and placeholder text. Raises ValueError with all failures listed.
"""

from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from detector import Problem

logger = logging.getLogger("quickwins")


def validate_results(
    quick_wins: List["Problem"],
    critical_errors: List["Problem"],
    warnings: List["Problem"],
) -> bool:
    """
    Validate results quality before display.

    Raises ValueError with a bullet-list of every failure found.
    Returns True if everything passes.
    """
    errors: List[str] = []

    # ── 1. Every Quick Win must exist in detailed errors with same URLs ──
    all_detailed = critical_errors + warnings
    detail_by_title = {p.title: p for p in all_detailed}

    for qw in quick_wins:
        match = detail_by_title.get(qw.title)
        if not match:
            errors.append(
                f"Quick Win '{qw.title}' has no matching entry in critical_errors or warnings"
            )
        elif set(qw.urls) != set(match.urls):
            errors.append(
                f"Quick Win '{qw.title}' URL list differs from its detail entry "
                f"({len(qw.urls)} vs {len(match.urls)} URLs)"
            )

    # ── 2. No HTML tags anywhere ──
    all_problems = list(quick_wins) + list(critical_errors) + list(warnings)
    for problem in all_problems:
        for field_name, field_val in [
            ("title", problem.title),
            ("description", problem.description),
            ("why_it_matters", problem.why_it_matters),
            ("how_to_fix", problem.how_to_fix),
        ]:
            if not field_val:
                continue
            if "<" in field_val and ">" in field_val:
                errors.append(
                    f"Possible HTML in '{problem.title}'.{field_name}: "
                    f"{field_val[:80]!r}"
                )
            if "&lt;" in field_val or "&gt;" in field_val or "&amp;" in field_val:
                errors.append(
                    f"HTML entity in '{problem.title}'.{field_name}: "
                    f"{field_val[:80]!r}"
                )

    # ── 3. No duplicate URLs within a single problem (www normalisation) ──
    for problem in all_problems:
        if len(problem.urls) != len(set(problem.urls)):
            errors.append(
                f"Duplicate URLs in '{problem.title}' (check www normalisation)"
            )

    # ── 4. No placeholder / hallucinated text ──
    forbidden_phrases = [
        "Not explicitly listed",
        "identified in crawl_summary",
        "see sample",
        "<p class=",
        "<div class=",
        "Not collected in this audit",
    ]
    for problem in all_problems:
        full_text = (
            f"{problem.description} {problem.why_it_matters} {problem.how_to_fix}"
        )
        for phrase in forbidden_phrases:
            if phrase in full_text:
                errors.append(
                    f"Forbidden text in '{problem.title}': contains '{phrase}'"
                )

    # ── Report ──
    if errors:
        msg = "VALIDATION FAILED:\n" + "\n".join(f"  • {e}" for e in errors)
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Validation passed (%d problems checked)", len(all_problems))
    return True
