import os
import re
import threading
import asyncio
from datetime import datetime, timezone, timedelta
from flask import Flask
import aiohttp
import discord
from discord.ext import commands
import asyncpg

# ==============================================================================
# 1. WEB SERVER TO KEEP HOSTING HEALTHY (e.g., Render/Heroku)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ==============================================================================
# 2. DISCORD BOT SETUP & HELPERS
# ==============================================================================
TARGET_USER_ID = 1302824809167589386
AUTHORIZED_ADMIN_ID = 1013741236261232720
DATABASE_URL = os.getenv("DATABASE_URL")  # Set this in your environment variables if using PostgreSQL

last_seen_time = None  # Tracks when target user was active

def parse_time(time_str: str) -> timedelta:
    """Parses standard duration strings like 10m, 2h, 1d into timedelta objects."""
    match = re.match(r"^(\d+)([smhd])$", time_str.lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    units = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
    return timedelta(**{units[unit]: amount})

class CustomBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_pool = None

    async def setup_hook(self):
        # Initialize PostgreSQL Database Pool if configured
        if DATABASE_URL:
            try:
                self.db_pool = await asyncpg.create_pool(DATABASE_URL)
                print("Database pool connected successfully.")
            except Exception as e:
                print(f"Failed to connect to database: {e}")

        # Sync Application Slash Commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash command(s).")
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")

intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.guilds = True
intents.message_content = True

bot = CustomBot(
    command_prefix=".",
    intents=intents,
    status=discord.Status.online
)

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name="for the President")
    )
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")

# ==============================================================================
# 3. MESSAGE & PRESENCE LISTENERS
# ==============================================================================
@bot.event
async def on_message(message):
    global last_seen_time

    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    # Check for target user activity
    if message.author.id == TARGET_USER_ID:
        last_seen_time = datetime.now(timezone.utc)

    # Forward direct messages sent to the bot to your DM
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id != AUTHORIZED_ADMIN_ID:
            try:
                admin_user = await bot.fetch_user(AUTHORIZED_ADMIN_ID)
                formatted_time = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                
                dm_notification = (
                    f"📩 **New Direct Message Received**\n"
                    f"👤 **From:** {message.author.name} (ID: `{message.author.id}`)\n"
                    f"🕒 **Time:** {formatted_time}\n"
                    f"💬 **Message:** {message.content}"
                )
                
                await admin_user.send(dm_notification)
            except Exception as e:
                print(f"Failed to forward DM to admin: {e}")

    await bot.process_commands(message)

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

# ==============================================================================
# 4. UTILITY & INFORMATIONAL COMMANDS
# ==============================================================================
@bot.tree.command(name="ping", description="Check if the bot is online and its latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 The bot is live! ({latency}ms)")

@bot.tree.command(name="summon", description="Summon the designated target user")
async def wake(interaction: discord.Interaction):
    await interaction.response.send_message(f"🚨 <@{TARGET_USER_ID}> You have been summoned!")

@bot.tree.command(name="lastseen", description="Check when the target user was last active")
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
        description="Available commands (supports both `/` slash and `.` prefix commands):",
        color=discord.Color.green()
    )
    embed.add_field(name="General", value="`/ping`, `/summon`, `/lastseen`, `/joke`, `/fact`", inline=False)
    embed.add_field(name="Moderation", value="`/kick <user> [reason]`\n`/ban <user> [reason]`\n`/timeout <user> <duration> [reason]`\n`/tempban <user> <duration> [reason]`", inline=False)
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# 5. ADMIN UTILITY COMMANDS (PREFIX)
# ==============================================================================
@bot.command(name="saychannel")
async def dm_say_channel(ctx, channel_id: int, *, message: str):
    if ctx.author.id != AUTHORIZED_ADMIN_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("This command can only be used in DMs.")
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            await ctx.send("❌ Channel not found or I do not have access to it.")
            return

    try:
        await channel.send(message)
        await ctx.send(f"✅ Message sent to **#{channel.name}** in **{channel.guild.name}**!")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to send messages in that channel.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="sayuser")
async def dm_say_user(ctx, user_id: int, *, message: str):
    if ctx.author.id != AUTHORIZED_ADMIN_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("This command can only be used in DMs.")
        return

    try:
        user = await bot.fetch_user(user_id)
        await user.send(message)
        await ctx.send(f"✅ Message sent to **{user.name}**!")
    except discord.Forbidden:
        await ctx.send("❌ Cannot DM that user. Their DMs might be closed or they don't share a server with me.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# ==============================================================================
# 6. MODERATION COMMANDS
# ==============================================================================

# --- KICK ---
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

# --- BAN ---
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

# --- TIMEOUT ---
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

# --- TEMPBAN ---
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

# ==============================================================================
# 7. RUN BOT
# ==============================================================================
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_BOT_TOKEN environment variable is missing.")
