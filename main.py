from telethon import TelegramClient, events
import asyncio, re
from flask import Flask
from threading import Thread

# ---------------- CONFIG ----------------
api_id = 34851852
api_hash = "44d65a2b2fd2febf46c9062b48878f6b"
client = TelegramClient("session", api_id, api_hash)

# État par utilisateur
user_state = {}

# ---------------- UTIL ----------------
def parse_tg_link(link):
    m = re.match(r'https://t\.me/(?:c/)?([\w\d_-]+)/(\d+)', link)
    if m:
        chat_part, msg_id = m.group(1), int(m.group(2))
        chat_id = -1000000000000 + int(chat_part) if chat_part.isdigit() else chat_part
        return chat_id, msg_id
    return None, None

# ---------------- COMMANDES DASHBOARD ----------------
@client.on(events.NewMessage(pattern=r'^\.start$'))
async def start(event):
    uid = event.sender_id
    user_state[uid] = {"step": 1, "running": False}
    await event.respond("Salut ! Envoie le lien du message que tu veux transférer :")

@client.on(events.NewMessage(pattern=r'^\.stop$'))
async def stop(event):
    uid = event.sender_id
    state = user_state.get(uid)
    if state and state.get("running"):
        state["running"] = False
        await event.respond("Transfert arrêté ✅")
    else:
        await event.respond("Aucun transfert en cours.")

@client.on(events.NewMessage(pattern=r'^\.status$'))
async def status(event):
    uid = event.sender_id
    state = user_state.get(uid)
    if not state:
        await event.respond("Aucun transfert configuré.")
        return

    source = state.get("source", {})
    targets = state.get("targets", [])
    running = "En cours ✅" if state.get("running") else "Arrêté ❌"
    total_counter = state.get("counter", 0)
    total_errors = state.get("errors", 0)

    topic_summary = ""
    for t in targets:
        topic_summary += f" - {t['chat']} / Topic {t['topic']} : {t.get('counter',0)}\n"
    if not topic_summary:
        topic_summary = "Aucune destination"

    await event.respond(f"=== Dashboard UserBot ===\n"
                        f"Message source : {source.get('chat','')} / ID {source.get('msg_id','')}\n"
                        f"Délai : {state.get('delay','')} secondes\n"
                        f"État : {running}\n"
                        f"Total messages transférés : {total_counter}\n"
                        f"Total erreurs : {total_errors}\n\n"
                        f"Messages par topic :\n{topic_summary}")

@client.on(events.NewMessage(pattern=r'^\.add (.+)$'))
async def add_destination(event):
    uid = event.sender_id
    state = user_state.get(uid)
    if not state:
        await event.respond("Configure d'abord un transfert avec .start")
        return
    link = event.pattern_match.group(1)
    chat_id, msg_id = parse_tg_link(link)
    if chat_id:
        state.setdefault("targets", []).append({"chat": chat_id, "topic": msg_id, "counter": 0})
        await event.respond(f"Destination ajoutée : {chat_id} / Topic {msg_id}")
    else:
        await event.respond("Lien invalide.")

@client.on(events.NewMessage(pattern=r'^\.remove (.+)$'))
async def remove_destination(event):
    uid = event.sender_id
    state = user_state.get(uid)
    if not state or "targets" not in state:
        await event.respond("Aucune destination à supprimer")
        return
    link = event.pattern_match.group(1)
    chat_id, msg_id = parse_tg_link(link)
    if chat_id:
        state["targets"] = [t for t in state["targets"] if not (t["chat"]==chat_id and t["topic"]==msg_id)]
        await event.respond(f"Destination supprimée : {chat_id} / Topic {msg_id}")
    else:
        await event.respond("Lien invalide.")

@client.on(events.NewMessage(pattern=r'^\.update_delay (\d+)$'))
async def update_delay(event):
    uid = event.sender_id
    state = user_state.get(uid)
    if not state:
        await event.respond("Configure d'abord un transfert avec .start")
        return
    delay = int(event.pattern_match.group(1))
    state["delay"] = delay
    await event.respond(f"Nouveau délai appliqué : {delay} secondes")

# ---------------- CONFIGURATION ET TRANSFERT ----------------
@client.on(events.NewMessage)
async def handle_message(event):
    uid = event.sender_id
    state = user_state.get(uid)
    if not state or state.get("step") not in [1,2,3]:
        return
    
    if state["step"] == 1:
        chat_id, msg_id = parse_tg_link(event.text)
        if chat_id:
            state["source"] = {"chat": chat_id, "msg_id": msg_id}
            state["step"] = 2
            await event.respond("Super ! Envoie les liens des topics où envoyer le message, un par ligne :")
        else:
            await event.respond("Lien invalide.")

    elif state["step"] == 2:
        lines = event.text.splitlines()
        targets = []
        for line in lines:
            chat_id, msg_id = parse_tg_link(line)
            if chat_id:
                targets.append({"chat": chat_id, "topic": msg_id, "counter": 0})
        if targets:
            state["targets"] = targets
            state["step"] = 3
            summary = "\n".join([f"- {t['chat']} / Topic {t['topic']}" for t in targets])
            await event.respond(f"Destinations :\n{summary}\nMaintenant indique le délai en secondes entre chaque envoi :")
        else:
            await event.respond("Aucun lien valide détecté, réessaie.")

    elif state["step"] == 3:
        try:
            delay = int(event.text)
            state["delay"] = delay
            state["running"] = True
            state["counter"] = 0
            state["errors"] = 0
            state["step"] = 4
            await event.respond(f"Transfert démarré toutes les {delay} secondes.\nTu peux utiliser `.stop` pour arrêter.\nMessages transférés : 0\nErreurs : 0")
            asyncio.create_task(forward_loop(uid))
        except:
            await event.respond("Délai invalide, envoie un nombre en secondes.")

async def forward_loop(uid):
    state = user_state[uid]
    source = state["source"]
    targets = state.get("targets", [])
    delay = state["delay"]

    while state.get("running"):
        for t in targets:
            try:
                await client.forward_messages(t["chat"], source["msg_id"], source["chat"], reply_to=t["topic"])
                t["counter"] = t.get("counter", 0) + 1
                state["counter"] = state.get("counter", 0) + 1
            except Exception as e:
                state["errors"] = state.get("errors", 0) + 1
                print(f"Erreur {t['chat']}: {e}")
        await client.send_message(uid, f"Messages transférés : {state['counter']}\nErreurs : {state['errors']}")
        await asyncio.sleep(delay)

# ---------------- KEEP ALIVE POUR REPLIT ----------------
app = Flask('')

@app.route('/')
def home():
    return "Userbot actif ✅"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---------------- DEMARRAGE ----------------
keep_alive()
client.start()
client.run_until_disconnected()
