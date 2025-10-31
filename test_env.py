from dotenv import load_dotenv
import os

load_dotenv()
print("CHANNEL_ID:", os.getenv("CHANNEL_ID"))
print("DISCORD_TOKEN:", os.getenv("DISCORD_TOKEN"))