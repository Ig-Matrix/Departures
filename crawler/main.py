"""DEPARTURES crawler.

Run:  python -m crawler.main

Fetches every source, classifies and scores each role, diffs against what it
saw last time, writes docs/jobs.json for the frontend, and emails a digest of
anything new worth looking at.

data/seen.json is this pipeline's memory between runs. Without it, "new since
last time" is unknowable and the alerts have nothing to be about.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, digest
from .classify import categorize, job_hash, level_of, score, subtracks
from .sources import collect_all

ROOT = Path(__file__).resolve().parent.parent
SEEN_PATH = ROOT / "data" / "seen.json"
OUT_PATH = ROOT / "docs" / "jobs.json"


def load_seen():
    if not SEEN_PATH.exists():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text())
    except Exception:
        print("  ! seen.json unreadable, treating as first run")
        return {}


def save_seen(seen):
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, separators=(",", ":"), sort_keys=True))


def process(raw):
    """Classify, score and filter. Returns the kept jobs."""
    kept, seen_hashes = [], set()

    for j in raw:
        if not j.get("title") or not j.get("url"):
            continue

        blob = " ".join([j["title"], " ".join(j.get("tags") or []), j.get("desc", "")])
        cat = categorize(blob)
        if not cat:
            continue

        lvl = level_of(j["title"])
        if not config.INCLUDE_SENIOR and lvl == "senior":
            continue

        sc = score(j["title"], j.get("loc", ""), j.get("desc", ""))
        if j.get("visa_hint"):
            sc["mode"] = "visa"
        if sc["score"] < config.MIN_SCORE:
            continue

        h = job_hash(j.get("company", ""), j["title"], j.get("loc", ""))
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        kept.append({
            "hash": h,
            "title": j["title"],
            "company": j.get("company") or "Unknown",
            "loc": j.get("loc") or "",
            "url": j["url"],
            "posted": j.get("posted"),
            "source": j["source"],
            "category": cat,
            "level": lvl,
            "subtracks": subtracks(blob),
            "score": sc["score"],
            "mode": sc["mode"],
            "reasons": sc["reasons"],
            "tags": (j.get("tags") or [])[:4],
        })
    return kept


def main():
    started = time.time()
    print("DEPARTURES crawl starting")

    raw, health = collect_all()
    print(f"  fetched {len(raw)} raw postings")
    for k in sorted(health):
        print(f"    {k:<12} {health[k]}")

    jobs = process(raw)
    print(f"  kept {len(jobs)} after classify + score")

    if not jobs:
        # Never overwrite a good board with an empty one. A total wipe here
        # almost always means a network blip, not that every job vanished.
        print("  ! nothing kept, leaving the existing board untouched")
        return 0

    seen = load_seen()
    first_run = not seen
    now = int(time.time())

    fresh = []
    for j in jobs:
        j["is_new"] = j["hash"] not in seen
        if j["is_new"]:
            fresh.append(j)
        seen[j["hash"]] = now

    # prune old hashes so state does not grow forever
    cutoff = now - config.SEEN_TTL_DAYS * 86400
    seen = {k: v for k, v in seen.items() if v >= cutoff}

    # newest first within each score band: sort by date desc, then stable-sort
    # by score desc so the date ordering survives inside equal scores
    jobs.sort(key=lambda j: j["posted"] or "", reverse=True)
    jobs.sort(key=lambda j: j["score"], reverse=True)
    jobs = jobs[:config.KEEP_JOBS]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "health": health,
        "jobs": jobs,
    }, separators=(",", ":")))
    print(f"  wrote {OUT_PATH.name} ({len(jobs)} jobs)")

    save_seen(seen)

    alerts = sorted(
        (j for j in fresh if j["score"] >= config.ALERT_MIN_SCORE),
        key=lambda j: -j["score"],
    )[:config.MAX_ALERTS]

    if first_run:
        # On a cold start every job looks new. Emailing hundreds of roles as
        # "new" would be noise, and worse, it teaches you to ignore the digest.
        print(f"  first run: seeding state with {len(jobs)} jobs, no email sent")
    elif alerts:
        plural = "" if len(alerts) == 1 else "s"
        digest.send(
            f"DEPARTURES: {len(alerts)} new role{plural}",
            digest.build_html(alerts, len(fresh), len(jobs), health,
                              os.environ.get("BOARD_URL")),
        )
    else:
        print(f"  {len(fresh)} new, none above score {config.ALERT_MIN_SCORE}, no email")

    print(f"done in {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
