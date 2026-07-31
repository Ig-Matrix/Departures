"""Everything you'll want to tune lives here."""

# ---- filtering -------------------------------------------------------------
MIN_SCORE = 35          # drop anything below this from the board entirely
ALERT_MIN_SCORE = 70    # only email me jobs at least this eligible
INCLUDE_SENIOR = False  # False = junior + mid only
MAX_ALERTS = 25         # cap per digest, so the email stays readable
KEEP_JOBS = 800         # cap the board served to the frontend
SEEN_TTL_DAYS = 0      # forget job hashes older than this

# ---- ATS company boards ----------------------------------------------------
# This list is the single biggest lever on board quality. ATS boards surface
# roles days before the aggregators pick them up.
#
# Finding a slug takes ten seconds: open a company's careers page and read
# the URL.
#     boards.greenhouse.io/monzo   -> greenhouse slug "monzo"
#     jobs.lever.co/voodoo         -> lever slug "voodoo"
#     jobs.ashbyhq.com/ramp        -> ashby slug "ramp"
#
# Wrong slugs cost nothing: they 404 and are skipped. Each run prints a
# per-board count so you can see which ones are actually producing, and
# any board that returns nothing run after run should be pruned.

GREENHOUSE = [
    "stripe",
    "figma",
    "gitlab",
    "databricks",
    "cloudflare",
    "discord",
]

LEVER = [
    "netflix",
    "palantir",
    "voodoo",
]

ASHBY = [
    "ramp",
    "linear",
    "plaid",
    "deel",
]

# ---- aggregator endpoints (no API keys, all free) --------------------------
REMOTIVE = [
    "https://remotive.com/api/remote-jobs?category=software-dev",
    "https://remotive.com/api/remote-jobs?search=power%20automate",
    "https://remotive.com/api/remote-jobs?search=n8n",
]
ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api?visa_sponsorship=true"
JOBICY = "https://jobicy.com/api/v2/remote-jobs?count=50&industry=dev"
