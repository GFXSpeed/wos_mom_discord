import asyncio
import discord
from .custom_logging import log_event
from discord.ext import tasks
from datetime import datetime, timedelta, timezone
from bot import bot, GUILD_ID, WHO_IS, ANNOUNCEMENT, NEWS
from .player_management import update_player_data, format_furnance_level

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


@tasks.loop(hours=24)
async def scheduled_update():
    channel = bot.get_channel(NEWS)
    
    if not channel:
        print("Update channel not found.")
        return

    await log_event("STARTING DAILY PLAYER UPDATE")
    updated_players, pending_players = await update_player_data()

    if not updated_players and not pending_players:
        return 
    
    # Limit to 25 embed fields
    async def send_embed(embed, embed_list):
        if len(embed.fields) > 0:
            embed_list.append(embed)
        if len(embed_list) > 0:
            for e in embed_list:
                await channel.send(embed=e)

    name_embed = discord.Embed(title="Updated Player Names", color=discord.Color.blue())
    level_embed = discord.Embed(title="Updated Player Furnance Levels", color=discord.Color.green())
    region_embed = discord.Embed(title="Updated Player Regions", color=discord.Color.orange())
    pending_embed = discord.Embed(title="Pending Players (Errors or Outside Region 543)", color=discord.Color.red())

    name_embeds, level_embeds, region_embeds, pending_embeds = [], [], [], []

    for player in updated_players:
        player_id = player["player_id"]
        player_name = player["new_name"] or player["old_name"]

        old_furnance_level = await format_furnance_level(player["old_furnance_level"])
        new_furnance_level = await format_furnance_level(player["new_furnance_level"])

        if player["new_name"]:
            name_embed.add_field(
                name=f"ID: {player_id} - {player_name}",
                value=f"{player['old_name']} -> {player['new_name']}",
                inline=False
            )
            if len(name_embed.fields) >= 25:
                await send_embed(name_embed, name_embeds)
                name_embed = discord.Embed(title="Updated Player Names (cont.)", color=discord.Color.blue())

        if player["new_furnance_level"] is not None:
            level_embed.add_field(
                name=f"ID: {player_id} - {player_name}",
                value=f"{old_furnance_level} -> {new_furnance_level}",
                inline=False
            )
            if len(level_embed.fields) >= 25:
                await send_embed(level_embed, level_embeds)
                level_embed = discord.Embed(title="Updated Player Furnance Levels (cont.)", color=discord.Color.green())

        if player["new_state"] is not None:
            region_embed.add_field(
                name=f"ID: {player_id} - {player_name}",
                value=f"{player['old_state']} -> {player['new_state']}",
                inline=False
            )
            if len(region_embed.fields) >= 25:
                await send_embed(region_embed, region_embeds)
                region_embed = discord.Embed(title="Updated Player Regions (cont.)", color=discord.Color.orange())

    for player_id, player_name in pending_players:
        pending_embed.add_field(
            name=f"ID: {player_id} - {player_name}",
            value=f"Name: {player_name}",
            inline=False
        )
        if len(pending_embed.fields) >= 25:
            await send_embed(pending_embed, pending_embeds)
            pending_embed = discord.Embed(title="Pending Players (cont.)", color=discord.Color.red())

    await send_embed(name_embed, name_embeds)
    await send_embed(level_embed, level_embeds)
    await send_embed(region_embed, region_embeds)
    await send_embed(pending_embed, pending_embeds)


@scheduled_update.before_loop
async def before_event_reminder():
    await bot.wait_until_ready()

    