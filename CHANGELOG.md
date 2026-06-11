# Changelog

All notable changes to the Event Scanner project. Routine "Daily scan" data
refreshes (automated, run every morning by GitHub Actions) are not listed
individually — only code/feature changes.

## 2026-06-11

### Fixed
- **Stale "Bought today" P&L note** — `pnl_note` for option positions hardcoded
  "Bought today" at entry time and was only refreshed by a successful daily
  option-quote pull. When that pull failed, the stale "today" wording persisted
  into later days, making positions opened yesterday (or earlier) look like
  they were opened today. `pnl_note` now embeds the actual entry date, and a
  failed quote refresh writes an explicit "Premium quote unavailable (entered
  <date>)" note instead of leaving the old text. (PR #4)

### Attempted fix / still open
- **Option premium + price quotes fail on every GitHub Actions run** —
  `get_current_price()` and `get_option_quote()` (yfinance) return `None` for
  every ticker when run from GitHub Actions ("possibly delisted; no price data
  found", "0/9 prices updated"), even though the same code works fine locally.
  Likely cause: Yahoo Finance blocks/rate-limits GitHub-hosted runner IP ranges.
  - PR #5 routed all yfinance `Ticker` calls through a `curl_cffi` Chrome-
    impersonation session (yfinance's documented cloud workaround). **Did not
    fix it** — yfinance 0.2.54 already uses curl_cffi internally by default, so
    this had no effect. Verified via a manual workflow run (27331025227): still
    "possibly delisted" for all tickers.
  - Real fix likely requires switching price data to the Twelve Data API
    (`TWELVEDATA_KEY` already in `scanner.py`, not currently used) for
    `get_current_price()`. Twelve Data has no options-chain endpoint, so
    `get_option_quote()` (real option P&L) may need a different data source or
    will remain "unavailable" on CI until one is found.
  - **Separately:** `TWELVEDATA_KEY` is currently hardcoded in `scanner.py` in
    this public repo — needs to move to a GitHub secret and be rotated
    (scheduled for 2026-06-12 10:00 AM).

## 2026-06-09

### Added
- **Real option premium P&L tracking** — for STRADDLE and LONG CALL plays, the
  daily update now fetches real bid/ask premiums from yfinance's option chain
  (ATM strike, nearest expiry on/after the exit date), records that as the
  cost basis as if bought the day the trade was added, and marks it to market
  daily for actual premium ROI% (`(REAL)` notes).
- **Portfolio Performance summary** on the dashboard — assumes a flat $1,000
  stake per tracked opportunity and shows total $ P&L, overall ROI%,
  closed-trade ROI%, and win rate across all trades.

### Fixed
- Daily scan workflow now also pushes results to `master` so GitHub Pages
  (served from `master`) stays in sync with `main`.
- Price refresh skips weekends (market closed) and logs any failed fetches
  instead of silently keeping stale data.
- Corrected IB paper account username to `elianpaper30`.

## 2026-06-01

### Added
- `CLAUDE.md` — full project documentation for Claude sessions (architecture,
  scoring system, strategy selection, branches, running locally).

### Fixed
- Daily scan results now pushed to `master` so GitHub Pages updates
  (previously only `main` was updated).

## 2026-05-31

### Added
- Initial event scanner dashboard: scans `DEFAULT_TICKERS` for upcoming
  earnings/events, scores each setup 0-100, and recommends a strategy
  (STRADDLE, LONG CALL, SHARES, DAY TRADE).
- Static `index.html` dashboard generated and published via GitHub Pages,
  refreshed daily at 6 AM PST by GitHub Actions.
- Full project README documenting the strategy, scoring, and IV-crush rules.
