import discord
import asyncio
from .logging import log_event
from discord.ext import tasks
from datetime import datetime, timedelta, timezone
from bot import bot, GUILD_ID, WHO_IS, ANNOUNCEMENT

@tasks.loop(minutes=60)
async def check_guesswho():
    print("Started check_guesswho loop")
    game_channel = bot.get_channel(WHO_IS)
    if game_channel is not None:
        threads = game_channel.threads
        for thread in threads:
            if thread.archived:
                continue
            if datetime.now(timezone.utc) - thread.created_at > timedelta(weeks=1):
                await thread.delete()
                await log_event("Thread deleted", created_on = thread.created_at)
                print(f'Thread {thread.name} was deleted.')
                
@check_guesswho.before_loop
async def before_check_threads():
    await bot.wait_until_ready()


tracked_events = set()
@tasks.loop(minutes=1)
async def event_reminder():
    guild = bot.get_guild(GUILD_ID)

    if guild: 
        events = await guild.fetch_scheduled_events()
        now = datetime.now(timezone.utc)
        current_event_ids = {event.id for event in events}

    if not events:
        print('[DEBUG] No Events found')
        return

    for event_id in list(tracked_events):
        if event_id not in current_event_ids:
            tracked_events.remove(event_id)
            print(f'[DEBUG] Event-ID {event_id} was deleted')

    for event in events: 
        start_time = event.start_time
        event_id = event.id
        event_name = event.name

        if start_time - timedelta(minutes=10) <= now < start_time:
            if event_id not in tracked_events:
                channel = bot.get_channel(ANNOUNCEMENT)
                await channel.send(f'@everyone Event **{event.name}** starts in 10 minutes!')
                tracked_events.add(event_id)

    next_event = min(
    (event for event in events if event.start_time > now),
    key = lambda e: e.start_time,
    default=None
    )

    if next_event:
        start_time = next_event.start_time
        event_id = next_event.id
        event_name = next_event.name
        print(f'[DEBUG] Next Event: {event_id}, {event_name} starts at: {start_time}')

@event_reminder.before_loop
async def before_event_reminder():
    await bot.wait_until_ready()