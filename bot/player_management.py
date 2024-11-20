import os
import sqlite3
import discord
import httpx
from discord import app_commands
from discord.ext import commands
from bot import bot, allowed_roles
from .wos_api import get_playerdata
from .custom_logging import log_commands, log_event
from .ui import PlayerActionView, PlayerDetailsView

#################### HELPER FUNCTIONS ####################
async def format_furnance_level(level):
    if level <= 30:
        return f"Furnance-Level {level}"
    elif 31 <= level <= 34:
        sub_level = level - 30
        return f"30-{sub_level}"
    else:
        # FC starting at lvl 35
        fc_level = (level - 35) // 5 + 1  # Main-FC-Level
        sub_level = (level - 35) % 5      # Sub-Levels
        return f"FC {fc_level}" if sub_level == 0 else f"FC {fc_level}-{sub_level}"

async def get_player_choices(interaction: discord.Interaction, current: str):
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()

    #get data of DB
    cursor.execute("""
        SELECT player_id, name FROM players
        WHERE name LIKE ? OR player_id LIKE ?
        LIMIT 25
    """, (f'%{current}%', f'%{current}%'))

    results = cursor.fetchall()
    conn.close()

    # Create choices for autocomplete 
    choices = [
        app_commands.Choice(name=f"{name} (ID: {player_id})", value=str(player_id))
        for player_id, name in results
    ]
    return choices

# Helper to update names during update process
async def update_player_in_db(player_id, name, state, furnance_level):
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET name = ?, state = ?, furnance_level = ? WHERE player_id = ?", (name, state, furnance_level, player_id))
    conn.commit()
    conn.close()

# Helper to get current name
async def get_name_from_db(player_id):
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None



#################### COMMANDS ####################
@bot.tree.command(name="add_id", description="Adds a player ID. Tracks progress and claims giftcodes. Usage: /add_id <player_id>")
async def add_id(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()
    await log_commands(interaction, player_id=player_id)

    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
        result = cursor.fetchone()

        if result:
            player_name = result[0]
            await interaction.followup.send(f'Player ID {player_id} already exists with name **{player_name}**.')
        else:
            async with httpx.AsyncClient() as client:
                playerdata = await get_playerdata(player_id, client)

            if playerdata:
                player_name = playerdata.get("nickname")
                avatar_image = playerdata.get("avatar_image")
                stove_lv_content = playerdata.get("stove_lv_content")

                cursor.execute('''
                    INSERT INTO players (player_id, name, state, furnance_level, redeem)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    int(player_id),
                    player_name,
                    playerdata.get("kid", 543),
                    playerdata.get("stove_lv", 1),
                    True  # True = Redeem, False = Only Watchlist
                ))
                conn.commit()

                
                embed = discord.Embed(title="", color=discord.Color.blue())
                if isinstance(stove_lv_content, str) and stove_lv_content.startswith(("http://", "https://")):
                    embed.set_author(name=player_name, icon_url=stove_lv_content)
                else:
                    embed.set_author(name=player_name) 
                embed.add_field(name="Player-ID", value=player_id, inline=False)
                embed.set_thumbnail(url=avatar_image)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f'Player ID {player_id} is not valid.')
    except Exception as e:
        await interaction.followup.send(f'Something went wrong. Please try again later.')
        await log_commands(e)
    finally:
        conn.close()

@bot.tree.command(name="watch", description="Track players progress. Giftcodes will not be redeemed. Usage: /watch <player_id>")
async def add_id(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()
    await log_commands(interaction, player_id=player_id)

    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM players WHERE player_id = ?", (player_id,))
        result = cursor.fetchone()

        if result:
            player_name = result[0]
            await interaction.followup.send(f'Player ID {player_id} already exists with name **{player_name}**.')
        else:
            async with httpx.AsyncClient() as client:
                playerdata = await get_playerdata(player_id, client)

            if playerdata:
                player_name = playerdata.get("nickname")
                avatar_image = playerdata.get("avatar_image")
                stove_lv_content = playerdata.get("stove_lv_content")

                cursor.execute('''
                    INSERT INTO players (player_id, name, state, furnance_level, redeem)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    int(player_id),
                    player_name,
                    playerdata.get("kid", 543),
                    playerdata.get("stove_lv", 1),
                    True  # True = Redeem, False = Only Watchlist
                ))
                conn.commit()

                
                embed = discord.Embed(title="", color=discord.Color.blue())
                if isinstance(stove_lv_content, str) and stove_lv_content.startswith(("http://", "https://")):
                    embed.set_author(name=player_name, icon_url=stove_lv_content)
                else:
                    embed.set_author(name=player_name)  
                embed.add_field(name="Player-ID", value=player_id, inline=False)
                embed.set_thumbnail(url=avatar_image)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f'Player ID {player_id} is not valid.')
    except Exception as e:
        await interaction.followup.send(f'Something went wrong. Please try again later.')
        await log_commands(e)
    finally:
        conn.close()

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


        
@bot.tree.command(name="details", description="Shows details of a player. Usage: /details <player_id>")
@app_commands.autocomplete(player_id=get_player_choices)
async def details(interaction: discord.Interaction, player_id: str):
    await log_commands(interaction)
    await interaction.response.defer()
    
    async with httpx.AsyncClient() as client:
        player_data = await get_playerdata(player_id, client)
    
    if player_data is None:
        await interaction.followup.send(f"Player ID {player_id} is not valid or could not be found.")
        return
    
    nickname = player_data.get("nickname", "Unknown")
    avatar_image = player_data.get("avatar_image")
    stove_lv_content = player_data.get("stove_lv_content")
    stove_lv = int(player_data.get("stove_lv", 0))
    formatted_stove_lv = await format_furnance_level(stove_lv)
    state = player_data.get("kid")

    # Check if player is already in db
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    cursor.execute("SELECT redeem FROM players WHERE player_id = ?", (player_id,))
    result = cursor.fetchone()
    player_exists = result is not None
    redeem_status = result[0] if result else None
    conn.close()

    embed = discord.Embed(title="", color=discord.Color.blue())
    if isinstance(stove_lv_content, str) and stove_lv_content.startswith(("http://", "https://")):
        embed.set_author(name=nickname, icon_url=stove_lv_content)
    else:
        embed.set_author(name=nickname)
    embed.add_field(name="Player-ID", value=player_id, inline=False)
    embed.add_field(name="Furnance-Level", value=formatted_stove_lv)
    embed.add_field(name="State", value=state)
    embed.set_thumbnail(url=avatar_image)

    if player_exists:
        status_text = "This player is already in the database."
        status_text += " (Watchlist)" if redeem_status == 0 else " (Active)"
    else:
        status_text = "This player is not in the database."

    embed.add_field(name="Status", value=status_text, inline=False)

    view = PlayerDetailsView(player_id, nickname, state, stove_lv, player_exists)
    await interaction.followup.send(embed=embed, view=view)

