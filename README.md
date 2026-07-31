# DEPARTURES

A job board that surfaces junior-to-mid **Automation / Frontend / Backend** roles
open to applicants based in Nigeria, scored for eligibility and delivered as a
daily email digest.

Runs entirely on free infrastructure. No servers, no database, no paid tier.

```
GitHub Actions (cron)  ->  crawler  ->  docs/jobs.json  ->  GitHub Pages
                              |
                              +------->  digest email (SMTP)
```

## What it costs

| Piece | Cost |
|---|---|
| GitHub Actions | Free. Public repos get unlimited minutes |
| GitHub Pages | Free for public repos |
| Job APIs (Remotive, Arbeitnow, Jobicy) | Free, no API key |
| ATS boards (Greenhouse, Lever, Ashby) | Free, public, no auth |
| Email via Gmail SMTP | Free |

Total: nothing.

---

## Setup

### 1. Create the repo

Make it **public** — that's what makes Actions minutes unlimited and Pages free.

```bash
git init
git add .
git commit -m "DEPARTURES: crawler, board and digest"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/departures.git
git push -u origin main
```

### 2. Turn on GitHub Pages

Repo **Settings → Pages → Source: Deploy from a branch → `main` / `/docs` → Save.**

Your board goes live at `https://YOUR_USERNAME.github.io/departures/` within a
minute or two.

### 3. Set up email

Gmail needs an **App Password**, not your normal password. Turn on 2-Step
Verification first (App Passwords don't exist without it), then generate one at
Google Account → Security → App passwords.

Repo **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASS` | the 16-character App Password |
| `MAIL_TO` | where the digest should land |

Then on the **Variables** tab add `BOARD_URL` set to your Pages URL, so each
digest links back to the full board.

Skip this step entirely and everything still works — the crawler just prints
that email isn't configured and carries on.

### 4. Fix the company board list

Open `crawler/config.py`. The `GREENHOUSE`, `LEVER` and `ASHBY` lists hold
starter slugs that are educated guesses. Some will be wrong.

This list is the single biggest lever on board quality, because ATS boards
surface roles days before the aggregators pick them up. Finding a slug takes
ten seconds:

| ATS | Careers page | Slug |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/`**`monzo`** | `monzo` |
| Lever | `jobs.lever.co/`**`voodoo`** | `voodoo` |
| Ashby | `jobs.ashbyhq.com/`**`ramp`** | `ramp` |

Wrong slugs cost nothing: they 404 and get skipped. Every run prints a
per-source count, so watch the log (or the Board health line in your digest)
and prune whatever stays at zero.

Keep the combined list under roughly 25 to start.

**One catch specific to Lever:** it returns an empty array both for an unknown
company *and* for a real company with zero openings. Those two are
indistinguishable, so a silent Lever board isn't necessarily a wrong slug.

### 5. Run it

**Locally first:**

```bash
pip install -r requirements.txt
python -m crawler.main
```

**Then on GitHub:** Actions tab → **crawl** → **Run workflow**.

The first run seeds state and deliberately sends no email. On a cold start
every job looks new, and a digest of 300 "new" roles is noise that teaches you
to ignore the next one. From the second run onward you only get genuine
arrivals.

### 6. View the board

Open your Pages URL. It reads `docs/jobs.json` from the same origin, so it
loads instantly and CORS never comes up.

To work on it locally, serve the folder rather than opening the file directly
(`file://` breaks the fetch):

```bash
cd docs && python -m http.server 5500
```

Then open `http://localhost:5500`. In VS Code the Live Server extension does
the same thing from a right-click.

---

## Tuning

All in `crawler/config.py`:

| Setting | Default | What it does |
|---|---|---|
| `MIN_SCORE` | 35 | Below this, a job never reaches the board |
| `ALERT_MIN_SCORE` | 70 | Below this, a new job never emails you |
| `INCLUDE_SENIOR` | `False` | Junior + mid only |
| `MAX_ALERTS` | 25 | Cap per digest |
| `KEEP_JOBS` | 800 | Cap on the published board |
| `SEEN_TTL_DAYS` | 45 | How long a job stays "already seen" |

Crawl times live in `.github/workflows/crawl.yml`. Cron there is **UTC**. Lagos
is UTC+1 with no daylight saving, so subtract one hour from the local time you
want. The default `0 5,11,17 * * 1-5` is 06:00 / 12:00 / 18:00 Lagos, weekdays.

Scheduled runs drift 5-30 minutes at peak times because Actions uses a shared
runner pool. That doesn't matter for a job board, but it's why this approach
isn't suitable for anything time-critical.

**Start `ALERT_MIN_SCORE` high and lower it later.** Tuning down from too-quiet
is easy. An alert you've started skimming past is hard to start trusting again.

---

## How scoring works

Every job gets 0-100 for **how open it is to you applying from Nigeria**, which
is not the same as how good the job is. It starts at 50, then:

- **Up** for `nigeria` (+45), `africa` (+35), `worldwide` (+30), `emea` (+18)
- **Up** for `visa sponsorship` (+40), `relocation package` (+30)
- **Down** for `must be authorized to work in the united states` (-70),
  `us only` (-60), `must be based in` (-40), `no visa sponsorship` (-35)

The negative rules matter most. A large share of jobs labelled "Remote" are
quietly "Remote, US only", and filtering those out saves more time than
anything else in the pipeline. Anything scoring 26+ on visa signals gets tagged
VISA rather than REMOTE.

The keyword lists are at the top of `crawler/classify.py`. Add phrases as you
spot them — every false positive you fix is a wasted application avoided.

---

## The one maintenance gotcha

GitHub **disables scheduled workflows after 60 days of repository inactivity**.
You get one email about it that's easy to miss, after which the crawler stops
silently.

This repo dodges that automatically: every run commits `docs/jobs.json` and
`data/seen.json`, which counts as activity. So as long as it's running, it keeps
itself alive. Worth knowing anyway, in case you ever pause it for a couple of
months.

---

## Layout

```
crawler/
  config.py      tunables + ATS company lists   <- edit this most
  sources.py     the six fetchers
  classify.py    track classification + eligibility scoring
  digest.py      email HTML + SMTP send
  main.py        orchestration, diffing, publishing
docs/
  index.html     the board
  jobs.json      generated each run
data/
  seen.json      the pipeline's memory between runs
.github/workflows/crawl.yml
```

`data/seen.json` is what makes "new since last time" knowable. Delete it and the
next run is treated as a cold start.
