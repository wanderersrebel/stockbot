"""Notifications: Telegram + Discord webhook, else console print.

Secrets come from secrets.py:
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID  -> Telegram alerts
  DISCORD_WEBHOOK_URL               -> Discord alerts (channel webhook)
If a channel is blank or fails, the other still fires; if both blank, it prints.
The bot never crashes on missing creds.
"""
import urllib.request
import urllib.parse
import json

try:
    from secrets import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK_URL)
except Exception:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    DISCORD_WEBHOOK_URL = ""


def send_telegram(token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def send_discord(webhook: str, text: str):
    # Discord webhooks take JSON {"content": "..."}. Split long msgs if needed.
    MAX = 1900
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)] or [text]
    for ch in chunks:
        data = json.dumps({"content": ch}).encode()
        req = urllib.request.Request(
            webhook, data=data,
            headers={"Content-Type": "application/json",
                     "User-Agent": "StockBot/1.0 (https://github.com/wanderersrebel)"},
            method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()


def notify(message: str):
    sent = False
    # Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            send_telegram(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, message)
            print(f"  [telegram] {message}")
            sent = True
        except Exception as e:
            print(f"  ! telegram failed: {e}")
    # Discord
    if DISCORD_WEBHOOK_URL:
        try:
            send_discord(DISCORD_WEBHOOK_URL, message)
            print(f"  [discord] {message}")
            sent = True
        except Exception as e:
            print(f"  ! discord failed: {e}")
    if not sent:
        print(f"[ALERT] {message}")
