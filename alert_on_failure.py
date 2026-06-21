#!/usr/bin/env python3
"""
Email alert if the daily event-scanner cron run failed or was killed for
hanging too long. Invoked from /etc/cron.d/event_scanner on the VPS:

  timeout 10m /bin/bash vps_daily_run.sh >> logs.log 2>&1 || python3 alert_on_failure.py

Reuses the same Resend alert config as the trading bots' watchdog
(/opt/scripts/watchdog.py) — see /etc/bot_alert.conf (root-only, not in git).
"""
import json
import subprocess
import urllib.request

CONF_FILE = "/etc/bot_alert.conf"
LOG_FILE = "/opt/event_scanner/logs.log"
TAIL_LINES = 60


def send_alert(conf, subject, body):
    payload = json.dumps({
        "from": conf["from_email"],
        "to": [conf["alert_email"]],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {conf['resend_api_key']}",
                 "Content-Type": "application/json",
                 # Resend sits behind Cloudflare, which blocks the default
                 # urllib User-Agent (error code 1010) as a bot signature.
                 "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def main():
    conf = json.load(open(CONF_FILE))
    tail = subprocess.run(
        ["tail", f"-{TAIL_LINES}", LOG_FILE], capture_output=True, text=True
    ).stdout
    send_alert(
        conf,
        "Event Scanner: daily run failed or timed out",
        "vps_daily_run.sh exited non-zero, or was killed after running longer "
        f"than 10 minutes.\n\nLast {TAIL_LINES} lines of {LOG_FILE}:\n\n{tail}",
    )


if __name__ == "__main__":
    main()
