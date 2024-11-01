import os
import json
import discord
import httpx
from discord import app_commands
from discord.ext import commands
from bot import bot, allowed_roles
from .wos_api import get_playerdata
from .custom_logging import log_commands, log_event
from .ui import PlayerActionView

async def load_player_data(file_name):
    file_path = os.path.join("/home/container", file_name)
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File '{file_name}' not found")
        return {}
    except Exception as e:
        print(f"Error on loading '{file_name}': {e}")
        return {}

async def save_player_data(file_name, data):
    file_path = os.path.join("/home/container", file_name)
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Error on saving '{file_name}': {e}")

async def get_player_choices(interaction: discord.Interaction, current: str):
    player_data = await load_player_data('players.json')
    choices = [
        app_commands.Choice(name=f"{name} (ID: {pid})", value=pid)
        for pid, name in player_data.items() if current.lower() in name.lower() or current in pid
    ]
    return choices[:25]  


@bot.tree.command(name="add_id", description="Adds a player ID. Usage: /add_id <player_id>")
async def add_id(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()
    await log_commands(interaction, player_id=player_id)
    player_data = await load_player_data('players.json')

    try:
        if player_id in player_data:
            player_name = player_data[player_id]
            await interaction.followup.send(f'Player ID {player_id} already exists with name **{player_name}**.')
        else:
            async with httpx.AsyncClient() as client:
                playerdata = await get_playerdata(player_id, client)

            if playerdata:
                player_name = playerdata.get("nickname")
                avatar_image = playerdata.get("avatar_image")
                stove_lv_content = playerdata.get("stove_lv_content")
                player_data[player_id] = player_name
                await save_player_data('players.json', player_data)

                embed = discord.Embed(title="", color=discord.Color.blue())
                embed.set_author(name=player_name, icon_url=stove_lv_content) 
                embed.add_field(name="Player-ID", value=player_id, inline=False)
                embed.set_thumbnail(url=avatar_image)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f'Player ID {player_id} is not valid.')
    except Exception as e:
        await interaction.followup.send(f'Something went wrong. Please try again later')
        await log_commands(e)



@bot.tree.command(name="remove_id", description="Removes player IDs. R4+ only. Usage: /remove_id <player_id, player_id>")
@app_commands.checks.has_any_role(*allowed_roles)
async def remove_id(interaction: discord.Interaction, player_ids: str):
    await log_commands(interaction, player_id=player_ids)
    player_ids = [pid.strip() for pid in player_ids.split(",")]

    player_data = await load_player_data('players.json')

    removed_players = []
    non_existent_ids = []

    for player_id in player_ids:
        if player_id not in player_data:
            non_existent_ids.append(player_id)
        else:
            player_name = player_data[player_id]
            del player_data[player_id]
            removed_players.append((player_id, player_name))

    await save_player_data('players.json', player_data)

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

@remove_id.error
async def remove_id_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("Sorry, you are not allowed to do this")


@bot.tree.command(name="list_ids", description="Lists all player IDs and names.")
async def list_ids(interaction: discord.Interaction):
    await log_commands(interaction)
    player_data = await load_player_data('players.json')
    
    if player_data:

        thread = await interaction.channel.create_thread(name="Player List", auto_archive_duration=60, type=discord.ChannelType.public_thread)
        thread_url = f"https://discord.com/channels/{interaction.guild.id}/{thread.id}"
        await interaction.response.send_message(f"IDs will be listed in this [thread]({thread_url}).")
        embeds = []
        embed = discord.Embed(title="Current Player IDs and Names", color=discord.Color.blue())
        field_count = 0

        for i, (player_id, player_name) in enumerate(player_data.items(), 1):
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
    stove_lv = player_data.get("stove_lv", "Unknown")

    embed = discord.Embed(title="", color=discord.Color.blue())
    embed.set_author(name=nickname, icon_url=stove_lv_content) 
    embed.add_field(name="Player-ID", value=player_id, inline=False)
    embed.add_field(name="Furnance-Level", value=stove_lv)
    embed.set_thumbnail(url=avatar_image)

    await interaction.followup.send(embed=embed)

async def update_player_data(player_id=None, player_name=None, player_data=None):
    updated_players = []
    pending_players = []
    updated_data = {}

    if player_data is None:
        try:
            player_data = await load_player_data('players.json')
        except FileNotFoundError:
            return [], []

        async with httpx.AsyncClient() as client:
            for player_id, old_name in player_data.items():
                try:
                    api_data = await get_playerdata(player_id, client)
                    if api_data:
                        new_name = api_data.get("nickname")
                        
                        if new_name and new_name != old_name:
                            updated_players.append((player_id, old_name, new_name))
                            updated_data[player_id] = new_name
                            await log_event('Player Name Updated', player_id=player_id, old_name=old_name, new_name=new_name)
                        else:
                            updated_data[player_id] = old_name
                    else:
                        pending_players.append((player_id, old_name))
                        updated_data[player_id] = old_name
                        await log_event("Adding to pending players:", player_id=player_id)
                except Exception as e:
                    print(f"Error processing player ID {player_id}: {e}")
                    await log_event('Update Player Error', player_id=player_id, error=str(e))
                    continue
    else:
        try:
            old_data = await load_player_data('players.json')
        except FileNotFoundError:
            print("Error: players.json not found.")
            return [], []
        
        for player_id, new_name in player_data.items():
            old_name = old_data.get(player_id, None)
            try:
                if new_name and new_name != old_name:
                    updated_players.append((player_id, old_name, new_name))
                    updated_data[player_id] = new_name
                    await log_event('Player Name Updated', player_id=player_id, old_name=old_name, new_name=new_name)
                    print(f"Player {player_id} updated: {old_name} -> {new_name}")
                else:
                    updated_data[player_id] = old_name
            except Exception as e:
                print(f"Error processing player ID {player_id}: {e}")
                await log_event('Update Player Error', player_id=player_id, error=str(e))
                continue

    await save_player_data('players.json', updated_data)
    print(f'Updated players: {updated_players}\nPending players:{pending_players}')
    return updated_players, pending_players



@bot.tree.command(name="update_player", description="Updates all player data to ensure validity.")
@app_commands.checks.has_any_role(*allowed_roles)
async def update_players(interaction: discord.Interaction):
    await log_commands(interaction)
    try:
        await interaction.response.send_message("Updating players. This could take a while...", ephemeral=True)
        updated_players, invalid_players = await update_player_data()
        changes_summary = "Player data update completed.\n"

        if updated_players:
            changes_summary += "Updated players:\n"
            for player_id, old_name, new_name in updated_players:
                changes_summary += f"ID: {player_id}, Old Name: {old_name}, New Name: {new_name}\n"
                
        for player_id, player_name in invalid_players:
            view = PlayerActionView(player_id, player_name, 'players.json')
            message = await interaction.followup.send(
                f"ID: {player_id}, Name: {player_name}\nError on getting Playerdata. Player may not exist. What do you want to do?",
                view=view,
                ephemeral=False
            )
            
            await view.wait()
            
        if not updated_players and not invalid_players:
            changes_summary = "No changes detected."
        await interaction.followup.send(changes_summary)
        
    except Exception as e:
        await interaction.followup.send(f'Something went wrong while updating player data', ephemeral=True)
        await log_commands(e)
