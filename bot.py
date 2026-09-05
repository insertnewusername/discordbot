import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# 1. Web Server to Keep Render Happy
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

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
    # Sync slash commands with Discord when bot logs in
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        
    print(f"Logged in as {bot.user.name}")

# 3. Slash Command (/ping)
@bot.tree.command(name="ping", description="Check if the bot is online")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 The bot is live! ({latency}ms)")

# 4. Presence Listener
@bot.event
async def on_presence_update(before, after):
    if after.id != TARGET_USER_ID:
        return

    prev_status = str(before.status) if before else "offline"
    curr_status = str(after.status)

    if prev_status == "offline" and curr_status != "offline":
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="chat")
            
            if channel is None:
                channel = guild.system_channel
            
            if channel is None or not channel.permissions_for(guild.me).send_messages:
                for c in guild.text_channels:
                    if c.permissions_for(guild.me).send_messages:
                        channel = c
                        break
            
            if channel and channel.permissions_for(guild.me).send_messages:
                await channel.send("# THE PRESIDENT HAS RETURNED, EVERYONE ACT BUSY #")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
