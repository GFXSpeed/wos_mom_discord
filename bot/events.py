import re
import discord
from bot import bot
from .redeem import use_codes
from .tasks import check_guesswho, event_reminder, scheduled_update
from .custom_logging import log_event

@bot.event
async def on_ready():
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game("Whiteout Survival"), status=discord.Status.online)
    check_guesswho.start()
    event_reminder.start()
    scheduled_update.start()

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