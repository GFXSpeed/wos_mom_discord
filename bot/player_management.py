import os
import asyncio
import sqlite3
import discord
import httpx
from discord import app_commands
from discord.ext import commands
from bot import bot, allowed_roles
from .wos_api import verify_player, DEFAULT_STATE
from .custom_logging import log_commands, log_event
from .ui import PlayerActionView

DB_PATH = 'players.db'

#################### HELPER FUNCTIONS ####################
async def format_furnance_level(level):
    if level is None:
        level = 0
    if not isinstance(level, int):
        return "Invalid Level"
    
    if level == 0:
        return "Unknown"  # not set - the API no longer reports levels
    if level <= 30:
        return f"Furnance-Level {level}"
    if 31 <= level <= 34:
        sub_level = level - 30
        return f"30-{sub_level}"
    
    # FC starting at lvl 35
    fc_level = (level - 35) // 5 + 1  # Main-FC-Level
    sub_level = (level - 35) % 5      # Sub-Levels
    return f"FC {fc_level}" if sub_level == 0 else f"FC {fc_level}-{sub_level}"

async def get_player_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete-Funktion für Spieler IDs"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT player_id, name FROM players
            WHERE name LIKE ? OR CAST(player_id AS TEXT) LIKE ?
            LIMIT 25
        ''', (f'%{current}%', f'%{current}%'))
        
        results = cursor.fetchall()
        choices = [
            app_commands.Choice(name=f"{name} (ID: {player_id})", value=str(player_id))
            for player_id, name in results
        ]
        return choices
    except Exception as e:
        print(f"Error in player autocomplete: {e}")
        return []
    finally:
        conn.close()

async def add_player(interaction: discord.Interaction, player_id: str, name: str, state: int, redeem: bool):
    """Shared body of /add_id and /watch. The API only accepts a player id together with its state."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
        result = cursor.fetchone()
        if result:
            await interaction.followup.send(f'Player ID {player_id} already exists with name **{result[0]}**.')
            return

        async with httpx.AsyncClient() as client:
            valid = await verify_player(client, player_id, state)

        if valid is False:
            await interaction.followup.send(f'Player ID {player_id} is not valid in state {state}.')
            return
        if valid is None:
            await interaction.followup.send('The gift code API is not responding. Please try again later.')
            return

        cursor.execute('''
            INSERT INTO players (player_id, name, state, furnance_level, redeem)
            VALUES (?, ?, ?, ?, ?)
        ''', (int(player_id), name, state, 0, redeem))
        conn.commit()

        embed = discord.Embed(title="", color=discord.Color.blue())
        embed.set_author(name=name)
        embed.add_field(name="Player-ID", value=player_id, inline=False)
        embed.add_field(name="State", value=str(state))
        embed.add_field(name="Status", value="Active" if redeem else "Watchlist")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send('Something went wrong. Please try again later.')
        await log_event('Add Player Error', player_id=player_id, error=str(e))
    finally:
        conn.close()


#################### COMMANDS ####################
@bot.tree.command(name="add_id", description="Adds a player. Tracks progress and claims giftcodes. Usage: /add_id <player_id> <name> [state]")
@app_commands.describe(name="In-game name", state="State the player is in")
async def add_id(interaction: discord.Interaction, player_id: str, name: str, state: int = DEFAULT_STATE):
    await interaction.response.defer()
    await log_commands(interaction, player_id=player_id, state=state)
    await add_player(interaction, player_id, name, state, redeem=True)


@bot.tree.command(name="watch", description="Track a players progress. Giftcodes will not be redeemed. Usage: /watch <player_id> <name> [state]")
@app_commands.describe(name="In-game name", state="State the player is in")
async def watch(interaction: discord.Interaction, player_id: str, name: str, state: int = DEFAULT_STATE):
    await interaction.response.defer()
    await log_commands(interaction, player_id=player_id, state=state)
    await add_player(interaction, player_id, name, state, redeem=False)


@bot.tree.command(name="remove_id", description="Removes player IDs. R4+ only. Usage: /remove_id <player_id> <player_id>")
@app_commands.checks.has_any_role(*allowed_roles)
async def remove_id(interaction: discord.Interaction, player_ids: str):
    await log_commands(interaction, player_id=player_ids)
    player_ids = [pid.strip() for pid in player_ids.split(",")]

    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()

    removed_players = []
    non_existent_ids = []

    for player_id in player_ids:
        cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
        result = cursor.fetchone()

        if result:
            player_name = result[0]
            cursor.execute("DELETE FROM players WHERE player_id = ?", (player_id,))
            removed_players.append((player_id, player_name))
        else:
            non_existent_ids.append(player_id)

    conn.commit()
    conn.close()

    removed_msg = ""
    non_existent_msg = ""

    if removed_players:
        removed_msg = "\n".join([f"ID {player_id}, name: {player_name}" for player_id, player_name in removed_players])
    
    if non_existent_ids:
        non_existent_msg = ", ".join(non_existent_ids)
    
    summary = ""
    if removed_msg:
        summary += f'The following players were removed:\n{removed_msg}\n'
    if non_existent_msg:
        summary += f'The following IDs do not exist: {non_existent_msg}'

    if summary:
        await interaction.response.send_message(summary)
    else:
        await interaction.response.send_message("No changes were made.")

    print(f"Removed players: {removed_players}, Non-existent IDs: {non_existent_ids}")


@bot.tree.command(name="list_ids", description="Lists all player IDs and names.")
async def list_ids(interaction: discord.Interaction):
    await log_commands(interaction)

    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name FROM players")
    player_data = cursor.fetchall()
    conn.close()

    if player_data:
        thread = await interaction.channel.create_thread(name="Player List", auto_archive_duration=60, type=discord.ChannelType.public_thread)
        thread_url = f"https://discord.com/channels/{interaction.guild.id}/{thread.id}"
        await interaction.response.send_message(f"IDs will be listed in this [thread]({thread_url}).")

        embeds = []
        embed = discord.Embed(title="Current Player IDs and Names", color=discord.Color.blue())
        field_count = 0

        for player_id, player_name in player_data:
            embed.add_field(name=f"ID: {player_id}", value=f"Name: {player_name}", inline=True)
            field_count += 1
            if field_count == 25:
                embeds.append(embed)
                embed = discord.Embed(title="Current Player IDs and Names (cont.)", color=discord.Color.blue())
                field_count = 0

        if len(embed.fields) > 0:
            embeds.append(embed)
        
        if len(embeds) == 1:
            await thread.send(embed=embeds[0])
        else:
            await thread.send(embed=embeds[0])
            for e in embeds[1:]:
                await thread.send(embed=e)
    else:
        await interaction.response.send_message("There are no player IDs in the database.")

@bot.tree.command(name="watchlist", description="Lists all players on our watchlist.")
async def list_ids(interaction: discord.Interaction):
    await log_commands(interaction)

    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name FROM players WHERE redeem IS FALSE")
    player_data = cursor.fetchall()
    conn.close()

    if player_data:
        thread = await interaction.channel.create_thread(name="MOMs Watchlist", auto_archive_duration=60, type=discord.ChannelType.public_thread)
        thread_url = f"https://discord.com/channels/{interaction.guild.id}/{thread.id}"
        await interaction.response.send_message(f"Watchlist will be in this [thread]({thread_url}).")

        embeds = []
        embed = discord.Embed(title="Current Player IDs and Names", color=discord.Color.blue())
        field_count = 0

        for player_id, player_name in player_data:
            embed.add_field(name=f"ID: {player_id}", value=f"Name: {player_name}", inline=True)
            field_count += 1
            if field_count == 25:
                embeds.append(embed)
                embed = discord.Embed(title="Current Player IDs and Names (cont.)", color=discord.Color.blue())
                field_count = 0

        if len(embed.fields) > 0:
            embeds.append(embed)
        
        if len(embeds) == 1:
            await thread.send(embed=embeds[0])
        else:
            await thread.send(embed=embeds[0])
            for e in embeds[1:]:
                await thread.send(embed=e)
    else:
        await interaction.response.send_message("There are no player IDs in the database.")


        
@bot.tree.command(name="details", description="Shows details of a player. Usage: /details <player_id> [state]")
@app_commands.autocomplete(player_id=get_player_autocomplete)
@app_commands.describe(state="Only needed for players that are not in the database")
async def details(interaction: discord.Interaction, player_id: str, state: int = None):
    await log_commands(interaction)
    await interaction.response.defer()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, state, furnance_level, redeem FROM players WHERE player_id = ?", (player_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        name, db_state, furnance_level, redeem_status = result
        state = state or db_state or DEFAULT_STATE
        status_text = "This player is in the database."
        status_text += " (Watchlist)" if redeem_status == 0 else " (Active)"
    else:
        name, furnance_level = "Unknown", 0
        state = state or DEFAULT_STATE
        status_text = f"This player is not in the database. Add with `/add_id {player_id} <name> {state}`."

    async with httpx.AsyncClient() as client:
        valid = await verify_player(client, player_id, state)
    validity = {True: "✅ accepted by the API", False: "❌ rejected by the API (wrong state or unknown ID)"}.get(valid, "❓ API did not respond")

    embed = discord.Embed(title="", color=discord.Color.blue())
    embed.set_author(name=name)
    embed.add_field(name="Player-ID", value=player_id, inline=False)
    embed.add_field(name="Furnance-Level", value=await format_furnance_level(furnance_level))
    embed.add_field(name="State", value=str(state))
    embed.add_field(name="ID + State", value=validity, inline=False)
    embed.add_field(name="Status", value=status_text, inline=False)

    view = PlayerActionView(player_id, name) if result else None
    await interaction.followup.send(embed=embed, view=view)


async def validate_players():
    """Check every stored id+state pair against the API. Returns the rejected ones."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name, state FROM players")
    players = cursor.fetchall()
    conn.close()

    invalid = []
    async with httpx.AsyncClient() as client:
        for player_id, name, state in players:
            valid = await verify_player(client, player_id, state or DEFAULT_STATE)
            if valid is False:
                invalid.append((player_id, name))
                await log_event("Player rejected by API", player_id=player_id, player_name=name, state=state)
            await asyncio.sleep(1)

    print(f'Invalid players: {invalid}')
    return invalid


@bot.tree.command(name="update_player", description="Updates a players data. R4+ only. Usage: /update_player <player_id> [name] [state] [level]")
@app_commands.autocomplete(player_id=get_player_autocomplete)
@app_commands.checks.has_any_role(*allowed_roles)
async def update_player(interaction: discord.Interaction, player_id: str, name: str = None, state: int = None, furnance_level: int = None):
    await log_commands(interaction, player_id=player_id)
    await interaction.response.defer()

    changes = {"name": name, "state": state, "furnance_level": furnance_level}
    changes = {column: value for column, value in changes.items() if value is not None}
    if not changes:
        await interaction.followup.send("Nothing to change. Provide a name, state or furnance level.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    assignments = ", ".join(f"{column} = ?" for column in changes)
    cursor.execute(f"UPDATE players SET {assignments} WHERE player_id = ?", (*changes.values(), player_id))
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if not updated:
        await interaction.followup.send(f"Player ID {player_id} is not in the database.")
        return

    await log_event('Player Data Updated', player_id=player_id, **changes)
    await interaction.followup.send(
        f"Updated player {player_id}: " + ", ".join(f"{column} -> {value}" for column, value in changes.items())
    )


@bot.tree.command(name="check_players", description="Checks all stored players against the API. R4+ only.")
@app_commands.checks.has_any_role(*allowed_roles)
async def check_players(interaction: discord.Interaction):
    await log_commands(interaction)
    await interaction.response.send_message("Checking players. This could take a while...", ephemeral=True)

    invalid = await validate_players()
    if not invalid:
        await interaction.followup.send("All players are valid.")
        return

    for player_id, name in invalid:
        view = PlayerActionView(player_id, name)
        await interaction.followup.send(
            f"ID: {player_id}, Name: {name}\nPlayer does not exist or is in another state. What do you want to do?",
            view=view
        )
        await view.wait()
