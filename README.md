# Event Scanner

Scans for stocks with upcoming catalysts (earnings, product launches, major events), scores each setup, and recommends whether to day trade or swing trade — with specific entry, instrument, and exit instructions.

Dashboard auto-updates every morning at 6 AM PST with fresh prices and new opportunities.

**Live dashboard:** https://juliaonmoon.github.io/event-scanner/
**Repo:** https://github.com/juliaonmoon/event-scanner

---

## Why this exists

Most traders either:
- Miss events entirely (no systematic scan)
- Hold through earnings and get destroyed by IV crush
- Buy options without knowing if IV is cheap or expensive

This scanner solves all three:
1. Finds stocks with events coming in the next 90 days
2. Scores each one based on historical reaction size, directional bias, and whether IV is cheap/expensive
3. Tells you exactly what to buy, when to enter, and — critically — when to exit before the event

---

## The core rule

> **Always exit before the earnings report drops. No exceptions.**

We are swing traders capturing the pre-earnings run-up — not gambling on the number. The edge is in the anticipation, not the reaction.

| Instrument | Exit timing |
|-----------|-------------|
| Shares | Day before event |
| Calls / Puts | Day before event |
| Straddle | Day before event |

---

## What is IV and why it matters

**IV (Implied Volatility)** is the market's expectation of how much a stock will move, derived from options prices. If IV says 8% on a $100 stock, the options market expects roughly an $8 move.

**IV Crush** — after an earnings announcement, IV collapses instantly because the uncertainty is gone. Even if the stock moves your way, your option can lose value because IV dropped out of it. This is why we exit before the report.

**The key comparison in this scanner:**

| Situation | Meaning | Play |
|-----------|---------|------|
| IV < historical avg move | Options underpriced — cheap to buy | Straddle or directional |
| IV ≈ historical avg move | Fairly priced | Directional only if you have bias |
| IV > historical avg move | Options overpriced — market already scared | Avoid options, shares only if momentum |

---

## Scoring system

Each opportunity is scored 0–100 based on:

| Factor | Points |
|--------|--------|
| Historical avg move ≥ 10% | +25 |
| Historical avg move ≥ 5% | +15 |
| Win rate ≥ 70% (bullish bias) | +20 |
| Win rate ≤ 30% (bearish bias) | +15 |
| IV underpricing history | +15 |
| Momentum confirms direction | +10 |
| Win rate 45–55% (no bias) | -5 |
| IV already pricing in move | -10 |

**Score thresholds:**
- 40+ = high confidence, act on it
- 25–39 = moderate, smaller size
- below 20 = AVOID

---

## Strategy types

### STRADDLE
Buy both an ATM call and ATM put, same strike, same expiry.

Use when: direction is unclear (win rate near 50%) but the move is reliably big, AND IV is underpriced.

You profit from IV rising as the event approaches — not necessarily from the stock moving. Exit the day before earnings when IV has expanded.

Example: RKLB — IV pricing 5.8% move, historical avg is 10.5%. Buy the straddle now, sell when IV rises to match history.

### LONG CALL
Buy an ATM or slightly OTM call.

Use when: win rate ≥ 65% (strong bullish bias), IV is underpriced or fair.

Example: GOOGL — 80% historical win rate going up on earnings. Buy a call, ride the pre-earnings drift, exit day before.

### SHARES (momentum only)
Buy the stock outright.

Use when: stock is already running hard on news/momentum, but IV is too expensive for options. Higher risk, simpler execution.

Example: SPCE after a +90% run — options spreads too wide, shares easier to manage.

### DAY TRADE
Buy at open on the event day, sell same day.

Use when: the event is today or tomorrow, stock has a history of big intraday moves on the catalyst.

Example: NVDA on Computex announcement day.

---

## Current watchlist

```
RKLB, LUNR, ASTS, SPCE        # SpaceX-adjacent / space sector
LMT, NOC, RTX, BA              # Aerospace / defense
NVDA, AMD, TSLA, AAPL, META, GOOGL  # High-event tech
MRNA, BNTX, RXRX, ACAD        # Biotech (FDA events)
```

