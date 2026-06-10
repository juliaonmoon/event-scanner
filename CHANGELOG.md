# Changelog

All notable changes to the Event Scanner project. Routine "Daily scan" data
refreshes (automated, run every morning by GitHub Actions) are not listed
individually — only code/feature changes.

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
