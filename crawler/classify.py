"""Track classification and Nigeria-eligibility scoring."""

import hashlib
import html
import re

CAT = {
    "automation": [
        "automation", "rpa", "power automate", "power apps", "powerapps",
        "power platform", "microsoft flow", "n8n", "zapier", "make.com",
        "workflow automation", "low-code", "no-code", "nocode", "lowcode",
        "uipath", "automation anywhere", "blue prism", "dataverse",
        "integration engineer", "etl developer", "process automation",
    ],
    "frontend": [
        "frontend", "front-end", "front end", "react", "angular", "vue.js",
        "svelte", "next.js", "nextjs", "nuxt", "tailwind", "ui engineer",
        "ui developer", "web developer", "javascript developer",
    ],
    "backend": [
        "backend", "back-end", "back end", "node.js", "django", "flask",
        "fastapi", "spring boot", "laravel", "asp.net", "golang",
        "ruby on rails", "microservice", "python developer", "api engineer",
        "platform engineer", ".net developer",
    ],
}

SUBTRACK = {
    "power-automate": ["power automate", "power platform", "microsoft flow", "rpa"],
    "power-apps": ["power apps", "powerapps", "canvas app", "dataverse", "model-driven"],
    "n8n": ["n8n", "zapier", "make.com", "workflow automation", "no-code", "low-code"],
    "python": ["python"],
}

# Signals a role is genuinely open to someone applying from Nigeria.
OPEN = [
    ("nigeria", 45), ("africa", 35), ("worldwide", 30),
    ("work from anywhere", 30), ("remote - global", 30),
    ("anywhere in the world", 30), ("globally distributed", 22),
    ("fully distributed", 20), ("any location", 22), ("emea", 18),
    ("anywhere", 18),
]

# Signals it is quietly geo-locked. These matter most: a large share of jobs
# labelled "Remote" are really "Remote, US only", and filtering those is the
# single biggest time saver in the pipeline.
BLOCK = [
    ("must be authorized to work in the united states", -70),
    ("authorized to work in the us", -60),
    ("us citizens only", -70), ("security clearance", -70),
    ("green card", -55), ("us only", -60), ("usa only", -60),
    ("eu residents", -45), ("must reside in", -40),
    ("must be located in", -40), ("must be based in", -40),
    ("work authorization in", -45), ("no visa sponsorship", -35),
    ("unable to sponsor", -35), ("cannot sponsor", -35), ("hybrid", -15),
]

VISA = [
    ("visa sponsorship", 40), ("sponsorship available", 40), ("we sponsor", 40),
    ("relocation package", 30), ("relocation assistance", 26),
    ("relocation support", 26), ("work permit", 20),
]

_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
_JUNIOR_RE = re.compile(r"\b(junior|jr\.?|entry[- ]level|graduate|intern|trainee|apprentice)\b", re.I)
_SENIOR_RE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|head of|director|vp|architect|manager)\b", re.I)


def strip_html(s):
    """Greenhouse serves descriptions as HTML that is itself HTML-escaped, so
    it has to be unescaped BEFORE tags are stripped. Miss this and every
    Greenhouse description arrives as literal &lt;p&gt; noise."""
    if not s:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(str(s)))).strip()


def job_hash(company, title, loc):
    raw = f"{company}|{title}|{loc}".lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def level_of(title):
    t = title or ""
    if _JUNIOR_RE.search(t):
        return "junior"
    if _SENIOR_RE.search(t):
        return "senior"
    return "mid"


def categorize(text):
    t = text.lower()
    if any(w in t for w in CAT["automation"]):
        return "automation"
    f = any(w in t for w in CAT["frontend"])
    b = any(w in t for w in CAT["backend"])
    if f and not b:
        return "frontend"
    if b:
        return "backend"
    return None


def subtracks(text):
    t = text.lower()
    return [k for k, words in SUBTRACK.items() if any(w in t for w in words)]


def score(title, loc, desc):
    """0-100 for how open this role is to an applicant based in Nigeria.
    Note this measures eligibility, not job quality."""
    hay = f"{loc} {title} {desc}".lower()
    s, reasons, visa_pts = 50, [], 0

    for w, p in OPEN:
        if w in hay:
            s += p
            reasons.append(f"+ {w}")
            break
    for w, p in VISA:
        if w in hay:
            s += p
            visa_pts += p
            reasons.append(f"+ {w}")
            break
    for w, p in BLOCK:
        if w in hay:
            s += p
            reasons.append(f"- {w}")

    return {
        "score": max(0, min(100, s)),
        "reasons": reasons[:3],
        "mode": "visa" if visa_pts >= 26 else "remote",
    }
