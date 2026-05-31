"""
Event scanner — finds stocks with upcoming catalysts and scores trade setups.
Designed to run in GitHub Actions (Linux) or locally.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import time
import warnings
warnings.filterwarnings("ignore")

TWELVEDATA_KEY = "7fd7d28f2b1947e7bb8e9f34406aba0c"

DEFAULT_TICKERS = [
    # SpaceX adjacent
    "RKLB", "LUNR", "ASTS", "SPCE",
    # Aerospace / defense
    "LMT", "NOC", "RTX", "BA",
    # High-event tech
    "NVDA", "AMD", "TSLA", "AAPL", "META", "GOOGL",
    # Biotech
    "MRNA", "BNTX", "RXRX", "ACAD",
]

TODAY = date.today()
LOOKAHEAD_DAYS = 90


def get_earnings_date(ticker):
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if not cal:
            return None, None
        earn = cal.get("Earnings Date")
        if not earn:
            return None, None
        dates = earn if isinstance(earn, list) else [earn]
        for d in dates:
            dt = pd.Timestamp(d).date()
            days = (dt - TODAY).days
            if 0 <= days <= LOOKAHEAD_DAYS:
                return str(dt), days
    except Exception:
        pass
    return None, None


def get_options_expected_move(ticker):
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return None
        target = None
        for exp in exps:
            d = datetime.strptime(exp, "%Y-%m-%d").date()
            if (d - TODAY).days >= 3:
                target = exp
                break
        if not target:
            return None
        chain = t.option_chain(target)
        spot = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
        if not spot:
            return None
        calls = chain.calls.set_index("strike")
        puts = chain.puts.set_index("strike")
        atm = min(calls.index, key=lambda x: abs(x - spot))
        c_price = calls.loc[atm, "lastPrice"] if atm in calls.index else 0
        p_price = puts.loc[atm, "lastPrice"] if atm in puts.index else 0
        return round(((c_price + p_price) / spot) * 100, 1)
    except Exception:
        return None


def get_historical_reactions(ticker, n_events=6):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2y", interval="1d")
        if hist.empty:
            return {}
        earnings_hist = t.earnings_dates
        if earnings_hist is None or earnings_hist.empty:
            return {}
        reactions = []
        for dt in earnings_hist.index[:n_events]:
            d = pd.Timestamp(dt).normalize()
            try:
                idx = hist.index.get_indexer([d], method="nearest")[0]
                if idx + 1 >= len(hist):
                    continue
                d0 = hist.iloc[idx]["Close"]
                d1 = hist.iloc[idx + 1]["Close"]
                reactions.append((d1 - d0) / d0 * 100)
            except Exception:
                continue
        if not reactions:
            return {}
        avg_move = round(sum(abs(r) for r in reactions) / len(reactions), 1)
        up_count = sum(1 for r in reactions if r > 0)
        return {
            "avg_move_pct": avg_move,
            "win_rate": round(up_count / len(reactions) * 100),
            "avg_direction": round(sum(reactions) / len(reactions), 1),
            "n": len(reactions),
        }
    except Exception:
        return {}


def get_recent_momentum(ticker, days=5):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="10d", interval="1d")
        if len(hist) < 2:
            return None
        old = hist.iloc[-min(days, len(hist))]["Close"]
        new = hist.iloc[-1]["Close"]
        return round((new - old) / old * 100, 1)
    except Exception:
        return None


def get_current_price(ticker):
    try:
        t = yf.Ticker(ticker)
        p = t.fast_info.get("lastPrice") or t.fast_info.get("regularMarketPrice")
        return round(float(p), 2) if p else None
    except Exception:
        return None


def score_and_suggest(row):
    score = 0
    notes = []
    avg_move = row.get("avg_move_pct") or 0
    exp_move = row.get("exp_move_pct") or 0
    win_rate = row.get("win_rate") or 50
    avg_dir  = row.get("avg_direction") or 0
    momentum = row.get("momentum_5d") or 0
    days_until = row.get("days_until")

    if avg_move >= 10:
        score += 25; notes.append(f"big avg move {avg_move}%")
    elif avg_move >= 5:
        score += 15; notes.append(f"moderate avg move {avg_move}%")
    elif avg_move >= 3:
        score += 8

    if win_rate >= 70:
        score += 20; notes.append(f"bullish bias {win_rate}% wins")
    elif win_rate <= 30:
        score += 15; notes.append(f"bearish bias {100-win_rate}% drops")
    elif 45 <= win_rate <= 55:
        score -= 5; notes.append("no clear bias")

    if exp_move and avg_move:
        iv_ratio = exp_move / avg_move
        if iv_ratio < 0.8:
            score += 15; notes.append("IV underpricing history")
        elif iv_ratio > 1.5:
            score -= 10; notes.append("IV already pricing in move")

    if avg_dir > 2 and momentum > 0:
        score += 10; notes.append("momentum confirms bullish bias")
    elif avg_dir < -2 and momentum < 0:
        score += 10; notes.append("momentum confirms bearish bias")

    if days_until is not None and days_until <= 1:
        play = "DAY"
    elif score < 20:
        play = "AVOID"
    elif days_until is not None and days_until <= 7 and score >= 30:
        play = "SWING"
    else:
        play = "SWING" if score >= 25 else "AVOID"

    return score, play, "; ".join(notes[:3])


def scan(tickers=None):
    tickers = tickers or DEFAULT_TICKERS
    rows = []
    for ticker in tickers:
        try:
            earn_date, days_until = get_earnings_date(ticker)
            if not earn_date:
                continue
            exp_move  = get_options_expected_move(ticker)
            hist      = get_historical_reactions(ticker)
            momentum  = get_recent_momentum(ticker)
            price     = get_current_price(ticker)
            row = {
                "ticker": ticker,
                "event": "EARNINGS",
                "event_date": earn_date,
                "days_until": days_until,
                "exp_move_pct": exp_move,
                "avg_move_pct": hist.get("avg_move_pct"),
                "win_rate": hist.get("win_rate"),
                "avg_direction": hist.get("avg_direction"),
                "momentum_5d": momentum,
                "entry_stock_price": price,
            }
            score, play, notes = score_and_suggest(row)
            row.update({"score": score, "play": play, "notes": notes})
            rows.append(row)
        except Exception as e:
            print(f"  {ticker} error: {e}")
        time.sleep(0.3)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("score", ascending=False)