To scan different tickers: edit `DEFAULT_TICKERS` in `scanner.py`.

---

## Opportunity lifecycle

```
ACTIVE  →  EXITED (day before event)  →  ARCHIVED (7 days after event)
```

- **ACTIVE**: event upcoming, strategy in play
- **EXITED**: past exit date — should have closed position
- **ARCHIVED**: event is over + 7 days, kept for P&L history

Past events and estimated P&L are shown in the bottom table on the dashboard.

---

## P&L tracking

P&L is **estimated**, not actual. The scanner does not place trades.

| Strategy | How P&L is estimated |
|----------|---------------------|
| SHARES | Exact: (current price - entry price) / entry price |
| STRADDLE | Estimated: uses stock move % as proxy for IV expansion. Large moves → winning leg outpaces losing leg |
| LONG CALL | Estimated: ~3x leverage on stock move (rough delta approximation) |
| DAY TRADE | Not tracked — depends on intraday execution |

All estimated P&L is marked `(ESTIMATED)` on the dashboard.

---

## File structure

```
event-scanner/
  scanner.py          — core scan logic: fetches earnings dates, IV, historical reactions, scores setups
  update.py           — daily runner: refreshes prices, adds new opps, archives expired, generates index.html
  opportunities.json  — persistent store of all opportunities (committed to repo, updated daily by Actions)
  index.html          — generated static dashboard (served by GitHub Pages)
  requirements.txt    — Python dependencies
  .github/
    workflows/
      daily_scan.yml  — GitHub Actions: runs update.py daily at 6 AM PST, commits results
```

---

## Schedule

| What | When | How |
|------|------|-----|
| Daily scan + price refresh | 6:00 AM PST every day | GitHub Actions cron `0 14 * * *` (UTC) |
| Dashboard update | Immediately after scan (~1 min) | Actions commits index.html to repo → Pages deploys |
| Manual trigger | Any time | GitHub → Actions → Daily Event Scan → Run workflow |

---

## How to add new tickers

Edit `DEFAULT_TICKERS` in `scanner.py`, commit, and push. The next morning scan will include them.

```python
DEFAULT_TICKERS = [
    "RKLB", "LUNR", ...
    "NEW_TICKER",  # add here
]
```

---

## How to run locally

```bash
cd event-scanner
pip install -r requirements.txt

# Run full update (refreshes prices, scans, generates HTML)
python update.py

# Run scanner only (prints table, no file writes)
python scanner.py
python scanner.py AAPL NVDA RKLB   # custom tickers
```

---

## Known limitations

- **Data source**: yfinance (Yahoo Finance). Occasionally returns stale or missing data — if a ticker shows no event, it may just be a data gap, not a real absence.
- **Earnings dates**: unconfirmed dates are estimates based on historical patterns. Always verify on the company's IR page before trading.
- **P&L is estimated**: the scanner does not know your actual entry/exit prices or option premiums paid.
- **Options pricing**: straddle cost estimates use rough IV approximations, not actual bid/ask from a broker.
- **No intraday data**: prices update once daily at 6 AM, not real-time.
- **SpaceX-specific events**: SpaceX is private — no direct stock. The scanner tracks correlated public names (RKLB, LUNR, ASTS, SPCE) that historically move on SpaceX milestones.

---

## What we learned building this

- **Exit before earnings** — always. The pre-event run-up is the trade, not the reaction.
- **IV crush is real** — even correct directional bets lose money if you hold options through the report.
- **Straddles work best when IV is cheap** — if IV is already elevated, you're buying expensive insurance.
- **Win rate alone is not enough** — NVDA has an 80% drop rate after earnings despite being a great company. Direction bias matters more than company quality.
- **SPCE is a momentum play only** — IV too high, fundamentals irrelevant, follow the momentum and get out before earnings.
