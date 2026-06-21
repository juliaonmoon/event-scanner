"""
Daily update script — runs in GitHub Actions.
1. Loads existing opportunities.json
2. Refreshes prices + P&L
3. Scans for new events, adds if not already tracked
4. Archives events 7 days after they pass
5. Generates static index.html
"""
import json, os, sys, time
from datetime import date, timedelta, datetime
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scanner import scan, DEFAULT_TICKERS, get_current_price, pick_expiry, get_option_quote
import calendar_events

OPPS_FILE = os.path.join(os.path.dirname(__file__), "opportunities.json")
HTML_FILE = os.path.join(os.path.dirname(__file__), "index.html")
TODAY     = date.today()


def load_opps():
    if not os.path.exists(OPPS_FILE):
        return []
    with open(OPPS_FILE) as f:
        return json.load(f)


def save_opps(opps):
    with open(OPPS_FILE, "w") as f:
        json.dump(opps, f, indent=2, default=str)


def calc_pnl(opp):
    entry   = opp.get("entry_stock_price")
    current = opp.get("current_stock_price")
    if not entry or not current:
        return None, None
    pct      = round((current - entry) / entry * 100, 2)
    strategy = opp.get("strategy", "")
    if "STRADDLE" in strategy:
        abs_pct = abs(pct)
        if abs_pct > 5:
            est = round(abs_pct * 1.5, 1)
            return est, f"stock {pct:+.1f}%, est straddle ~+{est}% (ESTIMATED)"
        elif abs_pct > 2:
            est = round(abs_pct * 0.8, 1)
            return est, f"stock {pct:+.1f}%, est straddle ~+{est}% (ESTIMATED)"
        else:
            return round(pct * 0.3, 1), f"stock near flat ({pct:+.1f}%), IV expansion may offset (ESTIMATED)"
    elif "LONG CALL" in strategy:
        est = round(pct * 3, 1) if pct > 0 else round(pct * 1.5, 1)
        return est, f"stock {pct:+.1f}%, est call ~{est:+.1f}% (ESTIMATED)"
    elif "DAY TRADE" in strategy:
        return None, "day trade - P&L depends on intraday execution"
    return pct, f"stock {pct:+.1f}% from entry"


def set_option_baseline(opp):
    """Pretend we bought the suggested option(s) today; record today's premium as cost basis."""
    strategy = opp.get("strategy", "")
    if "STRADDLE" not in strategy and "LONG CALL" not in strategy:
        return False
    ticker    = opp["ticker"]
    exit_date = date.fromisoformat(opp["exit_date"])
    expiry    = pick_expiry(ticker, exit_date)
    spot      = opp.get("current_stock_price")
    if not expiry or not spot:
        return False

    legs = ["CALL", "PUT"] if "STRADDLE" in strategy else ["CALL"]
    cost, strike = 0, None
    for kind in legs:
        premium, used_strike = get_option_quote(ticker, expiry, spot, kind)
        if premium is None:
            return False
        cost += premium
        strike = used_strike

    opp["option_expiry"]            = expiry
    opp["option_strike"]            = strike
    opp["option_legs"]              = legs
    opp["option_cost"]              = round(cost, 2)
    opp["option_current_value"]     = round(cost, 2)
    opp["option_entry_date"]        = TODAY.isoformat()
    opp["option_entry_stock_price"] = spot
    opp["pnl_pct"]  = 0.0
    opp["pnl_note"] = f"Bought {TODAY.isoformat()} @ ${round(cost,2)} premium ({'/'.join(legs)} ${strike}, exp {expiry}) (REAL)"
    return True


def update_option_pnl(opp):
    ticker, expiry, strike, legs = opp["ticker"], opp["option_expiry"], opp["option_strike"], opp["option_legs"]
    value = 0
    for kind in legs:
        premium, _ = get_option_quote(ticker, expiry, strike, kind)
        if premium is None:
            entry_date = opp.get("option_entry_date", "?")
            opp["pnl_note"] = f"Premium quote unavailable - cost ${opp['option_cost']} (entered {entry_date}, REAL)"
            return False
        value += premium
    cost = opp["option_cost"]
    pnl  = round((value - cost) / cost * 100, 1) if cost else None
    opp["option_current_value"] = round(value, 2)
    opp["pnl_pct"]  = pnl
    opp["pnl_note"] = f"Premium ${cost} -> ${round(value,2)} ({pnl:+.1f}%, REAL)" if pnl is not None else "premium unavailable"
    return True


