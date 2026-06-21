"""
Market events calendar — macro releases, notable earnings, and IPOs for the
next few months. Links from/to the main event-scanner dashboard.
"""
import json
import re
from datetime import date, timedelta

import requests

from scanner import DEFAULT_TICKERS, get_earnings_date

# --- Macro calendar ---------------------------------------------------------
# Hardcoded from official sources (Federal Reserve FOMC schedule, BLS/OMB
# "Schedule of Release Dates for Principal Federal Economic Indicators").
# These are published a year ahead and don't change, except for rare
# emergency FOMC meetings. Re-derive from federalreserve.gov/monetarypolicy
# and bls.gov/schedule when adding 2027 dates.

FOMC_DATES_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

JOBS_REPORT_DATES_2026 = [
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
    "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
    "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
]

CPI_DATES_2026 = [
    "2026-01-13", "2026-02-11", "2026-03-11", "2026-04-10",
    "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10",
]

PPI_DATES_2026 = [
    "2026-01-14", "2026-02-12", "2026-03-12", "2026-04-14",
    "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-13",
    "2026-09-10", "2026-10-15", "2026-11-13", "2026-12-15",
]

GDP_ADVANCE_DATES_2026 = [
    ("2026-01-29", "4Q'25"), ("2026-04-30", "1Q'26"),
    ("2026-07-30", "2Q'26"), ("2026-10-29", "3Q'26"),
]


def get_macro_events():
    events = []
    for d in FOMC_DATES_2026:
        events.append({"date": d, "type": "FOMC", "label": "FOMC Rate Decision"})
    for d in JOBS_REPORT_DATES_2026:
        events.append({"date": d, "type": "JOBS", "label": "Jobs Report (NFP)"})
    for d in CPI_DATES_2026:
        events.append({"date": d, "type": "CPI", "label": "CPI Release"})
    for d in PPI_DATES_2026:
        events.append({"date": d, "type": "PPI", "label": "PPI Release"})
    for d, q in GDP_ADVANCE_DATES_2026:
        events.append({"date": d, "type": "GDP", "label": f"GDP Advance Estimate ({q})"})
    return events


# --- Notable earnings --------------------------------------------------------
# Mega-cap / high-liquidity names beyond the scanner's niche watchlist, so the
# calendar surfaces earnings traders are likely to care about even if the
# scanner itself isn't tracking that ticker as a catalyst trade.
MEGA_CAP_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX",
    "AVGO", "ORCL", "CRM",
]
FINANCIALS_TICKERS = ["JPM", "BAC", "GS", "MS", "WFC", "V", "MA"]
INDUSTRIAL_ENERGY_TICKERS = ["XOM", "CVX", "BA", "CAT", "GE"]
RETAIL_CONSUMER_TICKERS = ["WMT", "COST", "HD", "DIS", "SBUX"]

NOTABLE_EARNINGS_TICKERS = sorted(set(
    DEFAULT_TICKERS + MEGA_CAP_TICKERS + FINANCIALS_TICKERS
    + INDUSTRIAL_ENERGY_TICKERS + RETAIL_CONSUMER_TICKERS
))


def get_earnings_events(tickers=None):
    tickers = tickers or NOTABLE_EARNINGS_TICKERS
    events = []
    for ticker in tickers:
        earn_date, _ = get_earnings_date(ticker)
        if earn_date:
            events.append({"date": earn_date, "type": "EARNINGS", "label": f"{ticker} Earnings", "ticker": ticker})
    return events


# --- IPOs --------------------------------------------------------------------
# Best-effort scrape of stockanalysis.com's public IPO calendar. IPO dates are
# rarely confirmed more than 1-2 weeks out, so don't expect this to populate
# more than the near term even though the calendar view spans months. If the
# page's markup changes this returns [] rather than raising.
IPO_CALENDAR_URL = "https://stockanalysis.com/ipos/calendar/"


