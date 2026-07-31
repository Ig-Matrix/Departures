"""Fetchers for all six sources, each normalizing to one schema.

All endpoints are public and keyless. Every fetcher returns [] on failure
rather than raising, so one dead board never kills the run.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from . import config
from .classify import strip_html

UA = "departures-jobboard/1.0 (+https://github.com)"
TIMEOUT = 25


def _get(url, retries=2):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 410):
                return None  # dead board, do not retry
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(1.5)
    return None


def _slug(url, idx=0):
    try:
        parts = [p for p in urlparse(url).path.split("/") if p]
        return parts[idx] if len(parts) > idx else "unknown"
    except Exception:
        return "unknown"


def _iso(ts):
    """Epoch seconds or millis -> ISO string."""
    if not ts:
        return None
    try:
        ts = float(ts)
        if ts > 1e11:  # millis
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


# --------------------------------------------------------------- aggregators
def fetch_remotive():
    out = []
    for url in config.REMOTIVE:
        d = _get(url) or {}
        for j in d.get("jobs", []):
            out.append({
                "title": j.get("title"),
                "company": j.get("company_name"),
                "loc": j.get("candidate_required_location") or "Worldwide",
                "url": j.get("url"),
                "posted": j.get("publication_date"),
                "desc": strip_html(j.get("description"))[:1500],
                "tags": (j.get("tags") or [])[:4],
                "source": "Remotive",
            })
    return out


def fetch_arbeitnow():
    d = _get(config.ARBEITNOW) or {}
    return [{
        "title": j.get("title"),
        "company": j.get("company_name"),
        "loc": j.get("location") or "Europe",
        "url": j.get("url"),
        "posted": _iso(j.get("created_at")),
        "desc": strip_html(j.get("description"))[:1500],
        "tags": (j.get("tags") or [])[:4],
        "source": "Arbeitnow",
        "visa_hint": True,
    } for j in d.get("data", [])]


def fetch_jobicy():
    d = _get(config.JOBICY) or {}
    return [{
        "title": j.get("jobTitle"),
        "company": j.get("companyName"),
        "loc": j.get("jobGeo") or "Worldwide",
        "url": j.get("url"),
        "posted": j.get("pubDate"),
        "desc": strip_html(j.get("jobExcerpt") or j.get("jobDescription"))[:1500],
        "tags": (j.get("jobIndustry") or [])[:4],
        "source": "Jobicy",
    } for j in d.get("jobs", [])]


# ----------------------------------------------------------------- ATS boards
def fetch_greenhouse(slug):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not d:
        return []
    return [{
        "title": j.get("title"),
        "company": slug,
        "loc": (j.get("location") or {}).get("name") or "See posting",
        "url": j.get("absolute_url"),
        "posted": j.get("updated_at"),
        "desc": strip_html(j.get("content"))[:1500],
        "tags": [],
        "source": "Greenhouse",
    } for j in d.get("jobs", [])]


def fetch_lever(slug):
    # Lever returns a flat array, and returns an empty one both for unknown
    # companies AND for companies with zero openings. Those two are
    # indistinguishable, so a silent board may just mean "nothing open".
    d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=100")
    if not isinstance(d, list):
        return []
    out = []
    for j in d:
        cats = j.get("categories") or {}
        out.append({
            "title": j.get("text"),
            "company": slug,
            "loc": cats.get("location") or "See posting",
            "url": j.get("hostedUrl"),
            "posted": _iso(j.get("createdAt")),
            "desc": strip_html(j.get("descriptionPlain") or j.get("description"))[:1500],
            "tags": [c for c in [cats.get("team")] if c],
            "source": "Lever",
        })
    return out


def fetch_ashby(slug):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if not d:
        return []
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:  # unlisted roles are not open applications
            continue
        out.append({
            "title": j.get("title"),
            "company": slug,
            "loc": j.get("location") or "See posting",
            "url": j.get("jobUrl"),
            "posted": j.get("publishedAt"),
            "desc": strip_html(j.get("descriptionHtml") or j.get("descriptionPlain"))[:1500],
            "tags": [t for t in [j.get("department"), j.get("team")] if t],
            "source": "Ashby",
        })
    return out


def collect_all():
    """Fetch every source in parallel. Returns (jobs, health-by-source)."""
    tasks = [("Remotive", fetch_remotive), ("Arbeitnow", fetch_arbeitnow),
             ("Jobicy", fetch_jobicy)]
    tasks += [("Greenhouse", lambda s=s: fetch_greenhouse(s)) for s in config.GREENHOUSE]
    tasks += [("Lever", lambda s=s: fetch_lever(s)) for s in config.LEVER]
    tasks += [("Ashby", lambda s=s: fetch_ashby(s)) for s in config.ASHBY]

    jobs, health = [], {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks}
        for fut, name in futures.items():
            try:
                rows = fut.result()
            except Exception as e:
                print(f"  ! {name} failed: {e}")
                rows = []
            health[name] = health.get(name, 0) + len(rows)
            jobs.extend(rows)
    return jobs, health
