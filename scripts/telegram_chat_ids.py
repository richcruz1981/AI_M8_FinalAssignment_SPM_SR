"""Lista los chat_id de quienes enviaron /start al bot (para llenar config/recipients.yaml o el secret RECIPIENTS_YAML).

Uso: TELEGRAM_BOT_TOKEN=xxxx python scripts/telegram_chat_ids.py
"""
import os
import sys

import requests

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    sys.exit("Define TELEGRAM_BOT_TOKEN")
r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
if not r.get("ok"):
    sys.exit(f"Error: {r}")
seen = {}
for u in r.get("result", []):
    msg = u.get("message") or u.get("edited_message") or {}
    chat = msg.get("chat", {})
    if chat.get("id"):
        seen[chat["id"]] = (chat.get("first_name", ""), chat.get("username", ""), msg.get("text", ""))
for cid, (name, user, text) in seen.items():
    print(f"chat_id={cid}  nombre={name}  usuario=@{user}  último_texto={text!r}")
if not seen:
    print("Sin mensajes. Pide a cada PM/PgM/PfM que abra el bot y envíe /start, luego vuelve a ejecutar.")
