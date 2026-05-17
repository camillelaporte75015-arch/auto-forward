import os
import time
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import CreateChatRequest, ExportChatInviteRequest

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# =====================
# ENV
# =====================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# =====================
# CLIENTS
# =====================
user_client = TelegramClient("user_session", API_ID, API_HASH)
bot_app = Application.builder().token(BOT_TOKEN).build()

# =====================
# DATA
# =====================
cooldowns = {}
blocked = {}
pending = {}

COOLDOWN = 60
EXPIRE = 300

# =====================
# BOT /start
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merci d’utiliser .mm @username")

# =====================
# BOT .mm handler
# =====================
async def mm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if not text.startswith(".mm"):
        return

    parts = text.split()
    if len(parts) < 2:
        return

    target = parts[1].replace("@", "")

    now = time.time()

    # cooldown
    if user.id in cooldowns and now - cooldowns[user.id] < COOLDOWN:
        remaining = int(COOLDOWN - (now - cooldowns[user.id]))
        await update.message.reply_text(f"Merci d’attendre encore {remaining}s")
        return

    cooldowns[user.id] = now

    await update.message.delete()

    await update.message.reply_text(
        f"Invitation envoyée à @{target}"
    )

# =====================
# RECEIVE LINK FROM SELFBOT
# =====================
async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text.startswith("LINK|"):
        _, requester_id, link = text.split("|")

        await context.bot.send_message(
            chat_id=int(requester_id),
            text=f"Votre deal est prêt : {link}"
        )

# =====================
# REGISTER BOT HANDLERS
# =====================
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mm))
bot_app.add_handler(MessageHandler(filters.TEXT, receive_link))

# =====================
# SELFBOT LOGIC
# =====================
@user_client.on(events.NewMessage(pattern=r"\.mm (.+)"))
async def mm_self(event):
    sender = await event.get_sender()
    requester_id = sender.id
    requester_username = sender.username

    target_username = event.pattern_match.group(1).replace("@", "")

    try:
        target = await user_client.get_entity(target_username)
    except:
        await event.reply("Utilisateur introuvable")
        return

    # block check
    if requester_id in blocked and target.id in blocked[requester_id]:
        await event.reply(f"@{target_username} refuse vos demandes")
        return

    pending[target.id] = requester_id

    await user_client.send_message(
        target.id,
        "Demande de deal. Répondez: accepté ou refus"
    )

# =====================
# STOP
# =====================
@user_client.on(events.NewMessage(pattern=r"\.stop (.+)"))
async def stop(event):
    sender = await event.get_sender()
    target = await user_client.get_entity(event.pattern_match.group(1).replace("@", ""))

    blocked.setdefault(sender.id, set()).add(target.id)

    await event.reply(f"@{target.username} bloqué")

# =====================
# UNSTOP
# =====================
@user_client.on(events.NewMessage(pattern=r"\.unstop (.+)"))
async def unstop(event):
    sender = await event.get_sender()
    target = await user_client.get_entity(event.pattern_match.group(1).replace("@", ""))

    if sender.id in blocked:
        blocked[sender.id].discard(target.id)

    await event.reply(f"@{target.username} débloqué")

# =====================
# ACCEPT / REFUS
# =====================
@user_client.on(events.NewMessage(pattern="(?i)accepté|refus"))
async def response(event):
    sender = await event.get_sender()
    sender_id = sender.id

    if sender_id not in pending:
        return

    requester_id = pending[sender_id]

    requester = await user_client.get_entity(requester_id)

    text = event.raw_text.lower()

    if text == "refus":
        await user_client.send_message(requester_id, "Deal refusé")
        return

    # ACCEPTÉ
    chat = await user_client(CreateChatRequest(
        users=[requester, sender],
        title=f"mm deal {requester_id}-{sender_id}"
    ))

    chat = chat.chats[0]

    invite = await user_client(ExportChatInviteRequest(chat))

    link = invite.link

    await user_client.send_message(
        "me",
        f"LINK|{requester_id}|{link}"
    )

    del pending[sender_id]

# =====================
# RUN
# =====================
async def main():
    await user_client.start(PHONE)
    print("Selfbot ON")

    await asyncio.gather(
        bot_app.run_polling(),
        user_client.run_until_disconnected()
    )

asyncio.run(main())