def update_prices(opps):
    if TODAY.weekday() >= 5:  # 5=Saturday, 6=Sunday
        print("  Skipping price refresh - market closed on weekends.")
        return opps
    updated = 0
    for opp in opps:
        if opp["status"] != "ACTIVE":
            continue
        price = get_current_price(opp["ticker"])
        if price:
            opp["current_stock_price"] = price
            updated += 1
        else:
            print(f"  {opp['ticker']}: price fetch failed, keeping last known")

        strategy = opp.get("strategy", "")
        if "STRADDLE" in strategy or "LONG CALL" in strategy:
            if not opp.get("option_cost"):
                if set_option_baseline(opp):
                    print(f"  {opp['ticker']}: option cost basis set @ ${opp['option_cost']}")
                else:
                    print(f"  {opp['ticker']}: could not fetch option chain, leaving as estimate")
            elif update_option_pnl(opp):
                print(f"  {opp['ticker']}: option value ${opp['option_current_value']} | P&L: {opp['pnl_pct']}%")
        elif price:
            pnl, note = calc_pnl(opp)
            opp["pnl_pct"]  = pnl
            opp["pnl_note"] = note
            print(f"  {opp['ticker']}: ${price} | P&L: {pnl}%")
        time.sleep(0.3)
    active_count = sum(1 for o in opps if o["status"] == "ACTIVE")
    print(f"  {updated}/{active_count} prices updated.")
    return opps


def archive_expired(opps):
    cutoff = TODAY - timedelta(days=7)
    for opp in opps:
        if opp["status"] == "ACTIVE":
            exit_date = date.fromisoformat(opp["exit_date"])
            if TODAY >= exit_date:
                opp["status"] = "EXITED"
                print(f"  {opp['ticker']} -> EXITED")
        if opp["status"] == "EXITED":
            event_date = date.fromisoformat(opp["event_date"])
            if event_date <= cutoff:
                opp["status"] = "ARCHIVED"
                print(f"  {opp['ticker']} -> ARCHIVED")
    return opps


def add_new_opps(opps):
    existing_ids = {o["id"] for o in opps}
    print("Scanning for new events...")
    df = scan(DEFAULT_TICKERS)
    if df.empty:
        print("  No new events found.")
        return opps

    added = 0
    for _, row in df[df["play"] != "AVOID"].iterrows():
        ticker     = row["ticker"]
        event_date = row["event_date"]
        opp_id     = f"{ticker}_{row['event']}_{event_date}"
        if opp_id in existing_ids:
            continue

        win_rate  = row.get("win_rate") or 50
        exp_move  = row.get("exp_move_pct") or 0
        avg_move  = row.get("avg_move_pct") or 0
        iv_ratio  = (exp_move / avg_move) if avg_move else 1
        play      = row["play"]

        if play == "DAY":
            strategy, instruments = "DAY TRADE", "Shares or 1-week calls at open, sell same day"
        elif iv_ratio < 0.85 and (win_rate < 45 or win_rate > 55):
            strategy    = "STRADDLE"
            instruments = "ATM Call + Put expiring after event"
        elif win_rate >= 65:
            strategy    = "LONG CALL"
            instruments = "ATM Call expiring 3 weeks after event"
        else:
            strategy    = "STRADDLE"
            instruments = "ATM Call + Put expiring after event"

        price     = row.get("entry_stock_price") or 0
        exit_date = (date.fromisoformat(event_date) - timedelta(days=1)).isoformat()

        opps.append({
            "id": opp_id,
            "ticker": ticker,
            "event_type": row["event"],
            "event_date": event_date,
            "exit_date": exit_date,
            "added_date": TODAY.isoformat(),
            "score": int(row["score"]),
            "play": play,
            "strategy": strategy,
            "instruments": instruments,
            "entry_stock_price": price,
            "current_stock_price": price,
            "exp_move_pct": exp_move,
            "avg_move_pct": row.get("avg_move_pct"),
            "win_rate": win_rate,
            "avg_direction": row.get("avg_direction"),
            "momentum_5d": row.get("momentum_5d"),
            "notes": row.get("notes", ""),
            "status": "ACTIVE",
            "pnl_pct": None,
            "pnl_note": None,
        })
        existing_ids.add(opp_id)
        print(f"  + {ticker} {play} (score={row['score']}, event={event_date})")
        added += 1
        time.sleep(0.3)

    print(f"  {added} new opportunities added.")
    return opps


