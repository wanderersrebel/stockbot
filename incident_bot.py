"""Incident-case Telegram bot (@Wander_incident_bot).

Two modes:
  python incident_bot.py --once            send incident summary to your chat
  python incident_bot.py --listen          poll for incoming messages and reply

Stdlib only. Secrets from secrets.py.
"""

import json
import sys
import time
import urllib.request
import urllib.error

import secrets


def _api(method, token, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error_code": e.code,
                "description": e.read().decode()[:300]}
    except Exception as e:  # network blip
        return {"ok": False, "description": str(e)}


def get_my_chat_id():
    """Return your chat id by polling getUpdates, else the saved one."""
    if secrets.INCIDENT_TELEGRAM_CHAT_ID:
        return secrets.INCIDENT_TELEGRAM_CHAT_ID
    res = _api("getUpdates", secrets.INCIDENT_TELEGRAM_TOKEN)
    if res.get("ok"):
        for u in res.get("result", []):
            msg = (u.get("message") or
                   u.get("edited_message") or
                   u.get("channel_post"))
            if msg and "chat" in msg:
                return str(msg["chat"]["id"])
    return None


def send(text, chat_id=None):
    """Send a message to your chat via the incident bot. Returns bool."""
    if chat_id is None:
        chat_id = get_my_chat_id()
    if not chat_id:
        print("[incident_bot] No chat id yet - message @Wander_incident_bot first.")
        return False
    res = _api("sendMessage", secrets.INCIDENT_TELEGRAM_TOKEN,
               chat_id=chat_id, text=text, parse_mode="HTML")
    ok = res.get("ok", False)
    print(f"[incident_bot] sent={ok} chat={chat_id}")
    if not ok:
        print("   ", res)
    return ok


def _find_newest_update_id(updates):
    """Return the highest update_id across all updates in one poll."""
    best = 0
    for u in updates:
        uid = u.get("update_id", 0)
        if uid > best:
            best = uid
    return best


def _message_text(update):
    """Extract plain text from a message update (or None)."""
    msg = (update.get("message") or
           update.get("edited_message") or
           update.get("channel_post"))
    if not msg:
        return None
    # text may be None for media-only messages
    return msg.get("text")


def _reply(text, chat_id):
    """Send a reply, using sendMessage reply_to_message_id when possible."""
    # Try to infer the last seen message id for threading
    res = _api("sendMessage", secrets.INCIDENT_TELEGRAM_TOKEN,
               chat_id=chat_id, text=text, parse_mode="HTML")
    ok = res.get("ok", False)
    print(f"[incident_bot] reply sent={ok} chat={chat_id}")
    if not ok:
        print("   ", res)
    return ok


def _handle_message(text, chat_id):
    """Return a reply (plain string, may be empty) for a user message.

    Kept deliberately simple and supportive. No medical advice, no
    diagnosis - just consistent, low-pressure presence.
    """
    t = (text or "").strip()
    if not t:
        return ""

    low = t.lower()

    # Crisis / distress signals -> offer direct support routes immediately
    if any(k in low for k in ["not good", "not feel good", "bad", "suicide",
                                "kill myself", "end it", "want to die",
                                "self harm", "selfharm", "hurt myself",
                                "can't cope", "crisis"]):
        return (
            "Thank you for telling me you don't feel good. That takes courage, "
            "and I'm glad you reached out here.\n\n"
            "You are not alone with this. If you feel in immediate danger or "
            "like you might hurt yourself, please ring <b>999</b> right now.\n\n"
            "If you need someone to talk to any time, day or night:\n"
            "  - <b>Samaritans: 116 123</b> (free, confidential, 24/7)\n"
            "  - <b>111 option 2</b> for the Wales mental health crisis line\n\n"
            "I can keep listening here too - tell me more if you want to."
        )

    # Check-in responses
    if any(k in low for k in ["hello", "hi", "hey", "morning", "afternoon",
                                "evening", "test", "ping", "are you there"]):
        return (
            "I'm here. What's on your mind today?"
        )

    # Bot self-test / status
    if any(k in low for k in ["status", "how are you", "are you working",
                                "do you work", "respond", "reply", "answer"]):
        return (
            "I'm working and I can reply now. You can tell me how you're "
            "feeling, what's going on, or anything you want to say - I'll "
            "respond. This is a safe space, no judgment."
        )

    # Support resources
    if any(k in low for k in ["who can help", "help me", "support",
                                "victim support", "phone", "number"]):
        return (
            "Here are the numbers that can help you directly:\n\n"
            "  - <b>Victim Support: 0808 168 9111</b> (free, 24/7, for victims "
            "of crime) - they can advocate with the police for you\n"
            "  - <b>Samaritans: 116 123</b> (free, confidential, 24/7)\n"
            "  - <b>111 option 2</b> for the Wales mental health crisis line\n"
            "  - <b>999</b> in an emergency\n\n"
            "Victim Support is often the best first call for case-related "
            "support and advocacy."
        )

    # Case / incident related
    if any(k in low for k in ["case", "bail", "police", "gorringe",
                                "2600267057", "suspect", "hale",
                                "condition", "johnny", "caydan"]):
        return (
            "On your case (ref 2600267057 with PC Gorringe 07816 180901): "
            "both suspects are on bail while the file goes to the CPS. If the "
            "police aren't giving you the support you need, Victim Support "
            "(0808 168 9111) can advocate on your behalf and help push for "
            "bail variation or a senior officer review. You can also ask your "
            "solicitor about an exclusion zone around your address."
        )

    # Mental health / feelings
    if any(k in low for k in ["feel", "feeling", "anxious", "anxiety",
                                "stress", "worried", "scared", "frightened",
                                "angry", "frustrated", "lonely", "sad",
                                "depressed", "down", "can't sleep", "sleep"]):
        return (
            "Thanks for telling me that. Feeling like that is heavy to carry "
            "on your own. A few things that may help:\n\n"
            "  - <b>Samaritans 116 123</b> - free, confidential, any time\n"
            "  - <b>111 option 2</b> - Wales mental health crisis line\n"
            "  - <b>Hollie Guard</b> is on your phone if you need a personal alarm\n\n"
            "If you want to talk here, I'm listening. What's been the worst bit "
            "today?"
        )

    # Practical / appointment
    if any(k in low for k in ["appointment", "counselling", "therapist",
                                "doctor", "gp", "hospital", "hirwaun"]):
        return (
            "For your counselling appointment (2/10/2026 09:45 at Hirwaun "
            "Health Centre) - keep the details handy and consider setting two "
            "reminders: one for the day before and one for the morning. If "
            "you're struggling to wait until then, Victim Support or your GP "
            "may be able to help with earlier support."
        )

    # Default - generic supportive acknowledgement, invite more
    return (
        "I hear you. I'm here and I'm listening - you can tell me as much or "
        "as little as you want. No judgment, no pressure to fix anything right "
        "now. What's on your mind?"
    )


