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


sent_reminders = {}
async def get_next_event():
    guild = bot.get_guild(GUILD_ID)

    try:
        events = await guild.fetch_scheduled_events()

    except discord.errors.DiscordServerError as e:
        print(f'Server Error on calling Event {e}. Retrying in 10 seconds')
        await asyncio.sleep(10)
        events = await guild.fetch_scheduled_events()

    if events:
        future_events = [event for event in events if event.start_time > datetime.now(timezone.utc)]
        
        if future_events:
            upcoming_event = min(future_events, key=lambda e: e.start_time)
            return upcoming_event
        else:
            print(f'Keine zukünftigen Events vorhanden.')
    
    return None

@tasks.loop(minutes=1)
async def check_event_reminder():
    now = datetime.now(timezone.utc)
    upcoming_event = await get_next_event()

    if upcoming_event:
        event_start_time = upcoming_event.start_time
        event_id = upcoming_event.id

        #print(f'[DEBUG] Zeit: {now}; Nächstes Event: {event_id}, {upcoming_event.name}: {event_start_time}')

        reminder_time = event_start_time - timedelta(minutes=10)

        if reminder_time <= now < event_start_time and not sent_reminders.get(event_id, False):
            channel = bot.get_channel(ANNOUNCEMENT)
            await channel.send(f'@everyone Event **{upcoming_event.name}** starts in 10 minutes!')

            sent_reminders[event_id] = True
        elif now > event_start_time:
            print(f'[DEBUG] Event **{upcoming_event.name}** already started.')
