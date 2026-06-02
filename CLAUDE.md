# Event Scanner — Claude Instructions

## What this project is

A stock event scanner that finds upcoming catalysts (earnings, product launches, conferences),
scores each setup 0–100, and recommends a trade strategy (STRADDLE, LONG CALL, SHARES, DAY TRADE).

Outputs a static HTML dashboard auto-updated daily via GitHub Actions.

**Live dashboard:** https://juliaonmoon.github.io/event-scanner/
**GitHub repo:** https://github.com/juliaonmoon/event-scanner (public)
**Local code:** C:\Users\jules\event-scanner\

---

## Architecture

This project runs entirely on GitHub infrastructure — no VPS, no local server.

| Component | What it does | Where |
|-----------|-------------|-------|
| `scanner.py` | Core logic: fetches earnings dates, IV, historical reactions, scores setups | GitHub repo |
| `update.py` | Daily runner: refreshes prices, archives expired opps, generates index.html | GitHub repo |
| `opportunities.json` | Persistent store of all opportunities, committed to repo | GitHub repo |
| `index.html` | Generated static dashboard, served by GitHub Pages | GitHub repo |
| `.github/workflows/daily_scan.yml` | Cron job: runs update.py at 6 AM PST daily | GitHub Actions |

**Data flow:** GitHub Actions runs `update.py` → commits `opportunities.json` + `index.html` to both
`main` and `master` → GitHub Pages serves `index.html` from `master`.

---

## Branches

- `main` — active development branch; GitHub Actions workflows live here
- `master` — GitHub Pages source; must stay in sync with main

**Important:** The daily scan workflow pushes to both branches (`git push origin HEAD:master`).
This was fixed on 2026-06-01 — previously master was not being updated.

---

## Interactive Brokers Account

IB account for this project (for future live/paper trading integration).
**Credentials are in PRIVATE.docx** (local only, never committed).

- Login: `elianpaper30`
- URL: clientportal.ibkr.com

---

## Watchlist (DEFAULT_TICKERS in scanner.py)

```
RKLB, LUNR, ASTS, SPCE     # SpaceX-adjacent / space
LMT, NOC, RTX, BA           # Aerospace / defense
NVDA, AMD, TSLA, AAPL, META, GOOGL  # High-event tech
MRNA, BNTX, RXRX, ACAD     # Biotech / FDA events
```

To add tickers: edit `DEFAULT_TICKERS` in `scanner.py`, commit, push.

---

## Scoring system (scanner.py: score_and_suggest)

| Factor | Points |
|--------|--------|
| Avg historical move ≥ 10% | +25 |
| Avg historical move ≥ 5% | +15 |
| Win rate ≥ 70% (bullish bias) | +20 |
| Win rate ≤ 30% (bearish bias) | +15 |
| IV underpricing vs history | +15 |
| Momentum confirms direction | +10 |
| No directional bias (45–55%) | -5 |
| IV already pricing in move | -10 |

Thresholds: 40+ = high confidence | 25–39 = moderate | below 20 = AVOID

---

## Strategy selection (update.py: add_new_opps)

| Condition | Strategy |
|-----------|----------|
| Event is today or tomorrow | DAY TRADE |
| IV ratio < 0.85 AND clear directional bias | STRADDLE |
| Win rate ≥ 65% | LONG CALL |
| Otherwise | STRADDLE |

**Core rule: always exit the day before the event.** We capture pre-event run-up, not the reaction.

---

## Opportunity lifecycle

```
ACTIVE → EXITED (day before event) → ARCHIVED (7 days after event)
```

---

## Running locally

```bash
cd C:\Users\jules\event-scanner
pip install -r requirements.txt

# Full update (refresh prices, scan new events, generate index.html)
python update.py

# Scan only (prints table, no file writes)
python scanner.py
python scanner.py AAPL NVDA RKLB   # custom tickers
```

---

## Manual dashboard refresh

Go to: https://github.com/juliaonmoon/event-scanner/actions
→ "Daily Event Scan" → "Run workflow"

---

## Data source

`yfinance` (Yahoo Finance) — free, no API key needed.
Twelve Data API key is also in `scanner.py` but not currently used for the main scan.

---

## Secrets / credentials

Nothing secret is committed to this repo. It is public.
All credentials are in `C:\Users\jules\bot projects\PRIVATE.docx`.

---

## Known issues / limitations

- yfinance occasionally returns stale/missing data
- Earnings dates are estimates for unconfirmed quarters — verify on IR page before trading
- P&L shown on dashboard is estimated, not actual
- Prices update once daily at 6 AM PST, not real-time
