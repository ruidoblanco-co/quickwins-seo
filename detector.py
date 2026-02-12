"""
Deterministic SEO problem detector.

Analyses crawl data using fixed rules — no LLM, no invented data.
Returns structured Problem objects ready for display and Excel export.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger("quickwins")


# ───────────────────────────────────────────
# URL normalisation (www = non-www)
# ───────────────────────────────────────────
def normalize_url(url: str) -> str:
    """Normalize URL so www and non-www are treated as the same."""
    url = (url or "").strip().rstrip("/")
    url = url.replace("://www.", "://")
    return url


# ───────────────────────────────────────────
# Data structures
# ───────────────────────────────────────────
@dataclass
class Problem:
    title: str
    severity: str  # "critical" or "warning"
    description: str
    why_it_matters: str
    how_to_fix: str
    urls: List[str] = field(default_factory=list)
    impact_score: int = 5
    effort_hours: float = 1.0

    @property
    def priority_score(self) -> float:
        """Higher = better quick win (more impact per effort)."""
        if self.effort_hours <= 0:
            return float(self.impact_score)
        return self.impact_score / self.effort_hours


# ───────────────────────────────────────────
# Detection helpers
# ───────────────────────────────────────────
def _safe_int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _norm_urls(urls: list) -> List[str]:
    """Normalize and deduplicate a list of URLs."""
    seen = set()
    result = []
    for u in urls:
        n = normalize_url(u)
        if n and n not in seen:
            seen.add(n)
            result.append(n)
    return result


# ───────────────────────────────────────────
# Individual detection rules
# ───────────────────────────────────────────
def _detect_missing_h1(pages: List[Dict]) -> Problem | None:
    urls = []
    for p in pages:
        if p.get("error"):
            continue
        if _safe_int(p.get("h1_count")) == 0:
            urls.append(p.get("final_url") or p.get("url"))
    if not urls:
        return None
    return Problem(
        title="Missing H1 Tags",
        severity="critical",
        description=f"{len(urls)} pages have no H1 heading tag. The H1 is the most important on-page heading signal for search engines.",
        why_it_matters="Google uses the H1 as a primary signal to understand a page's main topic. Pages without an H1 are harder to rank because search engines must guess the topic from other content.",
        how_to_fix="Add a single, descriptive H1 tag to each page that clearly states the page's main topic. Ensure it contains the primary keyword for that page.",
        urls=_norm_urls(urls),
        impact_score=9,
        effort_hours=2.0,
    )


def _detect_duplicate_meta(pages: List[Dict]) -> Problem | None:
    meta_map: Dict[str, List[str]] = {}
    for p in pages:
        if p.get("error"):
            continue
        meta = (p.get("meta") or "").strip()
        if not meta:
            continue
        url = p.get("final_url") or p.get("url")
        meta_map.setdefault(meta, []).append(url)

    dup_urls = []
    for meta_text, page_urls in meta_map.items():
        if len(page_urls) > 1:
            dup_urls.extend(page_urls)

    if not dup_urls:
        return None
    return Problem(
        title="Duplicate Meta Descriptions",
        severity="critical",
        description=f"{len(dup_urls)} pages share a meta description with at least one other page. Each page should have a unique meta description.",
        why_it_matters="Duplicate meta descriptions mean Google sees the same snippet for multiple pages, reducing click-through rates and making it harder for search engines to differentiate pages.",
        how_to_fix="Write a unique, compelling meta description (120-155 characters) for each page that accurately describes its specific content and includes relevant keywords.",
        urls=_norm_urls(dup_urls),
        impact_score=8,
        effort_hours=1.0,
    )


def _detect_thin_content(pages: List[Dict], threshold: int = 300) -> Problem | None:
    urls = []
    for p in pages:
        if p.get("error"):
            continue
        wc = _safe_int(p.get("word_count"))
        if 0 < wc < threshold:
            urls.append(p.get("final_url") or p.get("url"))
    if not urls:
        return None
    return Problem(
        title="Thin Content",
        severity="critical",
        description=f"{len(urls)} pages have fewer than {threshold} words. Pages with very little content are harder to rank and may be seen as low-quality by Google.",
        why_it_matters="Google's Helpful Content system penalises pages that don't provide enough value. Thin pages also have fewer keyword opportunities and are less likely to satisfy search intent.",
        how_to_fix="Expand each thin page with relevant, useful content — aim for at least 300-500 words. If a page truly has nothing to add, consider consolidating it with a related page or setting it to noindex.",
        urls=_norm_urls(urls),
        impact_score=8,
        effort_hours=4.0,
    )


def _detect_multiple_h1(pages: List[Dict]) -> Problem | None:
    urls = []
    for p in pages:
        if p.get("error"):
            continue
        if _safe_int(p.get("h1_count")) > 1:
            urls.append(p.get("final_url") or p.get("url"))
    if not urls:
        return None
    return Problem(
        title="Multiple H1 Tags",
        severity="warning",
        description=f"{len(urls)} pages have more than one H1 tag. While not a fatal error, having a single H1 gives a clearer topical signal.",
        why_it_matters="Multiple H1s dilute the main heading signal. Google can handle them, but a single H1 provides a stronger, unambiguous indication of the page's primary topic.",
        how_to_fix="Keep one H1 per page for the main topic. Demote additional H1 tags to H2 or H3 as appropriate for sub-sections.",
        urls=_norm_urls(urls),
        impact_score=6,
        effort_hours=1.0,
    )


def _detect_title_too_long(pages: List[Dict]) -> Problem | None:
    urls = []
    for p in pages:
        if p.get("error"):
            continue
        title = (p.get("title") or "").strip()
        if title and len(title) > 60:
            urls.append(p.get("final_url") or p.get("url"))
    if not urls:
        return None
    return Problem(
        title="Title Tags Too Long",
        severity="warning",
        description=f"{len(urls)} pages have title tags longer than 60 characters. Google typically truncates titles beyond this length in search results.",
        why_it_matters="Truncated titles lose their full message in search results, which can lower click-through rates. Users may not understand what the page is about.",
        how_to_fix="Rewrite titles to 50-60 characters, front-loading the most important keywords. Move secondary information to the meta description.",
        urls=_norm_urls(urls),
        impact_score=5,
        effort_hours=2.0,
    )


def _detect_missing_meta(pages: List[Dict]) -> Problem | None:
    urls = []
    for p in pages:
        if p.get("error"):
            continue
        meta = (p.get("meta") or "").strip()
        if not meta:
            urls.append(p.get("final_url") or p.get("url"))
    if not urls:
        return None
    return Problem(
        title="Missing Meta Descriptions",
        severity="warning",
        description=f"{len(urls)} pages have no meta description. Google will auto-generate a snippet, which may not represent the page well.",
        why_it_matters="Without a meta description, Google picks a random passage from the page as the search snippet. A well-crafted meta description improves click-through rates by giving searchers a clear reason to click.",
        how_to_fix="Add a unique meta description (120-155 characters) to each page. Summarise the page's value proposition and include the primary keyword naturally.",
        urls=_norm_urls(urls),
        impact_score=7,
        effort_hours=1.5,
    )


def _detect_broken_links(broken_examples: List[Dict]) -> Problem | None:
    if not broken_examples:
        return None
    urls = _norm_urls([b.get("url", "") for b in broken_examples])
    if not urls:
        return None
    return Problem(
        title="Broken Internal Links",
        severity="critical",
        description=f"{len(urls)} internal links point to pages that return errors (4xx/5xx). Visitors and search engine crawlers hit dead ends.",
        why_it_matters="Broken links waste crawl budget, create poor user experience, and leak link equity into nowhere. Google may also see excessive broken links as a sign of poor site maintenance.",
        how_to_fix="For each broken link: update the href to point to the correct page, redirect the broken URL to a relevant replacement, or remove the link entirely if the content no longer exists.",
        urls=urls,
        impact_score=9,
        effort_hours=0.5,
    )


def _detect_missing_title(pages: List[Dict]) -> Problem | None:
    urls = []
    for p in pages:
        if p.get("error"):
            continue
        title = (p.get("title") or "").strip()
        if not title:
            urls.append(p.get("final_url") or p.get("url"))
    if not urls:
        return None
    return Problem(
        title="Missing Title Tags",
        severity="critical",
        description=f"{len(urls)} pages have no title tag. The title tag is the single most important on-page SEO element.",
        why_it_matters="The title tag is what Google displays as the clickable headline in search results. Without one, Google must fabricate a title, often producing a poor or irrelevant result that hurts click-through rates.",
        how_to_fix="Add a unique, descriptive title tag (50-60 characters) to every page. Include the primary keyword near the beginning of the title.",
        urls=_norm_urls(urls),
        impact_score=9,
        effort_hours=1.0,
    )


def _detect_duplicate_titles(pages: List[Dict]) -> Problem | None:
    title_map: Dict[str, List[str]] = {}
    for p in pages:
        if p.get("error"):
            continue
        title = (p.get("title") or "").strip()
        if not title:
            continue
        url = p.get("final_url") or p.get("url")
        title_map.setdefault(title, []).append(url)

    dup_urls = []
    for title_text, page_urls in title_map.items():
        if len(page_urls) > 1:
            dup_urls.extend(page_urls)

    if not dup_urls:
        return None
    return Problem(
        title="Duplicate Title Tags",
        severity="critical",
        description=f"{len(dup_urls)} pages share a title tag with at least one other page. Each page needs a unique title for Google to distinguish them.",
        why_it_matters="Duplicate titles cause keyword cannibalization — Google doesn't know which page to rank for a given query, so both pages rank worse. It also confuses users who see identical titles in search results.",
        how_to_fix="Write a unique title for each page that reflects its specific content. Use the primary keyword for that page and differentiate from similar pages.",
        urls=_norm_urls(dup_urls),
        impact_score=8,
        effort_hours=1.0,
    )


def _detect_missing_schema(pages: List[Dict]) -> Problem | None:
    total_valid = 0
    urls_without = []
    for p in pages:
        if p.get("error"):
            continue
        total_valid += 1
        if _safe_int(p.get("jsonld_count")) == 0:
            urls_without.append(p.get("final_url") or p.get("url"))

    if total_valid == 0:
        return None

    # Only flag if >70% of pages lack schema (site-wide pattern)
    ratio = len(urls_without) / total_valid
    if ratio < 0.7 or len(urls_without) < 3:
        return None

    return Problem(
        title="Missing Structured Data",
        severity="warning",
        description=f"{len(urls_without)} of {total_valid} analyzed pages ({ratio:.0%}) have no JSON-LD structured data. The site is missing rich snippet opportunities.",
        why_it_matters="Structured data (JSON-LD) enables rich results in Google — star ratings, FAQ accordions, breadcrumbs, and more. Sites with rich snippets get significantly higher click-through rates.",
        how_to_fix="Add JSON-LD schema markup to your pages. Start with the most impactful types: Article for blog posts, Product for e-commerce, LocalBusiness for local sites, or Organization for the homepage.",
        urls=_norm_urls(urls_without[:40]),  # Cap to avoid huge lists
        impact_score=5,
        effort_hours=3.0,
    )


def _detect_pages_with_errors(pages: List[Dict]) -> Problem | None:
    """Detect pages from sitemap that return 4xx/5xx status codes."""
    urls = []
    for p in pages:
        status = p.get("status")
        if status is None or (isinstance(status, int) and status >= 400):
            # Only include if it was an actual HTTP error, not a request failure
            url = p.get("url", "")
            if url:
                urls.append(url)

    if not urls:
        return None
    return Problem(
        title="Pages Returning Error Status",
        severity="critical",
        description=f"{len(urls)} URLs from the sitemap return 4xx or 5xx errors. These are dead pages that Google is being told to crawl.",
        why_it_matters="Having error pages in the sitemap wastes crawl budget and sends negative quality signals. Google expects every URL in a sitemap to return a 200 status. Stale sitemap entries degrade overall crawl efficiency.",
        how_to_fix="Remove the dead URLs from the sitemap. If the content has moved, add 301 redirects to the new locations. If the content is permanently gone, let the 404 or 410 stand but remove from sitemap.",
        urls=_norm_urls(urls),
        impact_score=8,
        effort_hours=1.0,
    )


# ───────────────────────────────────────────
# Main detection orchestrator
# ───────────────────────────────────────────
def detect_problems(
    pages: List[Dict[str, Any]],
    broken_link_examples: List[Dict[str, Any]] | None = None,
    thin_content_threshold: int = 300,
) -> Dict[str, Any]:
    """
    Run all detection rules on crawled page data.

    Returns a dict with:
      - quick_wins: top 5 problems sorted by priority_score
      - critical_errors: all problems with severity == "critical"
      - warnings: all problems with severity == "warning"
    """
    if broken_link_examples is None:
        broken_link_examples = []

    # Run all 11 rules
    all_problems: List[Problem] = []
    detectors = [
        lambda: _detect_missing_h1(pages),
        lambda: _detect_duplicate_meta(pages),
        lambda: _detect_thin_content(pages, threshold=thin_content_threshold),
        lambda: _detect_multiple_h1(pages),
        lambda: _detect_title_too_long(pages),
        lambda: _detect_missing_meta(pages),
        lambda: _detect_broken_links(broken_link_examples),
        lambda: _detect_missing_title(pages),
        lambda: _detect_duplicate_titles(pages),
        lambda: _detect_missing_schema(pages),
        lambda: _detect_pages_with_errors(pages),
    ]

    for detect_fn in detectors:
        problem = detect_fn()
        if problem is not None and problem.urls:
            all_problems.append(problem)
            logger.info("Detected: %s (%d URLs)", problem.title, len(problem.urls))

    # Split by severity
    critical = [p for p in all_problems if p.severity == "critical"]
    warnings = [p for p in all_problems if p.severity == "warning"]

    # Quick wins = top 5 by priority_score (impact / effort)
    ranked = sorted(all_problems, key=lambda p: p.priority_score, reverse=True)
    quick_wins = ranked[:5]

    logger.info(
        "Detection complete: %d critical, %d warnings, %d quick wins",
        len(critical), len(warnings), len(quick_wins),
    )

    return {
        "quick_wins": quick_wins,
        "critical_errors": critical,
        "warnings": warnings,
    }
