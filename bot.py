import os
import threading
import asyncio
from datetime import datetime, timezone
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
last_seen_time = None  # Tracks when the target user went offline/online

intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.guilds = True

# Pass status=discord.Status.online right into the Bot initialization
bot = commands.Bot(
    command_prefix="!", 
    intents=intents, 
    status=discord.Status.online
)

@bot.event
async def on_ready():
    # Brief pause to let gateway connection settle fully
    await asyncio.sleep(2)

    # Re-enforce explicit online status with rich activity
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="for the President")
    )

    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        
    print(f"Logged in as {bot.user.name}")

# 3. Slash Commands
@bot.tree.command(name="ping", description="Check if the bot is online")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 The bot is live! ({latency}ms)")

@bot.tree.command(name="summon", description="Summon the President")
async def wake(interaction: discord.Interaction):
    await interaction.response.send_message(f"🚨 <@{TARGET_USER_ID}> You have been summoned!")

@bot.tree.command(name="lastseen", description="Check when the target user was last seen")
async def lastseen(interaction: discord.Interaction):
    global last_seen_time
    
    # Try fetching the user in the current guild to check live status
    member = interaction.guild.get_member(TARGET_USER_ID) if interaction.guild else None
    
    if member and member.status != discord.Status.offline:
        await interaction.response.send_message(f"👑 <@{TARGET_USER_ID}> is currently **online**!")
    elif last_seen_time:
        # Convert to Discord relative timestamp (<t:TIMESTAMP:R>)
        timestamp = int(last_seen_time.timestamp())
        await interaction.response.send_message(f"👀 <@{TARGET_USER_ID}> was last active <t:{timestamp}:R>.")
    else:
        await interaction.response.send_message(f"No activity recorded for <@{TARGET_USER_ID}> since the bot restarted.")

# 4. Presence Listener
@bot.event
async def on_presence_update(before, after):
    global last_seen_time

    if after.id != TARGET_USER_ID:
        return

    prev_status = str(before.status) if before else "offline"
    curr_status = str(after.status)

    # Update last seen timestamp whenever presence changes
    if curr_status != "offline":
        last_seen_time = datetime.now(timezone.utc)

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
