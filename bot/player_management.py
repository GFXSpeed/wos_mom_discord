import os
import json
import discord
from discord.ext import commands
from bot import bot, allowed_roles, SELENIUM
from .logging import log_commands

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

async def is_valid_player_id(player_id):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import NoSuchElementException
    import asyncio

    op = Options()
    op.add_argument("--disable-gpu")
    op.add_argument("--ignore-ssl-errors=yes")
    op.add_argument("--ignore-certificate-errors")

    driver = webdriver.Remote(command_executor=SELENIUM, options=op)
    try:
        driver.get("https://wos-giftcode.centurygame.com/")
        await asyncio.sleep(2)
        driver.find_element(By.XPATH, "//input[@placeholder='Player ID']").send_keys(player_id)
        driver.find_element(By.XPATH, "//*[@id='app']/div/div/div[3]/div[2]/div[1]/div[1]/div[2]/span").click()
        await asyncio.sleep(2)
        player_name = driver.find_element(By.XPATH, "/html/body/div/div/div/div[3]/div[2]/div[1]/div[1]/p[1]").text
        print(f'PlayerID {player_id} is: {player_name}')
        return True, player_name
    except NoSuchElementException:
        print(f'Invalid PlayerID: {player_id}')
        return False, None
    except Exception as e:
        print(f"Error: {e}")
        return False, None
    finally:
        driver.quit()

@bot.command(help="Adds a player ID. Usage: !add_id <player_id>", category="Player Management")
async def add_id(ctx, player_id: str):
    await log_commands(ctx, player_id=player_id)
    player_data = await load_player_data('players.json')
    try:
        if player_id in player_data:
            player_name = player_data[player_id]
            await ctx.send(f'Player ID {player_id} already exists with name **{player_name}**.')
        else:
            is_valid, player_name = await is_valid_player_id(player_id)
            if is_valid:
                player_data[player_id] = player_name
                await save_player_data('players.json', player_data)
                await ctx.send(f'Player ID {player_id} with name **{player_name}** added.')
            else:
                await ctx.send(f'Player ID {player_id} is not valid.')
    except Exception as e:
        await ctx.send(f'Something went wrong.')

@add_id.error
async def add_id_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("Sorry, you are not allowed to do this")

#@bot.command(help="Removes a player ID. R4+ only. Usage: !remove_id <player_id>", category="Player Management")
#@commands.has_any_role(*allowed_roles)
#async def remove_id(ctx, player_id: str):
#    await log_commands(ctx, removed_id=player_id)
#    player_data = await load_player_data('players.json')
#    if player_id not in player_data:
#        await ctx.send(f'Player ID {player_id} does not exist.')
#        print("Player does not exist")
#    else:
#        player_name = player_data[player_id]
#        del player_data[player_id]
#        await save_player_data('players.json', player_data)
#        await ctx.send(f'Player ID {player_id} with name {player_name} removed.')
#        print(f"Player {player_name} (ID: {player_id}) removed")

@bot.command(help="Removes a player ID. R4+ only. Usage: !remove_id <player_id>", category="Player Management")
@commands.has_any_role(*allowed_roles)
async def remove_id(ctx, *player_ids: str):
    await log_commands(ctx, removed_ids=player_ids)
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
    
    if removed_players:
        removed_msg = "\n".join([f"Player ID {player_id} with name {player_name} removed." for player_id, player_name in removed_players])
        await ctx.send(f'The following players were removed:\n{removed_msg}')
    
    if non_existent_ids:
        non_existent_msg = ", ".join(non_existent_ids)
        await ctx.send(f'The following IDs do not exist: {non_existent_msg}')
    
    print(f"Removed players: {removed_players}, Non-existent IDs: {non_existent_ids}")
    
@remove_id.error
async def remove_id_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("Sorry, you are not allowed to do this")

@bot.command(help="Lists all player IDs and names.", category="Player Management")
async def list_ids(ctx):
    await log_commands(ctx)
    player_data = await load_player_data('players.json')
    if player_data:
        embeds = []
        embed = discord.Embed(title="Current Player IDs and Names", color=discord.Color.blue())
        field_count = 0

        for i, (player_id, player_name) in enumerate(player_data.items(), 1):
            embed.add_field(name=f"ID: {player_id}", value=f"Name: {player_name}", inline=True)
            field_count += 1
            if field_count == 25:  # Discord-Limit for embeds
                embeds.append(embed)
                embed = discord.Embed(title="Current Player IDs and Names (cont.)", color=discord.Color.blue())
                field_count = 0
        
        if len(embed.fields) > 0:
            embeds.append(embed)
        
        for e in embeds:
            await ctx.send(embed=e)
    else:
        await ctx.send("There are no player IDs in the database.")


async def update_player_data(file_name):
    player_data = await load_player_data(file_name)
    if not player_data:
        return [], []

    updated_data = {}  
    removed_players = []
    updated_players = []

    for player_id, player_name in player_data.items():
        try:
            is_valid, new_name = await is_valid_player_id(player_id)
            if is_valid:
                if new_name != player_name:
                    updated_players.append((player_id, player_name, new_name))
                    updated_data[player_id] = new_name  
                else:
                    updated_data[player_id] = player_name
            else:
                removed_players.append(player_id)
        except Exception as e:
            print(f"Error processing player ID {player_id}: {e}")
            continue

    for player_id in removed_players:
        if player_id in updated_data:
            del updated_data[player_id]

    try:
        await save_player_data(file_name, updated_data)
    except Exception as e:
        print(f"Error saving updated player data")
        log_commands(e)

    return updated_players, removed_players

@bot.command(help="Updates all player data to ensure validity.", category="Player Management")
@commands.has_any_role(*allowed_roles)
async def update_players(ctx):
    await log_commands(ctx)
    try:
        await ctx.send("Updating players. This could take a while")
        updated_players, removed_players = await update_player_data('players.json')
        changes_summary = "Player data update completed.\n"

        
        if updated_players:
            changes_summary += "Updated players:\n"
            for player_id, old_name, new_name in updated_players:
                changes_summary += f"ID: {player_id}, Old Name: {old_name}, New Name: {new_name}\n"
        
        if removed_players:
            changes_summary += "Removed players:\n"
            for player_id in removed_players:
                changes_summary += f"ID: {player_id}\n"
        
        if not updated_players and not removed_players:
            changes_summary = "No changes detected."
        await ctx.send(changes_summary)

    except Exception as e:
        await ctx.send(f'Something went wrong while updating player data')
        await log_commands(e)

