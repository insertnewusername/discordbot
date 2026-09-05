import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# 1. Create a minimal Web Server to keep Render Happy
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Start Flask in a background thread
threading.Thread(target=run_flask, daemon=True).start()

# 2. Discord Bot Setup
TARGET_USER_ID = 1302824809167589386

intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.event
async def on_presence_update(before, after):
    if after.id != TARGET_USER_ID:
        return

    prev_status = str(before.status) if before else "offline"
    curr_status = str(after.status)

    if prev_status == "offline" and curr_status != "offline":
        for guild in bot.guilds:
            channel = guild.system_channel
            
            if channel is None or not channel.permissions_for(guild.me).send_messages:
                for c in guild.text_channels:
                    if c.permissions_for(guild.me).send_messages:
                        channel = c
                        break
            
            if channel:
                await channel.send("# THE PRESIDENT HAS RETURNED, EVERYONE ACT BUSY #")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
