import streamlit as st
import time
import logging
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import google.generativeai as genai
from docx import Document
from docx.shared import Pt, RGBColor
from io import BytesIO
import re
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET
from collections import defaultdict


# ===========================
# LOGGING
# ===========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("quickwins")


# ===========================
# CONSTANTS
# ===========================
CRAWL_TIMEOUT = 12
MAX_PAGES = 40
MAX_INTERNAL_LINKS_PER_PAGE = 10
MAX_BROKEN_LINK_CHECKS = 180
MAX_BROKEN_LINKS_REPORTED = 50
MAX_SITEMAP_URLS = 6000
THIN_CONTENT_THRESHOLD = 250
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
LLM_MAX_TOKENS = 1800
LLM_TEMPERATURE = 0.2
HTTP_MAX_RETRIES = 3
HTTP_BACKOFF_FACTOR = 1  # seconds: 1s, 2s, 4s


# ===========================
# PAGE CONFIGURATION
# ===========================
st.set_page_config(
    page_title="Quick Wins - SEO Audit Tool",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ===========================
# API CONFIGURATION
# ===========================
try:
    GEMINI_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
    else:
        GEMINI_AVAILABLE = False
        logger.warning("GOOGLE_API_KEY not found in secrets")
except Exception as e:
    GEMINI_AVAILABLE = False
    logger.error("Failed to configure Gemini API: %s", e)


# ===========================
# CUSTOM CSS
# ===========================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #2b2d42 0%, #1a1b26 100%);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1b26 0%, #121318 100%);
    }

    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #60a5fa;
        font-weight: 600;
    }

    [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-size: 13px;
        font-weight: 500;
    }

    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #60a5fa 0%, #3b82f6 100%);
        color: white;
        font-weight: 600;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        font-size: 15px;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 12px rgba(96, 165, 250, 0.3);
    }

    .stTextInput>div>div>input {
        background-color: rgba(255, 255, 255, 0.05);
        color: white;
        border: 1px solid rgba(96, 165, 250, 0.3);
        border-radius: 6px;
        padding: 8px;
        font-size: 14px;
    }

    .stSelectbox>div>div>div {
        background-color: rgba(255, 255, 255, 0.05);
        color: white;
        border-radius: 6px;
        font-size: 14px;
    }

    .stRadio>div {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 12px;
        border-radius: 6px;
        border: 1px solid rgba(96, 165, 250, 0.2);
    }

    h1 {
        color: #60a5fa;
        font-weight: 700;
    }

    h2, h3 {
        color: #e2e8f0;
    }

    .app-header {
        text-align: center;
        padding: 20px 0 30px 0;
        margin-bottom: 30px;
        border-bottom: 2px solid rgba(96, 165, 250, 0.2);
    }

    .app-title {
        font-size: 48px;
        font-weight: 700;
        color: #60a5fa;
        margin: 10px 0 5px 0;
        letter-spacing: -1px;
    }

    .app-subtitle {
        font-size: 17px;
        color: #94a3b8;
        font-weight: 400;
        line-height: 1.6;
        max-width: 600px;
        margin: 0 auto;
    }

    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin: 4px;
    }

    .status-connected {
        background-color: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        border: 1px solid #22c55e;
    }

    .status-disconnected {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid #ef4444;
    }

    .audit-report {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 30px;
        border-radius: 8px;
        border: 1px solid rgba(96, 165, 250, 0.2);
        line-height: 1.8;
    }

    .audit-report h1 {
        color: #60a5fa;
        border-bottom: 2px solid rgba(96, 165, 250, 0.3);
        padding-bottom: 10px;
        margin-bottom: 20px;
    }

    .audit-report h2 {
        color: #93c5fd;
        margin-top: 30px;
        margin-bottom: 15px;
    }

    .audit-report h3 {
        color: #bfdbfe;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    .stRadio label, .stSelectbox label {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


# ===========================
# PATHS
# ===========================
BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
PROMPT_BASIC = PROMPTS_DIR / "basic.md"


# ===========================
# HTTP SESSION WITH RETRY
# ===========================
def _create_http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=HTTP_MAX_RETRIES,
        backoff_factor=HTTP_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


http_session = _create_http_session()


# ===========================
# URL VALIDATION
# ===========================
_PRIVATE_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_PRIVATE_PREFIXES = ("192.168.", "10.", "172.16.", "172.17.", "172.18.",
                     "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                     "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                     "172.29.", "172.30.", "172.31.", "169.254.")


def validate_url(raw: str) -> tuple[bool, str]:
    """Validate and sanitize a URL. Returns (is_valid, clean_url_or_error)."""
    url = (raw or "").strip()
    if not url:
        return False, "URL is required."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL."
    if parsed.scheme not in ("http", "https"):
        return False, "Only HTTP/HTTPS URLs are supported."
    hostname = (parsed.hostname or "").lower()
    if not hostname or "." not in hostname:
        return False, "Invalid domain."
    if hostname in _PRIVATE_HOSTNAMES or hostname.startswith(_PRIVATE_PREFIXES):
        return False, "Local/private URLs are not allowed."
    return True, url


# ===========================
# UTILS
# ===========================
def normalize_domain(url_or_domain: str) -> str:
    s = (url_or_domain or "").strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://")):
        s = urlparse(s).netloc
    s = s.lower()
    if s.startswith("www."):
        s = s[4:]
    s = s.split(":")[0]
    return s


def load_prompt(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def strip_json_fences(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


# ===========================
# WEB ANALYSIS (single page snapshot)
# ===========================
def analyze_basic_site(url: str) -> dict:
    try:
        response = http_session.get(url, timeout=CRAWL_TIMEOUT)
        soup = BeautifulSoup(response.content, "html.parser")
        base_domain = normalize_domain(url)

        analysis = {
            "url": url,
            "status_code": response.status_code,
            "title": soup.title.string.strip() if soup.title and soup.title.string else "No title found",
            "meta_description": "",
            "h1_tags": [],
            "h2_tags": [],
            "images_without_alt": 0,
            "total_images": 0,
            "internal_links": 0,
            "external_links": 0,
            "word_count": 0,
        }

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            analysis["meta_description"] = meta_desc.get("content", "")

        analysis["h1_tags"] = [h1.get_text(" ", strip=True) for h1 in soup.find_all("h1")]
        analysis["h2_tags"] = [h2.get_text(" ", strip=True) for h2 in soup.find_all("h2")][:5]

        images = soup.find_all("img")
        analysis["total_images"] = len(images)
        analysis["images_without_alt"] = sum(1 for img in images if not img.get("alt"))

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue
            if href.startswith("http"):
                if normalize_domain(href) != base_domain:
                    analysis["external_links"] += 1
                else:
                    analysis["internal_links"] += 1
            else:
                analysis["internal_links"] += 1

        text = soup.get_text(" ", strip=True)
        analysis["word_count"] = len(text.split())

        logger.info("Homepage snapshot OK: %s (status %d)", url, response.status_code)
        return analysis

    except Exception as e:
        logger.error("Homepage snapshot failed for %s: %s", url, e)
        return {"error": str(e)}


# ===========================
# LIGHTWEIGHT CRAWLER
# ===========================
def fetch_url(url: str, timeout: int = CRAWL_TIMEOUT):
    try:
        return http_session.get(url, timeout=timeout, allow_redirects=True)
    except Exception as e:
        logger.debug("fetch_url failed for %s: %s", url, e)
        return None


def get_robots_sitemaps(base_url: str) -> list[str]:
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    r = fetch_url(robots_url)
    if not r or r.status_code >= 400:
        return []
    sitemaps = []
    for line in r.text.splitlines():
        if line.lower().startswith("sitemap:"):
            sm = line.split(":", 1)[1].strip()
            if sm:
                sitemaps.append(sm)
    return list(dict.fromkeys(sitemaps))


def try_default_sitemaps(base_url: str) -> list[str]:
    base = base_url.rstrip("/") + "/"
    return [
        urljoin(base, "sitemap.xml"),
        urljoin(base, "sitemap_index.xml"),
        urljoin(base, "sitemap-index.xml"),
    ]


def parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    urls, sitemaps = [], []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return urls, sitemaps

    def _tag_endswith(el, name):
        return el.tag.lower().endswith(name)

    if _tag_endswith(root, "sitemapindex"):
        for el in root.findall(".//"):
            if _tag_endswith(el, "loc") and el.text:
                sitemaps.append(el.text.strip())
    else:
        for el in root.findall(".//"):
            if _tag_endswith(el, "loc") and el.text:
                urls.append(el.text.strip())
    return urls, sitemaps


def fetch_sitemap_urls(sitemap_url: str, max_urls: int = MAX_SITEMAP_URLS) -> list[str]:
    r = fetch_url(sitemap_url)
    if not r or r.status_code >= 400:
        return []
    urls, sitemaps = parse_sitemap_xml(r.text)
    all_urls = list(urls)

    for sm in sitemaps[:20]:
        time.sleep(0.15)
        all_urls.extend(fetch_sitemap_urls(sm, max_urls=max_urls))
        if len(all_urls) >= max_urls:
            break

    deduped = list(dict.fromkeys(all_urls))
    return deduped[:max_urls]


def pick_sample_urls(urls: list[str], homepage_url: str, max_pages: int = MAX_PAGES) -> list[str]:
    urls = [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))]
    urls = list(dict.fromkeys(urls))

    sample = []
    if homepage_url:
        sample.append(homepage_url)

    by_bucket = defaultdict(list)
    for u in urls:
        try:
            p = urlparse(u)
            path = (p.path or "/").strip("/")
            bucket = path.split("/")[0] if path else "_root"
            by_bucket[bucket].append(u)
        except Exception:
            continue

    for _bucket, lst in by_bucket.items():
        if len(sample) >= max_pages:
            break
        chosen = lst[0]
        if chosen not in sample:
            sample.append(chosen)

    for u in urls:
        if len(sample) >= max_pages:
            break
        if u not in sample:
            sample.append(u)

    return sample[:max_pages]


def extract_page_signals(url: str, base_domain: str) -> dict:
    r = fetch_url(url)
    if not r:
        return {"url": url, "final_url": url, "status": None, "error": "request_failed"}

    final_url = r.url
    status = r.status_code
    content_type = (r.headers.get("Content-Type") or "").lower()
    if "text/html" not in content_type:
        return {"url": url, "final_url": final_url, "status": status,
                "content_type": content_type, "error": "non_html"}

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    meta_desc = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md:
        meta_desc = (md.get("content") or "").strip()

    canonical = ""
    canon = soup.find("link", attrs={"rel": lambda x: x and "canonical" in x.lower()})
    if canon:
        canonical = (canon.get("href") or "").strip()

    robots_meta = ""
    rm = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
    if rm:
        robots_meta = (rm.get("content") or "").strip().lower()

    h1_count = len(soup.find_all("h1"))

    text = soup.get_text(" ", strip=True)
    word_count = len(text.split())

    imgs = soup.find_all("img")
    images_total = len(imgs)
    images_missing_alt = sum(1 for img in imgs if not (img.get("alt") or "").strip())

    hreflang_tags = soup.find_all("link", attrs={
        "rel": lambda x: x and "alternate" in x.lower(), "hreflang": True
    })
    hreflang_count = len(hreflang_tags)

    jsonld_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    jsonld_count = len(jsonld_tags)

    internal_links = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        abs_url = href if href.startswith(("http://", "https://")) else urljoin(final_url, href)
        if normalize_domain(abs_url) == base_domain:
            internal_links.append(abs_url)
        if len(internal_links) >= MAX_INTERNAL_LINKS_PER_PAGE:
            break

    return {
        "url": url,
        "final_url": final_url,
        "status": status,
        "title": title,
        "title_len": len(title),
        "meta": meta_desc,
        "meta_len": len(meta_desc),
        "canonical": canonical,
        "robots_meta": robots_meta,
        "h1_count": h1_count,
        "word_count": word_count,
        "images_total": images_total,
        "images_missing_alt": images_missing_alt,
        "hreflang_count": hreflang_count,
        "jsonld_count": jsonld_count,
        "sample_internal_links": internal_links,
    }


def check_links_for_broken(links: list[str]) -> tuple[int, list[dict]]:
    broken = []
    ok = 0
    for link in links:
        try:
            r = http_session.head(link, timeout=CRAWL_TIMEOUT, allow_redirects=True)
            code = r.status_code
            if code >= 400 or code == 0:
                rg = http_session.get(link, timeout=CRAWL_TIMEOUT, allow_redirects=True)
                code = rg.status_code
            if code >= 400:
                broken.append({"url": link, "status": code})
            else:
                ok += 1
        except Exception:
            broken.append({"url": link, "status": None})
        time.sleep(0.05)
        if len(broken) >= MAX_BROKEN_LINKS_REPORTED:
            break
    return ok, broken


def build_site_level_findings(pages: list[dict], base_domain: str) -> tuple[dict, dict]:
    summary = {
        "analyzed_pages": len(pages),
        "status_4xx_5xx": 0,
        "redirects": 0,
        "missing_title": 0,
        "missing_meta": 0,
        "missing_h1": 0,
        "multiple_h1": 0,
        "noindex_pages": 0,
        "missing_canonical": 0,
        "canonical_mismatch": 0,
        "thin_pages": 0,
        "total_images_missing_alt": 0,
        "pages_with_schema": 0,
        "pages_with_hreflang": 0,
    }

    examples = {
        "duplicate_titles": [],
        "duplicate_meta": [],
        "noindex_examples": [],
        "canonical_examples": [],
        "thin_examples": [],
        "status_examples": [],
    }

    titles = defaultdict(list)
    metas = defaultdict(list)

    for p in pages:
        status = p.get("status")
        url = p.get("final_url") or p.get("url")

        if status is None or (isinstance(status, int) and status >= 400):
            summary["status_4xx_5xx"] += 1
            if len(examples["status_examples"]) < 10:
                examples["status_examples"].append({"url": url, "status": status})
        elif (p.get("final_url") or p.get("url")) != p.get("url"):
            summary["redirects"] += 1

        title = (p.get("title") or "").strip()
        meta = (p.get("meta") or "").strip()

        if not title:
            summary["missing_title"] += 1
        else:
            titles[title].append(url)

        if not meta:
            summary["missing_meta"] += 1
        else:
            metas[meta].append(url)

        h1c = safe_int(p.get("h1_count"), 0)
        if h1c == 0:
            summary["missing_h1"] += 1
        elif h1c > 1:
            summary["multiple_h1"] += 1

        robots = (p.get("robots_meta") or "").lower()
        if "noindex" in robots:
            summary["noindex_pages"] += 1
            if len(examples["noindex_examples"]) < 10:
                examples["noindex_examples"].append({"url": url, "robots": robots})

        canonical = (p.get("canonical") or "").strip()
        if not canonical:
            summary["missing_canonical"] += 1
        else:
            try:
                c_abs = urljoin(url, canonical) if canonical.startswith("/") else canonical
                if normalize_domain(c_abs) != base_domain:
                    summary["canonical_mismatch"] += 1
                    if len(examples["canonical_examples"]) < 10:
                        examples["canonical_examples"].append({"url": url, "canonical": canonical})
            except Exception:
                pass

        wc = safe_int(p.get("word_count"), 0)
        if 0 < wc < THIN_CONTENT_THRESHOLD:
            summary["thin_pages"] += 1
            if len(examples["thin_examples"]) < 10:
                examples["thin_examples"].append({"url": url, "word_count": wc})

        summary["total_images_missing_alt"] += safe_int(p.get("images_missing_alt"), 0)
        if safe_int(p.get("jsonld_count"), 0) > 0:
            summary["pages_with_schema"] += 1
        if safe_int(p.get("hreflang_count"), 0) > 0:
            summary["pages_with_hreflang"] += 1

    dup_titles = sorted(
        [(t, urls) for t, urls in titles.items() if len(urls) > 1],
        key=lambda x: len(x[1]),
        reverse=True,
    )
    for t, urls in dup_titles[:5]:
        examples["duplicate_titles"].append({"value": t[:140], "count": len(urls), "urls": urls[:5]})

    dup_meta = sorted(
        [(m, urls) for m, urls in metas.items() if len(urls) > 1],
        key=lambda x: len(x[1]),
        reverse=True,
    )
    for m, urls in dup_meta[:5]:
        examples["duplicate_meta"].append({"value": m[:160], "count": len(urls), "urls": urls[:5]})

    return summary, examples


def run_basic_audit(url_input: str) -> dict:
    base_domain = normalize_domain(url_input)
    if not base_domain:
        raise ValueError("Invalid URL/domain")

    base_url = url_input if url_input.startswith(("http://", "https://")) else "https://" + url_input
    p = urlparse(base_url)
    base_url = f"{p.scheme}://{p.netloc}"

    logger.info("Starting audit for %s", base_domain)

    sitemaps = get_robots_sitemaps(base_url)
    if not sitemaps:
        sitemaps = try_default_sitemaps(base_url)

    discovered_urls = []
    used_sitemap = None
    for sm in sitemaps:
        urls = fetch_sitemap_urls(sm, max_urls=MAX_SITEMAP_URLS)
        if urls:
            discovered_urls = urls
            used_sitemap = sm
            break

    homepage = base_url
    if not discovered_urls:
        sample_urls = [homepage]
        discovery_method = "homepage_only (no sitemap found)"
        urls_discovered_count = 1
    else:
        sample_urls = pick_sample_urls(discovered_urls, homepage, max_pages=MAX_PAGES)
        discovery_method = f"robots/sitemap ({used_sitemap})"
        urls_discovered_count = len(discovered_urls)

    logger.info("Discovered %d URLs, sampling %d", urls_discovered_count, len(sample_urls))

    pages = []
    for u in sample_urls:
        pages.append(extract_page_signals(u, base_domain=base_domain))
        time.sleep(0.12)

    crawl_summary, examples = build_site_level_findings(pages, base_domain=base_domain)

    all_links = []
    for pz in pages:
        for ln in pz.get("sample_internal_links") or []:
            if ln not in all_links:
                all_links.append(ln)
            if len(all_links) >= MAX_BROKEN_LINK_CHECKS:
                break
        if len(all_links) >= MAX_BROKEN_LINK_CHECKS:
            break

    ok_count, broken_examples = check_links_for_broken(all_links)
    crawl_summary["broken_internal_links_checked"] = len(all_links)
    crawl_summary["broken_internal_links_found"] = len(broken_examples)
    examples["broken_links"] = broken_examples

    logger.info("Audit finished: %d pages analyzed, %d broken links found",
                len(pages), len(broken_examples))

    return {
        "domain": base_domain,
        "audit_date": datetime.now().strftime("%B %Y"),
        "discovery_method": discovery_method,
        "urls_discovered": urls_discovered_count,
        "urls_analyzed": len(pages),
        "crawl_summary": crawl_summary,
        "pages": pages,
        "examples": examples,
    }


# ===========================
# AI (Gemini only)
# ===========================
def run_llm(prompt_text: str) -> str:
    model = genai.GenerativeModel("gemini-3-flash-preview")
    resp = model.generate_content(prompt_text)
    return (getattr(resp, "text", "") or "").strip()


def build_prompt(context: dict) -> str:
    p = load_prompt(PROMPT_BASIC).strip()
    if not p:
        p = (
            "You are a senior SEO auditor.\n"
            "Return ONLY Markdown with findings and evidence.\n"
            "CONTEXT_JSON:\n{{CONTEXT_JSON}}\n"
        )
    return p.replace("{{CONTEXT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2))


# ===========================
# DOCX GENERATION (Markdown to docx)
# ===========================
def create_word_from_content(audit_content: str, site_name: str) -> BytesIO:
    doc = Document()
    title = doc.add_heading(f"SEO Audit - {site_name}", 0)
    title.alignment = 1

    subtitle = doc.add_paragraph("Basic Audit")
    subtitle.alignment = 1
    subtitle_run = subtitle.runs[0]
    subtitle_run.font.size = Pt(14)
    subtitle_run.font.color.rgb = RGBColor(96, 165, 250)

    doc.add_paragraph()

    for line in (audit_content or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith(("- ", "* ")):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif re.match(r"^\d+\.", line):
            doc.add_paragraph(re.sub(r"^\d+\.\s*", "", line), style="List Number")
        elif line == "---":
            doc.add_paragraph("_" * 60)
        else:
            doc.add_paragraph(line.replace("**", ""))

    doc.add_paragraph()
    footer = doc.add_paragraph(f"Generated by Quick Wins - {datetime.now().strftime('%B %d, %Y')}")
    footer.alignment = 1
    footer_run = footer.runs[0]
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor(148, 163, 184)

    doc_io = BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    return doc_io


# ===========================
# SIDEBAR
# ===========================
with st.sidebar:
    st.markdown("### System Status")

    if GEMINI_AVAILABLE:
        st.markdown(
            '<span class="status-badge status-connected">Gemini Connected</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-badge status-disconnected">Gemini Offline</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    st.markdown("### About")
    st.markdown("""
    **Quick Wins** generates SEO audits in seconds.

    **Features**:
    - Lightweight site crawl (robots + sitemap)
    - On-page signal analysis
    - AI-powered insights (Gemini)
    - Downloadable Word reports
    """)

    st.markdown("---")
    st.caption("v3.0")


# ===========================
# MAIN INTERFACE
# ===========================
st.markdown("""
<div class="app-header">
    <div class="app-title">QUICK WINS</div>
    <div class="app-subtitle">Instant AI-powered SEO audits. Crawl any site, detect issues, and get actionable recommendations in seconds.</div>
</div>
""", unsafe_allow_html=True)

# Info box
st.info("**SEO Audit** — Crawl via robots.txt + sitemap, sample analysis, duplicates & indexability checks, AI-powered findings.")

st.markdown("---")

# URL Input
url_input = st.text_input(
    "Website URL",
    placeholder="https://example.com",
    help="Enter the full URL including https://"
)

st.markdown("---")

# Generate Button
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if st.button("Audit Now!", disabled=not url_input, use_container_width=True):
        if not GEMINI_AVAILABLE:
            st.error("Gemini API is not configured. Add GOOGLE_API_KEY to your Streamlit secrets.")
            st.stop()

        # Validate URL
        is_valid, result = validate_url(url_input)
        if not is_valid:
            st.error(f"Invalid URL: {result}")
            st.stop()
        clean_url = result

        st.markdown("---")

        progress_bar = st.progress(0)
        status_text = st.empty()

        domain = normalize_domain(clean_url)
        site_name = domain or clean_url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

        # Step 1: Crawl & analyze
        status_text.text("Discovering pages (robots/sitemap) and sampling URLs...")
        progress_bar.progress(20)

        try:
            audit_context = run_basic_audit(clean_url)
        except Exception as e:
            logger.error("Audit crawl failed: %s", e)
            st.error(f"Audit crawl failed: {e}")
            st.stop()

        status_text.text("Taking homepage snapshot...")
        progress_bar.progress(40)

        site_data = analyze_basic_site(clean_url)
        if isinstance(site_data, dict) and "error" in site_data:
            st.error(f"Error analyzing homepage: {site_data['error']}")
            st.stop()

        # Step 2: Generate AI content
        status_text.text("Generating audit content with Gemini...")
        progress_bar.progress(60)

        context = audit_context.copy()
        context["basic_onpage"] = site_data

        try:
            prompt_text = build_prompt(context)
            audit_content = run_llm(prompt_text)
        except Exception as e:
            logger.error("AI generation failed: %s", e)
            st.error(f"AI generation failed: {e}")
            st.stop()

        # Step 3: Create document
        status_text.text("Creating report document...")
        progress_bar.progress(85)

        doc_file = create_word_from_content(audit_content, site_name)

        progress_bar.progress(100)
        status_text.text("Complete!")
        time.sleep(0.5)

        progress_bar.empty()
        status_text.empty()

        # Results
        st.markdown("---")
        st.success("Audit completed successfully!")

        tab1, tab2 = st.tabs(["Preview", "Download"])

        with tab1:
            st.markdown('<div class="audit-report">', unsafe_allow_html=True)
            st.markdown(audit_content)
            st.markdown("</div>", unsafe_allow_html=True)

        with tab2:
            st.markdown("### Download Your Report")
            st.download_button(
                label="Download Report (.docx)",
                data=doc_file,
                file_name=f"SEO_Audit_{site_name}_{datetime.now().strftime('%Y%m%d')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )


# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Quick Wins**")
    st.caption("SEO audits in seconds")

with col2:
    st.markdown("**Powered by**")
    st.caption("Google Gemini")

with col3:
    st.markdown("**Need help?**")
    st.caption("[Documentation](#) | [Support](#)")
