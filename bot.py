# bot.py
import discord
import asyncio
import aiohttp
from sales_listener import check_sales
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone

# .ENV
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
RONIN_API_URL = os.getenv("RONIN_API_URL")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS"))
FETCH_SIZE = int(os.getenv("FETCH_SIZE"))


class NFTSalesBot(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session: aiohttp.ClientSession | None = None
        self.channel = None
        self.last_timestamp: int = 0
        self.seen_tx_hashes: set[str] = set()
        self.running = True
        self.bg_task = None

    async def setup_hook(self):
        # Se ejecuta antes de on_ready; ideal para crear la sesión HTTP
        self.session = aiohttp.ClientSession()
        # Crear tarea de polling
        self.bg_task = asyncio.create_task(self._poll_sales())

    async def on_ready(self):
        print(f"Conectado como {self.user} (ID: {self.user.id})")
        self.channel = self.get_channel(CHANNEL_ID)
        if not self.channel:
            print(f"[ERROR] No se encontró el canal con ID {CHANNEL_ID}")
            await self.close()
            return
        await self.channel.send("✅ **Bot de seguimiento de ventas de NFTs iniciado!**")

    async def _poll_sales(self):
        # Esperar a que esté listo y el canal asignado
        await self.wait_until_ready()
        while not self.is_closed() and self.running:
            try:
                new_ts = await check_sales(
                    self.session, self.channel, RONIN_API_URL, API_KEY,
                    self.last_timestamp, COLLECTION_NAME, CONTRACT_ADDRESS,
                    FETCH_SIZE, self.seen_tx_hashes
                )
                if new_ts > self.last_timestamp:
                    self.last_timestamp = new_ts
                    print(f"[INFO] last_timestamp actualizado a {self.last_timestamp}")
            except Exception as e:
                print(f"[ERROR] Ciclo de polling: {e}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def close(self):
        self.running = False
        if self.bg_task:
            self.bg_task.cancel()
        if self.session:
            await self.session.close()
        await super().close()

intents = discord.Intents.default()
client = NFTSalesBot(intents=intents)
client.run(DISCORD_TOKEN)


