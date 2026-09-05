import os
import discord
from discord.ext import commands

# The target user ID to watch for
TARGET_USER_ID = 1302824809167589386

# Set up required gateway intents
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user.name}")

@bot.event
async def on_presence_update(before, after):
    # Only track the target user
    if after.id != TARGET_USER_ID:
        return

    prev_status = str(before.status) if before else "offline"
    curr_status = str(after.status)

    # Check if user transitioned from offline to online/idle/dnd
    if prev_status == "offline" and curr_status != "offline":
        for guild in bot.guilds:
            channel = guild.system_channel
            
            # Fallback to the first writable text channel if system channel is unavailable
            if channel is None or not channel.permissions_for(guild.me).send_messages:
                for c in guild.text_channels:
                    if c.permissions_for(guild.me).send_messages:
                        channel = c
                        break
            
            if channel:
                await channel.send("# THE PRESIDENT HAS RETURNED, EVERYONE ACT BUSY #")

# Retrieves your bot token securely from Render's environment settings
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_BOT_TOKEN environment variable not set.")