def generate_html(opps):
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M PST")
    data_json = json.dumps(opps, default=str)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Event Scanner</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px}}
    header{{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;align-items:center;justify-content:space-between}}
    header h1{{font-size:18px;font-weight:600;color:#58a6ff}}
    .meta{{font-size:12px;color:#8b949e}}
    .meta span{{color:#3fb950}}
    .nav-link{{font-size:12px;color:#58a6ff;text-decoration:none;border:1px solid #30363d;border-radius:6px;padding:6px 12px}}
    .nav-link:hover{{background:#21262d}}
    .container{{padding:20px 24px;max-width:1400px;margin:0 auto}}
    .section-title{{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#8b949e;margin:24px 0 12px;padding-bottom:8px;border-bottom:1px solid #21262d}}
    .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
    .card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;position:relative;overflow:hidden}}
    .card::before{{content:'';position:absolute;top:0;left:0;width:3px;height:100%}}
    .card.swing::before{{background:#58a6ff}}
    .card.day::before{{background:#f0883e}}
    .card-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}}
    .ticker{{font-size:20px;font-weight:700}}
    .score-badge{{padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}}
    .score-high{{background:#1a3a2a;color:#3fb950;border:1px solid #2ea043}}
    .score-mid{{background:#2d2a1a;color:#d29922;border:1px solid #9e6a03}}
    .score-low{{background:#21262d;color:#8b949e;border:1px solid #30363d}}
    .play-tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;letter-spacing:.05em;margin-bottom:10px}}
    .play-swing{{background:#0d2041;color:#58a6ff}}
    .play-day{{background:#2d1f0a;color:#f0883e}}
    .event-info{{font-size:12px;color:#8b949e;margin-bottom:10px}}
    .event-info strong{{color:#c9d1d9}}
    .countdown{{font-size:12px;font-weight:600;color:#d29922}}
    .countdown.soon{{color:#f85149}}
    .strategy-box{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:10px;margin:10px 0}}
    .strategy-box .lbl{{font-size:11px;color:#8b949e;margin-bottom:3px}}
    .strategy-box .val{{font-size:13px;color:#58a6ff;font-weight:600}}
    .strategy-box .inst{{font-size:12px;color:#c9d1d9;margin-top:4px}}
    .metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}}
    .metric{{text-align:center}}
    .metric .v{{font-size:14px;font-weight:600}}
    .metric .l{{font-size:10px;color:#8b949e;margin-top:2px}}
    .green{{color:#3fb950}} .yellow{{color:#d29922}} .red{{color:#f85149}}
    .pnl-box{{margin-top:10px;padding:8px;border-radius:6px;font-size:12px}}
    .pnl-pos{{background:#1a3a2a;color:#3fb950;border:1px solid #2ea043}}
    .pnl-neg{{background:#3a1a1a;color:#f85149;border:1px solid #da3633}}
    .pnl-neu{{background:#21262d;color:#8b949e;border:1px solid #30363d}}
    .notes{{font-size:11px;color:#8b949e;margin-top:8px}}
    .exit-info{{font-size:11px;color:#8b949e;margin-top:8px;padding-top:8px;border-top:1px solid #21262d}}
    .exit-info strong{{color:#f0883e}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{text-align:left;padding:8px 12px;color:#8b949e;font-weight:500;font-size:12px;border-bottom:1px solid #21262d}}
    td{{padding:10px 12px;border-bottom:1px solid #161b22;vertical-align:middle}}
    tr:hover td{{background:#161b22}}
    .st-badge{{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}}
    .st-exited{{background:#21262d;color:#8b949e}}
    .st-archived{{background:#1a1a1a;color:#484f58}}
    .pnl-p{{color:#3fb950;font-weight:600}} .pnl-n{{color:#f85149;font-weight:600}} .pnl-e{{color:#d29922}}
    .empty{{text-align:center;padding:40px;color:#484f58}}
    .portfolio{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}}
    .portfolio .stat{{text-align:center}}
    .portfolio .stat .v{{font-size:22px;font-weight:700}}
    .portfolio .stat .l{{font-size:11px;color:#8b949e;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
    .portfolio-note{{font-size:11px;color:#8b949e;margin-top:10px}}
  </style>
</head>
<body>
<header>
  <div>
    <h1>Event Scanner</h1>
    <div class="meta">Updated: <span>{now_str}</span> &nbsp;|&nbsp; Refreshes daily at 6:00 AM PST</div>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <div class="meta" id="counts"></div>
    <a class="nav-link" href="calendar.html">Market Events Calendar &rarr;</a>
  </div>
</header>
<div class="container">
  <div class="section-title">Portfolio Performance</div>
  <div class="portfolio" id="portfolio-summary"></div>
  <div class="section-title">Active Opportunities</div>
  <div class="cards" id="active-cards"><div class="empty">Loading...</div></div>
  <div class="section-title" style="margin-top:32px">Past Events &amp; P&amp;L</div>
  <table><thead><tr>
    <th>Ticker</th><th>Event</th><th>Event Date</th><th>Strategy</th>
    <th>Entry Price</th><th>Score</th><th>P&amp;L</th><th>Note</th><th>Status</th>
  </tr></thead><tbody id="past-rows"></tbody></table>
</div>
<script>
const DATA = {data_json};

function sc(s){{return s>=40?'score-high':s>=25?'score-mid':'score-low'}}
function pnlCls(p){{return p===null||p===undefined?'pnl-neu':p>=0?'pnl-pos':'pnl-neg'}}
function mColor(v,isWR){{
  if(isWR){{return v>=65?'green':v>=50?'yellow':'red'}}
  if(v===null||v===undefined)return'';return v>=0?'green':'red'
}}

function card(o){{
  const cls   = o.play==='DAY'?'day':'swing';
  const ptag  = o.play==='DAY'?'play-day':'play-swing';
  const days  = Math.ceil((new Date(o.event_date)-new Date())/86400000);
  const edays = Math.ceil((new Date(o.exit_date)-new Date())/86400000);
  const chg   = o.current_stock_price&&o.entry_stock_price
    ? ((o.current_stock_price-o.entry_stock_price)/o.entry_stock_price*100).toFixed(1) : null;
  const pnlH  = o.pnl_pct!==null&&o.pnl_pct!==undefined
    ? `<div class="pnl-box ${{pnlCls(o.pnl_pct)}}"><strong>P&L: ${{o.pnl_pct>=0?'+':''}}${{o.pnl_pct}}%</strong>${{o.pnl_note?`<br><span style="font-size:11px">${{o.pnl_note}}</span>`:''}}
</div>` : '';
  return `<div class="card ${{cls}}">
    <div class="card-header">
      <div><div class="ticker">${{o.ticker}}</div><span class="play-tag ${{ptag}}">${{o.play}}</span></div>
      <span class="score-badge ${{sc(o.score)}}">Score ${{o.score}}</span>
    </div>
    <div class="event-info"><strong>${{o.event_type}}</strong> &mdash; ${{o.event_date}}
      &nbsp;<span class="countdown${{days<=7?' soon':''}}">${{days}}d away</span></div>
    <div class="strategy-box">
      <div class="lbl">Strategy</div><div class="val">${{o.strategy}}</div>
      <div class="inst">${{o.instruments}}</div>
    </div>
    <div class="metrics">
      <div class="metric"><div class="v ${{mColor(o.win_rate,true)}}">${{o.win_rate??'--'}}%</div><div class="l">Win Rate</div></div>
      <div class="metric"><div class="v">${{o.avg_move_pct??'--'}}%</div><div class="l">Hist Move</div></div>
      <div class="metric"><div class="v ${{mColor(o.avg_direction,false)}}">${{o.avg_direction!==null?(o.avg_direction>=0?'+':'')+o.avg_direction+'%':'--'}}</div><div class="l">Avg Dir</div></div>
    </div>
    <div class="metrics">
      <div class="metric"><div class="v">${{o.exp_move_pct??'--'}}%</div><div class="l">IV Move</div></div>
      <div class="metric"><div class="v">$${{o.current_stock_price??'--'}}</div><div class="l">Price</div></div>
      <div class="metric"><div class="v ${{mColor(chg,false)}}">${{chg!==null?(chg>=0?'+':'')+chg+'%':'--'}}</div><div class="l">vs Entry</div></div>
    </div>
    ${{pnlH}}
    ${{o.notes?`<div class="notes">${{o.notes}}</div>`:''}}
    <div class="exit-info">Exit by: <strong>${{o.exit_date}}</strong> (${{edays}}d) &mdash; Added ${{o.added_date}}</div>
  </div>`;
}}

function pastRow(o){{
  const p = o.pnl_pct;
  const pt = p!==null&&p!==undefined?`${{p>=0?'+':''}}${{p}}%`:'--';
  const pc = p!==null&&p!==undefined?(p>=0?'pnl-p':'pnl-n')+(o.pnl_note&&o.pnl_note.includes('ESTIMATED')?' pnl-e':''):'';
  return `<tr>
    <td><strong>${{o.ticker}}</strong></td><td>${{o.event_type}}</td><td>${{o.event_date}}</td>
    <td>${{o.strategy}}</td><td>$${{o.entry_stock_price??'--'}}</td><td>${{o.score}}</td>
    <td class="${{pc}}">${{pt}}${{o.pnl_note&&o.pnl_note.includes('ESTIMATED')?' *':''}}</td>
    <td style="color:#8b949e;font-size:11px;max-width:200px">${{o.pnl_note??''}}</td>
    <td><span class="st-badge st-${{o.status.toLowerCase()}}">${{o.status}}</span></td>
  </tr>`;
}}

const STAKE = 1000; // hypothetical $ invested per opportunity, for tracking purposes

function renderPortfolio(){{
  const tracked = DATA.filter(o=>o.pnl_pct!==null&&o.pnl_pct!==undefined);
  const closed  = tracked.filter(o=>o.status!=='ACTIVE');
  const openT   = tracked.filter(o=>o.status==='ACTIVE');

  const sumPnl = arr => arr.reduce((s,o)=>s+STAKE*o.pnl_pct/100,0);
  const totalInvested = tracked.length*STAKE;
  const totalPnlDollar = sumPnl(tracked);
  const totalRoi = totalInvested ? (totalPnlDollar/totalInvested*100) : 0;
  const closedRoi = closed.length ? (sumPnl(closed)/(closed.length*STAKE)*100) : 0;
  const wins = closed.filter(o=>o.pnl_pct>0).length;
  const winRate = closed.length ? (wins/closed.length*100) : null;

  const fmtUsd = v => `${{v>=0?'+':'-'}}$${{Math.abs(v).toFixed(2)}}`;
  const fmtPct = v => `${{v>=0?'+':''}}${{v.toFixed(1)}}%`;
  const cls = v => v>=0?'green':'red';

  document.getElementById('portfolio-summary').innerHTML = `
    <div class="stat"><div class="v">${{tracked.length}}</div><div class="l">Trades Tracked</div></div>
    <div class="stat"><div class="v">$${{totalInvested.toLocaleString()}}</div><div class="l">Hypothetical Invested ($${{STAKE}}/trade)</div></div>
    <div class="stat"><div class="v ${{cls(totalPnlDollar)}}">${{fmtUsd(totalPnlDollar)}}</div><div class="l">Total P&amp;L</div></div>
    <div class="stat"><div class="v ${{cls(totalRoi)}}">${{fmtPct(totalRoi)}}</div><div class="l">Overall ROI</div></div>
    <div class="stat"><div class="v ${{cls(closedRoi)}}">${{closed.length?fmtPct(closedRoi):'--'}}</div><div class="l">Closed-Trade ROI (${{closed.length}})</div></div>
    <div class="stat"><div class="v">${{winRate!==null?winRate.toFixed(0)+'%':'--'}}</div><div class="l">Win Rate (Closed)</div></div>
  ` + `<div class="portfolio-note" style="grid-column:1/-1">Assumes a flat $${{STAKE}} stake per opportunity. STRADDLE/LONG CALL positions are tracked against real option premiums (entry cost recorded the day the trade was added, marked to live bid/ask daily); SHARES/DAY TRADE positions track the underlying stock price. ${{openT.length}} positions still open.</div>`;
}}
renderPortfolio();

const active = DATA.filter(o=>o.status==='ACTIVE').sort((a,b)=>b.score-a.score);
const past   = DATA.filter(o=>o.status!=='ACTIVE').sort((a,b)=>new Date(b.event_date)-new Date(a.event_date));

document.getElementById('active-cards').innerHTML =
  active.length ? active.map(card).join('') : '<div class="empty">No active opportunities.</div>';
document.getElementById('past-rows').innerHTML =
  past.length ? past.map(pastRow).join('') :
  '<tr><td colspan="9" style="text-align:center;color:#484f58;padding:20px">No past events yet.</td></tr>';
document.getElementById('counts').textContent =
  `${{active.length}} active / ${{past.length}} past`;
</script>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  index.html generated ({len(opps)} opportunities)")


def main():
    print(f"=== Daily update {TODAY} ===")
    opps = load_opps()
    print(f"Loaded {len(opps)} existing opportunities")
    opps = update_prices(opps)
    opps = archive_expired(opps)
    opps = add_new_opps(opps)
    save_opps(opps)
    generate_html(opps)
    print("Refreshing market events calendar...")
    calendar_events.main()
    active = sum(1 for o in opps if o["status"] == "ACTIVE")
    print(f"Done. {active} active, {len(opps)} total.")


if __name__ == "__main__":
    main()
