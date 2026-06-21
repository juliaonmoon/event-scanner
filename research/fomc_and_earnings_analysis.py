"""
One-off research script (not part of the daily dashboard pipeline):
1. Does SPY/QQQ tend to drop in the days leading into an FOMC decision day?
2. Do the "Magnificent 7" tend to run up into earnings and then drop after?

Run: python research/fomc_and_earnings_analysis.py
"""
import sys
import os
import warnings
from datetime import date

import pandas as pd
import yfinance as yf
from curl_cffi import requests as cffi_requests

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SESSION = cffi_requests.Session(impersonate="chrome")
TODAY = date.today()

# FOMC decision days (2nd day of each 2-day meeting), 2023 through the most
# recent completed 2026 meeting. Sourced from federalreserve.gov.
FOMC_DECISION_DAYS = [
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-10",
    # 2026 (only completed ones)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
]

MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


def fetch_history(ticker, start="2022-06-01"):
    t = yf.Ticker(ticker, session=SESSION)
    hist = t.history(start=start, interval="1d")
    hist.index = hist.index.tz_localize(None)
    return hist


def nearest_idx(hist, target_date):
    idx = hist.index.get_indexer([pd.Timestamp(target_date)], method="nearest")[0]
    return idx


def pct_change(hist, i_from, i_to):
    if i_from < 0 or i_to >= len(hist) or i_from >= len(hist):
        return None
    p0 = hist.iloc[i_from]["Close"]
    p1 = hist.iloc[i_to]["Close"]
    return (p1 - p0) / p0 * 100


def analyze_fomc(ticker):
    hist = fetch_history(ticker)
    rows = []
    for d in FOMC_DECISION_DAYS:
        d_date = pd.Timestamp(d)
        if d_date > hist.index[-1] or d_date < hist.index[0]:
            continue
        i_decision = nearest_idx(hist, d_date)
        pre_5to1 = pct_change(hist, i_decision - 5, i_decision - 1)
        decision_day = pct_change(hist, i_decision - 1, i_decision)
        post_1day = pct_change(hist, i_decision, i_decision + 1)
        if pre_5to1 is None:
            continue
        rows.append({
            "date": d, "pre_5to1_pct": pre_5to1,
            "decision_day_pct": decision_day, "post_1day_pct": post_1day,
        })
    return pd.DataFrame(rows)


def analyze_earnings(ticker, n_quarters=8):
    hist = fetch_history(ticker)
    t = yf.Ticker(ticker, session=SESSION)
    try:
        earn = t.earnings_dates
    except Exception:
        earn = None
    if earn is None or earn.empty:
        return pd.DataFrame()
    earn.index = earn.index.tz_localize(None)
    past_dates = sorted([d for d in earn.index if d.date() < TODAY], reverse=True)[:n_quarters]

    rows = []
    for d in past_dates:
        if d > hist.index[-1] or d < hist.index[0]:
            continue
        i_e = nearest_idx(hist, d)
        runup_5to1 = pct_change(hist, i_e - 5, i_e - 1)
        reaction_1to1 = pct_change(hist, i_e - 1, i_e + 1)
        if runup_5to1 is None or reaction_1to1 is None:
            continue
        rows.append({
            "date": d.date().isoformat(),
            "runup_5to1_pct": runup_5to1,
            "reaction_pct": reaction_1to1,
        })
    return pd.DataFrame(rows)


def summarize(df, cols):
    if df.empty:
        return {c: None for c in cols}
    return {c: (round(df[c].mean(), 2), round((df[c] < 0).mean() * 100)) for c in cols}


def main():
    print("=" * 70)
    print("FOMC ANALYSIS — SPY & QQQ, pre-meeting drift")
    print(f"({len(FOMC_DECISION_DAYS)} FOMC decision days, 2023-2026)")
    print("=" * 70)
    for ticker in ["SPY", "QQQ"]:
        df = analyze_fomc(ticker)
        s = summarize(df, ["pre_5to1_pct", "decision_day_pct", "post_1day_pct"])
        print(f"\n{ticker} (n={len(df)} meetings):")
        print(f"  5d-before -> day-before decision: avg {s['pre_5to1_pct'][0]:+.2f}%  "
              f"(negative {s['pre_5to1_pct'][1]}% of the time)")
        print(f"  decision day itself:               avg {s['decision_day_pct'][0]:+.2f}%  "
              f"(negative {s['decision_day_pct'][1]}% of the time)")
        print(f"  day after decision:                avg {s['post_1day_pct'][0]:+.2f}%  "
              f"(negative {s['post_1day_pct'][1]}% of the time)")

    print("\n" + "=" * 70)
    print("MAGNIFICENT 7 — pre-earnings run-up vs post-earnings reaction")
    print("=" * 70)
    all_runup, all_reaction = [], []
    for ticker in MAG7:
        df = analyze_earnings(ticker)
        if df.empty:
            print(f"\n{ticker}: no data")
            continue
        s = summarize(df, ["runup_5to1_pct", "reaction_pct"])
        all_runup.append(s["runup_5to1_pct"][0])
        all_reaction.append(s["reaction_pct"][0])
        both_up_then_drop = ((df["runup_5to1_pct"] > 0) & (df["reaction_pct"] < 0)).mean() * 100
        print(f"\n{ticker} (n={len(df)} quarters):")
        print(f"  5d run-up into earnings: avg {s['runup_5to1_pct'][0]:+.2f}%  "
              f"(up {100 - s['runup_5to1_pct'][1]}% of quarters)")
        print(f"  reaction (close before -> close after): avg {s['reaction_pct'][0]:+.2f}%  "
              f"(down {s['reaction_pct'][1]}% of quarters)")
        print(f"  ran up into earnings AND dropped after: {both_up_then_drop:.0f}% of quarters")

    if all_runup:
        print(f"\nMag7 average across tickers: run-up {sum(all_runup)/len(all_runup):+.2f}%, "
              f"reaction {sum(all_reaction)/len(all_reaction):+.2f}%")


if __name__ == "__main__":
    main()