def get_ipo_events():
    try:
        resp = requests.get(IPO_CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        table_match = re.search(r'<table id="main-table".*?</table>', resp.text, re.S)
        if not table_match:
            return []
        rows = re.findall(r'<tr class="svelte-[\w-]+">(.*?)</tr>', table_match.group(0), re.S)
        events = []
        for row in rows:
            date_m = re.search(r'<td class="svelte-[\w-]+">([^<]+)</td>', row)
            sym_m = re.search(r'href="/stocks/[a-zA-Z.-]+/">([A-Z.]+)</a>', row)
            name_m = re.search(r'<td class="slw svelte-[\w-]+">([^<]+)</td>', row)
            if not (date_m and sym_m and name_m):
                continue
            try:
                d = date.fromisoformat(_parse_us_date(date_m.group(1)))
            except ValueError:
                continue
            events.append({
                "date": d.isoformat(),
                "type": "IPO",
                "label": f"{sym_m.group(1)} IPO — {name_m.group(1).strip()}",
                "ticker": sym_m.group(1),
            })
        return events
    except Exception:
        return []


def _parse_us_date(s):
    from datetime import datetime
    return datetime.strptime(s.strip(), "%b %d, %Y").date().isoformat()


# --- Combine + render ---------------------------------------------------------
LOOKAHEAD_DAYS = 90


def build_events():
    today = date.today()
    cutoff = today + timedelta(days=LOOKAHEAD_DAYS)
    events = get_macro_events() + get_earnings_events() + get_ipo_events()
    events = [e for e in events if today.isoformat() <= e["date"] <= cutoff.isoformat()]
    events.sort(key=lambda e: e["date"])
    return events


TYPE_META = {
    "FOMC":     {"color": "#f85149", "name": "Fed / FOMC"},
    "JOBS":     {"color": "#f0883e", "name": "Jobs Report"},
    "CPI":      {"color": "#d29922", "name": "CPI"},
    "PPI":      {"color": "#9e6a03", "name": "PPI"},
    "GDP":      {"color": "#bc8cff", "name": "GDP"},
    "EARNINGS": {"color": "#58a6ff", "name": "Earnings"},
    "IPO":      {"color": "#3fb950", "name": "IPO"},
}


def generate_calendar_html(events, out_path):
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M PST")
    data_json = json.dumps(events)
    legend_html = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{m["color"]}"></span>{m["name"]}</div>'
        for m in TYPE_META.values()
    )
    type_meta_json = json.dumps(TYPE_META)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Market Events Calendar</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px}}
    header{{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
    header h1{{font-size:18px;font-weight:600;color:#58a6ff}}
    .meta{{font-size:12px;color:#8b949e}}
    .meta span{{color:#3fb950}}
    .nav-link{{font-size:12px;color:#58a6ff;text-decoration:none;border:1px solid #30363d;border-radius:6px;padding:6px 12px}}
    .nav-link:hover{{background:#21262d}}
    .container{{padding:20px 24px;max-width:1200px;margin:0 auto}}
    .legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;font-size:12px;color:#8b949e}}
    .legend-item{{display:flex;align-items:center;gap:6px}}
    .dot{{width:9px;height:9px;border-radius:50%;display:inline-block}}
    .month-nav{{display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:16px}}
    .month-nav button{{background:#161b22;border:1px solid #30363d;color:#e6edf3;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:14px}}
    .month-nav button:hover{{background:#21262d}}
    .month-nav h2{{font-size:16px;font-weight:600;min-width:180px;text-align:center}}
    .grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:#21262d;border:1px solid #21262d;border-radius:8px;overflow:hidden}}
    .dow{{background:#161b22;text-align:center;font-size:11px;color:#8b949e;padding:8px 0;text-transform:uppercase;letter-spacing:.05em}}
    .day{{background:#0d1117;min-height:100px;padding:6px;position:relative}}
    .day.other-month{{background:#080a0e;color:#30363d}}
    .day.today{{background:#0d2041}}
    .day-num{{font-size:12px;color:#8b949e;margin-bottom:4px}}
    .day.today .day-num{{color:#58a6ff;font-weight:700}}
    .chip{{display:block;font-size:10px;border-radius:3px;padding:2px 4px;margin-bottom:2px;color:#0d1117;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:default}}
    .more{{font-size:10px;color:#8b949e;margin-top:2px}}
  </style>
</head>
<body>
<header>
  <div>
    <h1>Market Events Calendar</h1>
    <div class="meta">Updated: <span>{now_str}</span> &nbsp;|&nbsp; Fed days, CPI/jobs releases, notable earnings, IPOs</div>
  </div>
  <a class="nav-link" href="index.html">&larr; Event Scanner Dashboard</a>
</header>
<div class="container">
  <div class="legend">{legend_html}</div>
  <div class="month-nav">
    <button id="prev-month">&larr;</button>
    <h2 id="month-label"></h2>
    <button id="next-month">&rarr;</button>
  </div>
  <div class="grid" id="cal-grid"></div>
</div>
<script>
const EVENTS = {data_json};
const TYPE_META = {type_meta_json};

const byDate = {{}};
for (const e of EVENTS) {{
  (byDate[e.date] = byDate[e.date] || []).push(e);
}}

const today = new Date();
let viewYear = today.getFullYear();
let viewMonth = today.getMonth(); // 0-indexed

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

function pad(n) {{ return String(n).padStart(2, "0"); }}

function render() {{
  document.getElementById("month-label").textContent = `${{MONTH_NAMES[viewMonth]}} ${{viewYear}}`;
  const grid = document.getElementById("cal-grid");
  grid.innerHTML = "";
  ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach(d => {{
    const el = document.createElement("div");
    el.className = "dow";
    el.textContent = d;
    grid.appendChild(el);
  }});

  const firstOfMonth = new Date(viewYear, viewMonth, 1);
  const startOffset = firstOfMonth.getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const todayStr = `${{today.getFullYear()}}-${{pad(today.getMonth()+1)}}-${{pad(today.getDate())}}`;

  const cellCount = Math.ceil((startOffset + daysInMonth) / 7) * 7;
  for (let i = 0; i < cellCount; i++) {{
    const dayNum = i - startOffset + 1;
    const cell = document.createElement("div");
    let dateStr = null;
    if (dayNum < 1 || dayNum > daysInMonth) {{
      cell.className = "day other-month";
    }} else {{
      dateStr = `${{viewYear}}-${{pad(viewMonth+1)}}-${{pad(dayNum)}}`;
      cell.className = "day" + (dateStr === todayStr ? " today" : "");
      const numEl = document.createElement("div");
      numEl.className = "day-num";
      numEl.textContent = dayNum;
      cell.appendChild(numEl);
      const dayEvents = byDate[dateStr] || [];
      const shown = dayEvents.slice(0, 4);
      for (const e of shown) {{
        const chip = document.createElement("div");
        chip.className = "chip";
        chip.style.background = (TYPE_META[e.type] || {{}}).color || "#8b949e";
        chip.textContent = e.label;
        chip.title = e.label;
        cell.appendChild(chip);
      }}
      if (dayEvents.length > shown.length) {{
        const more = document.createElement("div");
        more.className = "more";
        more.textContent = `+${{dayEvents.length - shown.length}} more`;
        more.title = dayEvents.slice(shown.length).map(e => e.label).join(", ");
        cell.appendChild(more);
      }}
    }}
    grid.appendChild(cell);
  }}
}}

document.getElementById("prev-month").addEventListener("click", () => {{
  viewMonth--;
  if (viewMonth < 0) {{ viewMonth = 11; viewYear--; }}
  render();
}});
document.getElementById("next-month").addEventListener("click", () => {{
  viewMonth++;
  if (viewMonth > 11) {{ viewMonth = 0; viewYear++; }}
  render();
}});

render();
</script>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    import os
    events = build_events()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "calendar_events.json"), "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    generate_calendar_html(events, os.path.join(out_dir, "calendar.html"))
    print(f"  calendar.html generated ({len(events)} events)")


if __name__ == "__main__":
    main()
