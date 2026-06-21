# Event Scanner — Status

## What this project is
A stock event scanner that finds upcoming catalysts (earnings, etc.), scores
setups 0-100, and recommends a trade strategy (STRADDLE, LONG CALL, SHARES,
DAY TRADE). For Julia's own trading research. Outputs two linked static HTML
dashboards: the scanner itself, and a Market Events Calendar (FOMC, CPI/PPI/
jobs reports, GDP, notable earnings, IPOs). Both auto-updated daily.

## Stack & services
- **Live scanner dashboard:** https://juliaonmoon.github.io/event-scanner/ (GitHub Pages, served from `master`)
- **Live calendar dashboard:** https://juliaonmoon.github.io/event-scanner/calendar.html
- **Repo:** https://github.com/juliaonmoon/event-scanner (public)
- **Local code:** `C:\Users\jules\event-scanner\`
- **Daily refresh:** runs via **cron on the trading-bots VPS** (206.189.184.84 — same box as the bots, see the VPS bots project notes), NOT GitHub Actions (moved 2026-06-12, see Hard-won gotchas). Schedule lives in `/etc/cron.d/event_scanner` on the VPS (own file, parallel to the bots' `bot_session_reset`/`bot_watchdog` — not in root's personal crontab, not in this git repo). Fires `0 12 * * *` (8:00 AM ET), wrapped in `timeout 10m`; on failure or timeout, emails the user via `alert_on_failure.py`.
- `.github/workflows/daily_scan.yml` still exists but is manual-`workflow_dispatch`-only (schedule disabled) — kept for ad-hoc runs, but yfinance is blocked from GitHub-hosted runner IPs (see gotchas), so it mostly won't produce useful price data.
- Run locally: `cd C:\Users\jules\event-scanner && python update.py` (full update, regenerates both dashboards) or `python scanner.py [TICKERS...]` (scan only, no writes) or `python calendar_events.py` (calendar only, no writes outside its own JSON/HTML)

## File map
- `C:\Users\jules\event-scanner\scanner.py` — core logic: earnings dates, IV, historical reactions, scoring, `get_current_price`/`get_option_quote`/`pick_expiry` (yfinance wrappers), `DEFAULT_TICKERS` watchlist
- `C:\Users\jules\event-scanner\update.py` — daily runner: refresh prices/P&L, archive expired, generate `index.html`, then calls `calendar_events.main()`. `set_option_baseline()`/`update_option_pnl()` handle real option P&L.
- `C:\Users\jules\event-scanner\calendar_events.py` — Market Events Calendar: hardcoded full-2026 FOMC/CPI/PPI/jobs-report/GDP dates, notable earnings (extends `DEFAULT_TICKERS` with mega-cap/financial/industrial/retail names via `get_earnings_date`), best-effort IPO scrape of stockanalysis.com, generates `calendar.html`
- `C:\Users\jules\event-scanner\alert_on_failure.py` — emails the user (Resend API, reusing the bots' `/etc/bot_alert.conf`) with the cron log tail if the VPS daily run fails or times out
- `C:\Users\jules\event-scanner\opportunities.json` — persistent opportunity store, committed to repo
- `C:\Users\jules\event-scanner\calendar_events.json` — persistent calendar event store, committed to repo (debugging aid; calendar.html embeds the same data inline)
- `C:\Users\jules\event-scanner\index.html` / `calendar.html` — generated static dashboards, cross-linked via a nav button in each header
- `C:\Users\jules\event-scanner\.github\workflows\daily_scan.yml` — manual-dispatch-only workflow (see Stack & services)
- `C:\Users\jules\event-scanner\vps_daily_run.sh` — the script the VPS cron actually runs: git pull main → `update.py` → commit + force-push `master`
- `C:\Users\jules\event-scanner\CHANGELOG.md` — code/feature change log (not routine data refreshes)
- VPS-side, not in this repo: `/etc/cron.d/event_scanner` (schedule), `/etc/bot_alert.conf` (Resend creds, root-only 600 perms, shared with the bots' own watchdog)
- `C:\Users\jules\bot projects\PRIVATE.docx` — credentials (local only, never committed)

## What works (verified)
- VPS cron runs daily, regenerates both `index.html` and `calendar.html`, commits to `main`, force-pushes `index.html`+`calendar.html`+`opportunities.json`+`calendar_events.json` to `master` (verified via VPS logs.log and live site, 2026-06-21).
- Calendar shows all 12 months of 2026 macro events (90 total events as of 2026-06-21: 8 FOMC, 12 each JOBS/CPI/PPI, 4 GDP, 39 earnings, 3 IPO) — confirmed via `calendar_events.json` after a local run.
- Nav links between `index.html` ↔ `calendar.html` work both directions (verified in browser preview).
- `alert_on_failure.py` confirmed working end-to-end on the VPS — sent a real test email via Resend, delivered successfully (2026-06-21).
- `pnl_note` for option positions shows the real entry date and an explicit "unavailable" message on failed quote refresh (verified via manual run 27330538453, 2026-06-11).

## Hard-won gotchas
- **yfinance fails on GitHub Actions runners** — `get_current_price()`/`get_option_quote()`/earnings lookups return `None`/"possibly delisted" for every ticker when run from GitHub Actions, but work fine locally and from the VPS. Root cause: Yahoo blocks GitHub-hosted runner IP ranges. A `curl_cffi` Chrome-impersonation session (PR #5) had **no effect** — yfinance already bundles curl_cffi by default. **Real fix applied 2026-06-12:** moved the daily cron off GitHub Actions entirely, onto the trading-bots VPS (dedicated IP, no IP-range block). The GH Actions workflow still exists for manual runs but will likely still hit this.
- **Resend API blocks default urllib User-Agent (HTTP 403, "error code: 1010")** — Resend sits behind Cloudflare, which flags Python's default `urllib` User-Agent as a bot signature and silently blocks the request. Fix: add `headers={"User-Agent": "Mozilla/5.0"}` to the `urllib.request.Request` call. Found 2026-06-21 while building `alert_on_failure.py`. **The trading bots' own `/opt/scripts/watchdog.py` likely has this exact same bug** (same urllib pattern, no custom UA) and has simply never needed to fire recently — flagged as a separate task (not part of this repo) to verify/fix.
- **Windows `open()` defaults to cp1252, not UTF-8** — `calendar_events.py`'s JSON write originally omitted `encoding="utf-8"`, silently mangling non-ASCII characters (e.g. em dashes in IPO labels) into `�` when run locally on Windows. Always pass `encoding="utf-8"` explicitly on any file write here, since this repo runs on both Windows (local/dev) and Linux (VPS).
- **IPO calendar is inherently short-range** — stockanalysis.com's own IPO calendar rarely has confirmed dates more than 1-2 weeks out (industry-wide — IPO dates just aren't set that far ahead). Don't expect `get_ipo_events()` to populate much even though the calendar view spans all of 2026; that's expected, not a bug.
- **`pnl_note` text vs `option_entry_date`** — `set_option_baseline()` sets `option_entry_date` once, but the human-readable `pnl_note` is separately regenerated by `update_option_pnl()` only on success. If that fetch fails, the old note text persists verbatim into future days — any "as of today" wording in a note must embed an actual date, never the word "today" (fixed PR #4).

## Pending / blocked
- **Rotate `TWELVEDATA_KEY`** — still hardcoded in `scanner.py` in this public repo, unused for the main scan. Real exposure risk (it's a live API key in a public GitHub repo) independent of the CI-migration motivation below, which is now moot.
- **yfinance-on-CI migration to Twelve Data is now moot** — the original motivation (Yahoo blocking GitHub Actions IPs) was solved by moving the cron to the VPS instead, which has a dedicated IP and works fine with yfinance directly. No need to migrate data sources unless GitHub Actions needs to become reliable again for some other reason.
- **Trading bots' watchdog.py Resend bug** — likely has the same Cloudflare/User-Agent block described above. Flagged as background task `task_f5aaf213` (2026-06-21); not yet confirmed fixed. This is bot infra, not part of this repo.

## Conventions
- Branch → PR → squash-merge → delete branch, per `C:\Users\jules\.claude\CLAUDE.md` global workflow (this repo uses `main`, not `master`, for development; `master` is GitHub Pages output only and is force-pushed by the VPS cron, not CI).
- Doc-only changes (CHANGELOG, STATUS, HANDOFF) still go through a PR per the global workflow, but don't need CI verification beyond "PR mergeable" — there is no automated test suite in this repo, so "CI passing" in practice means manual verification (local run + browser check) before merge.
- Bug/issue tracking for this repo lives in `CHANGELOG.md` (not the trading-bots `BUGS.md`, which is a different project).
- VPS-side infra changes (cron schedule, `/etc/bot_alert.conf`) are made directly via SSH, not tracked in this git repo — only the scripts they invoke (`vps_daily_run.sh`, `alert_on_failure.py`) live in git.
