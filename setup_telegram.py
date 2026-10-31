"""One-time Telegram setup. Run:  python setup_telegram.py

It writes your token + chat id into secrets.py (which is git-ignored).
Your secrets are never printed back to the screen after entry.
"""
import os

SECRETS = os.path.join(os.path.dirname(__file__), "secrets.py")
TOKEN_HINT = 'TELEGRAM_TOKEN = "{}"\n'
CHAT_HINT = 'TELEGRAM_CHAT_ID = "{}"\n'


def main():
    print("=== StockBot Telegram setup ===")
    print("1) In Telegram, message @BotFather -> /newbot -> give it a name.")
    print("   BotFather replies with a token like 123456:ABC-DEF....")
    print("2) Open your new bot and send it any message (e.g. 'hi').")
    print("3) Run:  python get_chat_id.py  -> it prints your chat id.")
    print()
    token = input("Paste your bot token: ").strip()
    chat_id = input("Paste your chat id: ").strip()
    if not token or not chat_id:
        print("Both values are required. Aborting.")
        return
    with open(SECRETS, "w") as f:
        f.write(TOKEN_HINT.format(token))
        f.write(CHAT_HINT.format(chat_id))
    print("\nSaved to secrets.py. Sending a test message...")
    try:
        import notifier
        notifier.notify("StockBot connected OK")
        print("Check Telegram — you should have received the test message.")
    except Exception as e:
        print(f"Test send failed: {e}")


if __name__ == "__main__":
    main()
