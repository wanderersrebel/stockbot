"""Discover your Telegram chat id. Run:  python get_chat_id.py

Prerequisite: you must have messaged your bot at least once,
otherwise Telegram has no 'update' to report.
"""
import urllib.request
import json
import sys

token = sys.argv[1] if len(sys.argv) > 1 else input("Bot token: ").strip()
url = f"https://api.telegram.org/bot{token}/getUpdates"
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read().decode())
    updates = data.get("result", [])
    if not updates:
        print("No messages yet. Open your bot in Telegram and send it a message,")
        print("then rerun this script.")
    else:
        print("Found these chats (use the id for TELEGRAM_CHAT_ID):")
        for u in updates:
            chat = u.get("message", {}).get("chat", {})
            name = f"{chat.get('first_name','')} {chat.get('last_name','')} (@{chat.get('username','')})".strip()
            print(f"  chat_id = {chat.get('id')}   {name}")
except Exception as e:
    print(f"Error: {e}")
