"""Send the daily one-liner to your phone.

Every channel is configured purely through environment variables and is
skipped when its variables are absent, so the trader never fails because a
notification could not be sent. Configure one or several:

  SMS via Twilio (a real text message)
      TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM (+1...), TWILIO_TO (+1...)

  SMS via your carrier's email-to-text gateway (free, needs any SMTP mailbox)
      SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
      SMS_EMAIL_TO  e.g. 5551234567@tmomail.net (T-Mobile), @vtext.com (Verizon)

  Push notification via ntfy.sh (free, no account; install the ntfy app and
  subscribe to a topic name of your choosing)
      NTFY_TOPIC            (optionally NTFY_SERVER, default https://ntfy.sh)

  Telegram (free; create a bot with @BotFather, message it once, get chat id)
      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import datetime as dt
import os
import smtplib
from email.message import EmailMessage

import requests

from .config import TVMConfig, DEFAULT

TIMEOUT = 20


def to_text(report: dict, perf: dict | None, cfg: TVMConfig = DEFAULT, mode: str = "") -> str:
    """Compact status line; stays under ~300 chars so it fits in two SMS segments."""
    sig, after = report["signal"], report["state_after"]
    day = dt.date.fromisoformat(report["as_of"]).strftime("%b %d")
    head = f"TVM {day}"
    if mode and mode != "live":
        head += f" [{mode}]"
    if sig["risk_on"]:
        pos = f"RISK-ON {after['asset']} {after['exposure']:.2f}x (vol {sig['realized_vol']:.0%})"
    else:
        pos = "RISK-OFF -> cash (below 200d SMA)"
    if report["orders"]:
        parts = []
        for o in report["orders"]:
            if o["liquidate"]:
                parts.append(f"sell all {o['symbol']}")
            else:
                parts.append(f"{'buy' if o['notional'] > 0 else 'sell'} {o['symbol']} ${abs(o['notional']) / 1000:.1f}k")
        trades = ("Orders (not sent): " if report["dry_run"] else "Orders: ") + ", ".join(parts)
    else:
        trades = "No trades"
    perf_txt = f"Equity ${report['equity']:,.0f}"
    if perf:
        perf_txt = (f"Paper ${perf['equity']:,.0f} {perf['strategy_return']:+.1%} vs {cfg.benchmark_symbol} "
                    f"{perf['benchmark_return']:+.1%} since {dt.date.fromisoformat(perf['since']).strftime('%b %d')}")
    return f"{head}: {pos}. {trades}. {perf_txt}."


# --------------------------------------------------------------------------- channels

def send_twilio(text: str, env=os.environ) -> bool:
    sid, token = env.get("TWILIO_ACCOUNT_SID"), env.get("TWILIO_AUTH_TOKEN")
    frm, to = env.get("TWILIO_FROM"), env.get("TWILIO_TO")
    if not all([sid, token, frm, to]):
        return False
    r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                      auth=(sid, token), data={"From": frm, "To": to, "Body": text}, timeout=TIMEOUT)
    r.raise_for_status()
    return True


def send_email_sms(text: str, env=os.environ, smtp_factory=smtplib.SMTP) -> bool:
    host, user, pw, to = env.get("SMTP_HOST"), env.get("SMTP_USER"), env.get("SMTP_PASSWORD"), env.get("SMS_EMAIL_TO")
    if not all([host, user, pw, to]):
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, ""
    msg.set_content(text)
    with smtp_factory(host, int(env.get("SMTP_PORT", "587")), timeout=TIMEOUT) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    return True


def send_ntfy(text: str, env=os.environ) -> bool:
    topic = env.get("NTFY_TOPIC")
    if not topic:
        return False
    server = env.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    r = requests.post(f"{server}/{topic}", data=text.encode("utf-8"),
                      headers={"Title": "TVM paper trading", "Tags": "chart_with_upwards_trend"}, timeout=TIMEOUT)
    r.raise_for_status()
    return True


def send_telegram(text: str, env=os.environ) -> bool:
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=TIMEOUT)
    r.raise_for_status()
    return True


CHANNELS = {"twilio": send_twilio, "email-sms": send_email_sms, "ntfy": send_ntfy, "telegram": send_telegram}


def send_all(text: str, env=os.environ, log=print) -> dict[str, str]:
    """Try every configured channel. Returns {channel: 'sent' | 'skipped' | 'error: ...'}."""
    results: dict[str, str] = {}
    for name, fn in CHANNELS.items():
        try:
            results[name] = "sent" if fn(text, env) else "skipped"
        except Exception as exc:  # a broken notifier must never break the trading run
            results[name] = f"error: {exc}"
            log(f"notification via {name} failed: {exc}")
    return results
