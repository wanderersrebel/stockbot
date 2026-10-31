"""Incident bot listener: receives your incoming Telegram messages to
@Wander_incident_bot, logs them to incident_log.txt, and acks.

Stdlib only. Run:  python incident_listen.py   (background)
Stop:  Ctrl+C

It keeps a persistent offset in state/incident_offset.json so it never
re-processes old messages. Each inbound message is appended to
incident_log.txt as:  [YYYY-MM-DD HH:MM] <name>: <text>
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import secrets

STATE_DIR = os.path.join(os.path.dirname(__file__), "state")
OFFSET_FILE = os.path.join(STATE_DIR, "incident_offset.json")
LOG_FILE = os.path.join(os.path.dirname(__file__), "incident_log.txt")
POLL_SECONDS = 5


def _api(method, **params):
    url = f"https://api.telegram.org/bot{secrets.INCIDENT_TELEGRAM_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error_code": e.code}
    except Exception:
        return {"ok": False}


def _load_offset():
    try:
        return json.load(open(OFFSET_FILE))["offset"]
    except Exception:
        return 0


def _save_offset(offset):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump({"offset": offset}, open(OFFSET_FILE, "w"))


def _log(name, text):
    os.makedirs(STATE_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"[{stamp}] {name}: {text}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.rstrip())


def main():
    offset = _load_offset()
    print(f"Incident listener live (chat {secrets.INCIDENT_TELEGRAM_CHAT_ID}). "
          f"Polling every {POLL_SECONDS}s. Ctrl+C to stop.")
    while True:
        try:
            res = _api("getUpdates", offset=offset, timeout=POLL_SECONDS + 5)
            if res.get("ok"):
                for u in res.get("result", []):
                    offset = u["update_id"] + 1
                    msg = u.get("message") or u.get("edited_message")
                    if not msg:
                        continue
                    chat = msg.get("chat", {})
                    name = chat.get("first_name") or chat.get("username") or chat.get("id")
                    text = msg.get("text", "")
                    if str(chat.get("id")) == str(secrets.INCIDENT_TELEGRAM_CHAT_ID) and text:
                        _log(name, text)
                        # ack
                        _api("sendMessage",
                             chat_id=secrets.INCIDENT_TELEGRAM_CHAT_ID,
                             text="\u2705 received & logged.")
                    _save_offset(offset)
        except KeyboardInterrupt:
            print("\nListener stopped.")
            break
        except Exception as e:
            print("poll error:", e)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
