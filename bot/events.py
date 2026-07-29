import re
import discord
from bot import bot
from .redeem import use_codes
from .tasks import check_guesswho, event_reminder
from .custom_logging import log_event

def check_startup_permissions():
    required_permissions = [
        ("view_channel", "View Channels"),
        ("send_messages", "Send Messages"),
        ("embed_links", "Embed Links"),
        ("read_message_history", "Read Message History"),
        ("create_public_threads", "Create Public Threads"),
        ("send_messages_in_threads", "Send Messages in Threads"),
        ("manage_threads", "Manage Threads"),
        ("mention_everyone", "Mention Everyone"),
        ("view_guild_scheduled_events", "View Scheduled Events"),
    ]

    for guild in bot.guilds:
        member = guild.me or guild.get_member(bot.user.id)
        if not member:
            print(f"[STARTUP] Could not resolve bot member for guild '{guild.name}' ({guild.id}).")
            continue

        permissions = member.guild_permissions
        missing = [
            label for flag, label in required_permissions
            if getattr(permissions, flag, None) is False
        ]

        if missing:
            print(
                f"[STARTUP] Missing permissions in '{guild.name}' ({guild.id}): "
                f"{', '.join(missing)}"
            )
        else:
            print(f"[STARTUP] Permissions OK in '{guild.name}' ({guild.id}).")


async def sync_commands_to_all_guilds():
    await bot.wait_until_ready()

    for g in bot.guilds:
        guild_obj = discord.Object(id=g.id)
        bot.tree.copy_global_to(guild=guild_obj)

        try:
            await bot.tree.sync(guild=guild_obj)
            print(f"[SYNC] Synced commands to: {g.name} ({g.id})")
        except discord.Forbidden:
            print(f"[SYNC] Missing permissions in: {g.name} ({g.id})")
        except discord.HTTPException as e:
            print(f"[SYNC] Failed for {g.name} ({g.id}): {e}")

async def setup_hook():
    bot.loop.create_task(sync_commands_to_all_guilds())
    
bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Whiteout Survival"), status=discord.Status.online)
    check_startup_permissions()
    check_guesswho.start()
    event_reminder.start()

    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    print(f'Message from {message.author}: {message.content}')
    pattern = r'📌 Code: (.*?)\s+⏰Valid Until:'
    match = re.search(pattern, message.content)
    if match:
        code = match.group(1)
        print("Found Code:", code)
        ctx = await bot.get_context(message)
        await use_codes(ctx, code)
    else:
        print("No code found")
    await bot.process_commands(message)


@bot.event
async def on_scheduled_event_update(before, after):
    event_id = after.id
    old_start_time = before.start_time
    old_name = before.name
    new_start_time = after.start_time
    new_name = after.name

    if old_start_time != new_start_time or old_name != new_name:
        print(f'[DEBUG] Event {old_name} changed. New Details: Name: {new_name}, Time: {new_start_time}')
        await log_event("EVENT_UPDATE", old_name = old_name, new_name = new_name, old_time= old_start_time, new_time = new_start_time)