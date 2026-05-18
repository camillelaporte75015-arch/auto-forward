from telethon import TelegramClient, functions
from telethon.errors import FloodWaitError
import asyncio

# Tes infos
api_id = 12345678
api_hash = "TON_API_HASH"

SOURCE_CHAT = "ua_logs"
MESSAGE_ID = 2
FOLDER_LINK = "https://t.me/addlist/UG4R-kbEAbNmY2Jk"

client = TelegramClient("session", api_id, api_hash)


async def get_chats():
    result = await client(functions.chatlists.JoinChatlistInviteRequest(
        slug=FOLDER_LINK.split("/")[-1],
        peers=[]
    ))
    return result.chats


async def main():
    await client.start()
    print("Userbot connecté")

    source = await client.get_entity(SOURCE_CHAT)

    while True:
        try:
            msg = await client.get_messages(source, ids=MESSAGE_ID)

            if not msg:
                print("Message introuvable")
                await asyncio.sleep(30)
                continue

            chats = await get_chats()

            print(f"Envoi vers {len(chats)} canaux...")

            for chat in chats:
                try:
                    await client.forward_messages(chat.id, msg)
                    print(f"Envoyé -> {chat.title}")

                    # petit délai entre chaque canal
                    await asyncio.sleep(2)

                except FloodWaitError as e:
                    print(f"FloodWait: {e.seconds}s")
                    await asyncio.sleep(e.seconds)

                except Exception as e:
                    print(f"Erreur {chat.title}: {e}")

            print("Cycle terminé → attente 30 sec")
            await asyncio.sleep(30)

        except Exception as e:
            print("Erreur globale :", e)
            await asyncio.sleep(30)


with client:
    client.loop.run_until_complete(main())
