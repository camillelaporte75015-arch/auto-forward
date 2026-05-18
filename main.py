from telethon import TelegramClient
from telethon.errors import FloodWaitError
import asyncio

api_id = 12345678
api_hash = "TON_API_HASH"

SOURCE_CHAT = "ua_logs"
MESSAGE_ID = 2

client = TelegramClient("session", api_id, api_hash)


async def get_channels():
    channels = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        # garde seulement les channels/groups
        if getattr(entity, "broadcast", False) or getattr(entity, "megagroup", False):
            channels.append(entity)

    return channels


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

            channels = await get_channels()

            print(f"{len(channels)} canaux trouvés")

            for channel in channels:
                try:
                    await client.forward_messages(channel.id, msg)
                    print(f"Envoyé -> {channel.title}")

                    await asyncio.sleep(2)

                except FloodWaitError as e:
                    print(f"Flood wait {e.seconds}s")
                    await asyncio.sleep(e.seconds)

                except Exception as e:
                    print(f"Erreur {channel.title}: {e}")

            print("Attente 30 secondes...")
            await asyncio.sleep(30)

        except Exception as e:
            print(f"Erreur globale: {e}")
            await asyncio.sleep(30)


with client:
    client.loop.run_until_complete(main())
