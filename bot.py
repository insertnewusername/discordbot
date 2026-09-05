import os
import re
import threading
import asyncio
from datetime import datetime, timezone, timedelta
from flask import Flask
import aiohttp
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

# 2. Discord Bot Setup & Helpers
TARGET_USER_ID = 1302824809167589386
last_seen_time = None  # Tracks when the target user went offline/online

def parse_time(time_str: str) -> timedelta:
    """Parses strings like 10m, 2h, 1d into timedelta objects."""
    match = re.match(r"^(\d+)([smhd])$", time_str.lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    units = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
    return timedelta(**{units[unit]: amount})

intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=".", 
    intents=intents, 
    status=discord.Status.online
)

@bot.event
async def on_ready():
    await asyncio.sleep(2)
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="for the President")
    )

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        
    print(f"Logged in as {bot.user.name}")

# 3. Message Activity Listener
@bot.event
async def on_message(message):
    global last_seen_time
    if message.author.id == TARGET_USER_ID:
        last_seen_time = datetime.now(timezone.utc)
    await bot.process_commands(message)

# 4. Utility & API Commands
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
    member = interaction.guild.get_member(TARGET_USER_ID) if interaction.guild else None
    
    if member and member.status not in (discord.Status.offline, discord.Status.invisible):
        await interaction.response.send_message(f"👑 <@{TARGET_USER_ID}> is currently **online** ({member.status})!")
    elif last_seen_time:
        timestamp = int(last_seen_time.timestamp())
        await interaction.response.send_message(f"👀 <@{TARGET_USER_ID}> was last active <t:{timestamp}:R>.")
    else:
        await interaction.response.send_message(f"No activity recorded for <@{TARGET_USER_ID}> since the bot restarted.")

@bot.tree.command(name="joke", description="Get a random joke")
async def joke(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://official-joke-api.appspot.com/random_joke") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await interaction.followup.send(f"😂 **{data['setup']}**\n||{data['punchline']}||")
                else:
                    await interaction.followup.send("Failed to fetch a joke right now.")
        except Exception:
            await interaction.followup.send("An error occurred while fetching the joke.")

@bot.tree.command(name="fact", description="Get a random useless fact")
async def fact(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await interaction.followup.send(f"💡 **Did you know?**\n{data['text']}")
                else:
                    await interaction.followup.send("Failed to fetch a fact right now.")
        except Exception:
            await interaction.followup.send("An error occurred while fetching the fact.")

@bot.tree.command(name="help", description="Display all available bot commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Available commands (supports both `/` and `.` prefix):",
        color=discord.Color.green()
    )
    embed.add_field(name="General", value="`/ping`, `/summon`, `/lastseen`, `/joke`, `/fact`", inline=False)
    embed.add_field(name="Moderation", value="`/kick <user> [reason]`\n`/ban <user> [reason]`\n`/timeout <user> <duration> [reason]`\n`/tempban <user> <duration> [reason]`", inline=False)
    await interaction.response.send_message(embed=embed)

# 5. Moderation Commands (Slash & Prefix)

# --- Kick ---
@bot.tree.command(name="kick", description="Kick a member from the server")
@discord.app_commands.checks.has_permissions(kick_members=True)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ **{member.display_name}** was kicked. | Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to kick user: {e}", ephemeral=True)

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def prefix_kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"✅ **{member.display_name}** was kicked. | Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to kick user: {e}")

# --- Ban ---
@bot.tree.command(name="ban", description="Ban a member from the server")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"⛔ **{member.display_name}** was banned. | Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to ban user: {e}", ephemeral=True)

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def prefix_ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"⛔ **{member.display_name}** was banned. | Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to ban user: {e}")

# --- Timeout ---
@bot.tree.command(name="timeout", description="Timeout a member (e.g., 10m, 1h, 1d)")
@discord.app_commands.checks.has_permissions(moderate_members=True)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    time_delta = parse_time(duration)
    if not time_delta:
        await interaction.response.send_message("❌ Invalid duration! Use format like `10m`, `2h`, or `1d`.", ephemeral=True)
        return
    try:
        await member.timeout(time_delta, reason=reason)
        await interaction.response.send_message(f"🤫 **{member.display_name}** timed out for {duration}. | Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to timeout user: {e}", ephemeral=True)

@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def prefix_timeout(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
    time_delta = parse_time(duration)
    if not time_delta:
        await ctx.send("❌ Invalid duration! Use format like `10m`, `2h`, or `1d`.")
        return
    try:
        await member.timeout(time_delta, reason=reason)
        await ctx.send(f"🤫 **{member.display_name}** timed out for {duration}. | Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to timeout user: {e}")

# --- Tempban ---
@bot.tree.command(name="tempban", description="Temporarily ban a member (e.g., 1d, 7d)")
@discord.app_commands.checks.has_permissions(ban_members=True)
async def slash_tempban(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    time_delta = parse_time(duration)
    if not time_delta:
        await interaction.response.send_message("❌ Invalid duration! Use format like `1d` or `7d`.", ephemeral=True)
        return
    try:
        await member.ban(reason=f"Tempban ({duration}) | {reason}")
        await interaction.response.send_message(f"⏳ **{member.display_name}** tempbanned for {duration}. | Reason: {reason}")
        await asyncio.sleep(time_delta.total_seconds())
        await interaction.guild.unban(member, reason="Tempban duration expired")
    except Exception as e:
        await interaction.response.send_message(f"❌ Tempban error: {e}", ephemeral=True)

@bot.command(name="tempban")
@commands.has_permissions(ban_members=True)
async def prefix_tempban(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
    time_delta = parse_time(duration)
    if not time_delta:
        await ctx.send("❌ Invalid duration! Use format like `1d` or `7d`.")
        return
    try:
        await member.ban(reason=f"Tempban ({duration}) | {reason}")
        await ctx.send(f"⏳ **{member.display_name}** tempbanned for {duration}. | Reason: {reason}")
        await asyncio.sleep(time_delta.total_seconds())
        await ctx.guild.unban(member, reason="Tempban duration expired")
    except Exception as e:
        await ctx.send(f"❌ Tempban error: {e}")

# 6. Presence Listener
@bot.event
async def on_presence_update(before, after):
    global last_seen_time

    if after.id != TARGET_USER_ID:
        return

    prev_status = str(before.status) if before else "offline"
    curr_status = str(after.status)

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