def _mark_seen(updates):
    """Return the offset to use for the NEXT getUpdates call so we skip
    everything we've already processed."""
    highest = 0
    for u in updates:
        uid = u.get("update_id", 0)
        if uid > highest:
            highest = uid
    return highest + 1


def listen_once(last_offset):
    """Poll once. For each message we haven't seen, print it and send a reply.
    Return the new offset to use next time (or the old one if nothing)."""
    res = _api("getUpdates",
               secrets.INCIDENT_TELEGRAM_TOKEN,
               offset=last_offset,
               timeout=0,
               allowed_updates=["message", "edited_message"])

    if not res.get("ok"):
        print("[incident_bot] getUpdates error:", res.get("description"))
        return last_offset

    updates = res.get("result", [])
    if not updates:
        return last_offset

    new_offset = _mark_seen(updates)
    for u in updates:
        text = _message_text(u)
        if not text:
            continue
        msg_obj = (u.get("message") or
                   u.get("edited_message") or
                   u.get("channel_post"))
        chat_id = str(msg_obj.get("chat", {}).get("id", ""))
        if not chat_id:
            continue
        # Only reply to your chat (skip any group/other chats)
        saved = secrets.INCIDENT_TELEGRAM_CHAT_ID
        if saved and str(chat_id) != str(saved):
            # If we have a saved chat id, only talk to that one
            continue
        reply_text = _handle_message(text, chat_id)
        if reply_text:
            _reply(reply_text, chat_id)

    return new_offset


def listen_loop():
    """Poll continuously: each new message -> print + reply."""
    chat_id = get_my_chat_id()
    if not chat_id:
        print("[incident_bot] STEP 1: open https://t.me/Wander_incident_bot "
              "and send any message, then re-run with --listen.")
        print("[incident_bot] (or use --once to just get the incident summary)")
        return

    print(f"[incident_bot] listening for messages from chat {chat_id}")
    print("[incident_bot] reply mode active - any message you send gets a reply")
    last_offset = chat_id  # start from 0, really
    last_offset = 0

    while True:
        last_offset = listen_once(last_offset)
        time.sleep(2)


def main():
    print("Incident bot:",
          _api("getMe", secrets.INCIDENT_TELEGRAM_TOKEN)
          .get("result", {})
          .get("username", "unknown"))

    if "--listen" in sys.argv:
        listen_loop()
        return

    # Default: one-shot send of the incident summary
    chat_id = get_my_chat_id()
    if not chat_id:
        print("STEP 1: open https://t.me/Wander_incident_bot and send any "
              "message.")
        print("STEP 2: run this again - it will deliver the summary.")
        return
    send(INCIDENT_SUMMARY)


INCIDENT_SUMMARY = """<b>INCIDENT CASE SUMMARY</b> (from secure notes)

<b>Ref:</b> 2600267057
<b>Officer:</b> PC Gorringe (SWP) 07816 180901
<b>Date/time:</b> 15 Aug 2026, ~16:25
<b>Location:</b> 15 Wenallt Rd, Abernant, CF44

<b>Suspects:</b>
- Johnny Hayton (adult; licence + tag to 2030; Penywaun; current partner of
  Heidi, 9 Wenallt - your ex-partner)
- Caydan Williams (b. ~2008; bail 18 Sep 2026)
- Both bailed ~3 months

<b>Flags:</b>
- Ex false rape allegation (warned)
- Subject mental-health contact 02/09
- Do NOT contact suspects
- Exclude 2019 / 2023 clip footage
- Johnny seen on Wenallt Rd, ~3 doors from your address - safety concern raised
  with police, response was "nothing we can do unless he contacts you"
- Ex-partner Heidi now with Johnny - proximity/intimidation concern

<b>Actions:</b>
- CICA compensation claim by 15 Aug 2028
- Medical: Crohn's + Steqeyma (ustekinumab) - keep GP/hospital informed
- Counselling appt: 2/10/2026 09:45 at Hirwaun Health Centre
- Victim Support: 0808 168 9111
- Samaritans: 116 123
- 111 option 2 for Wales mental health crisis line
- 999 in emergency

<i>This is a copy of recorded notes, not legal advice.</i>"""


if __name__ == "__main__":
    main()