async def update_player_data(player_id=None, player_name=None, player_data=None):
    updated_players = []
    pending_players = []

    if player_data is None:
        conn = sqlite3.connect('players.db')
        cursor = conn.cursor()

        cursor.execute("SELECT player_id, name, state, furnance_level FROM players")
        player_data = {str(row[0]): {"name": row[1], "state": row[2], "furnance_level": row[3]} for row in cursor.fetchall()}
        conn.close()

        async with httpx.AsyncClient() as client:
            for player_id, old_data in player_data.items():
                old_name = old_data["name"]
                old_state = old_data["state"]
                old_furnance_level = old_data["furnance_level"]

                try:
                    api_data = await get_playerdata(player_id, client)
                    if api_data:
                        new_name = api_data.get("nickname")
                        new_state = api_data.get("kid")
                        new_furnance_level = api_data.get("stove_lv")

                        # Player in another state
                        if new_state != 543:
                            pending_players.append((player_id, old_name))
                            await log_event("Player outside state 543", player_id=player_id, player_name=new_name, state=new_state)
                            print(f"Player {player_id} is outside region 543 (region {new_state})")
                            continue

                        # Apply changes
                        if new_name != old_name or new_state != old_state or new_furnance_level != old_furnance_level:
                            updated_players.append({
                                "player_id": player_id,
                                "old_name": old_name,
                                "new_name": new_name if new_name != old_name else None,
                                "old_state": old_state,
                                "new_state": new_state if new_state != old_state else None,
                                "old_furnance_level": old_furnance_level,
                                "new_furnance_level": new_furnance_level if new_furnance_level != old_furnance_level else None
                            })
                            await update_player_in_db(player_id, new_name, new_state, new_furnance_level)
                            await log_event(
                                'Player Data Updated',
                                player_id=player_id,
                                old_name=old_name,
                                new_name=new_name if new_name != old_name else old_name,
                                old_state=old_state,
                                new_state=new_state if new_state != old_state else old_state,
                                old_furnance_level=old_furnance_level,
                                new_furnance_level=new_furnance_level if new_furnance_level != old_furnance_level else old_furnance_level
                            )
                except Exception as e:
                    print(f"Error processing player ID {player_id}: {e}")
                    await log_event('Update Player Error', player_id=player_id, error=str(e))
                    continue

    print(f'Updated players: {updated_players}\nPending players: {pending_players}')
    return updated_players, pending_players

@bot.tree.command(name="update_player", description="Updates all player data to ensure validity.")
@app_commands.checks.has_any_role(*allowed_roles)
async def update_players(interaction: discord.Interaction):
    await log_commands(interaction)
    try:
        await interaction.response.send_message("Updating players. This could take a while...", ephemeral=True)
        
        updated_players, pending_players = await update_player_data()
        changes_summary = "Player data update completed.\n"

        if updated_players:
            changes_summary += "Updated players:\n"
            for player in updated_players:
                player_id = player["player_id"]
                old_name = player["old_name"]
                new_name = player["new_name"] if player["new_name"] else old_name
                changes_summary += f"ID: {player_id}, Old Name: {old_name}, New Name: {new_name}\n"
                
                # Optional: Adding region and Furnance-Lvl
                if player["new_state"] is not None:
                    changes_summary += f"  - State: {player['old_state']} -> {player['new_state']}\n"
                if player["new_furnance_level"] is not None:
                    changes_summary += f"  - Furnance Level: {player['old_furnance_level']} -> {player['new_furnance_level']}\n"

        # Using Buttons to chose what to do with pending players
        for player_id, player_name in pending_players:
            view = PlayerActionView(player_id, player_name, 'players.db')
            message = await interaction.followup.send(
                f"ID: {player_id}, Name: {player_name}\nPlayer may not exist or is in another state. What do you want to do?",
                view=view,
                ephemeral=False
            )
            await view.wait()

        if not updated_players and not pending_players:
            changes_summary = "No changes detected."

        await interaction.followup.send(changes_summary)
        
    except Exception as e:
        await interaction.followup.send(f'Something went wrong while updating player data', ephemeral=True)
        await log_commands(f"Error: {e}")
