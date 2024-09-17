import os
import json
import discord
from discord import app_commands
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

@bot.tree.command(name="add_id", description="Adds a player ID. Usage: /add_id <player_id>")
async def add_id(interaction: discord.Interaction, player_id: str):
    await interaction.response.defer()

    await log_commands(interaction)
    player_data = await load_player_data('players.json')

    try:
        if player_id in player_data:
            player_name = player_data[player_id]
            await interaction.followup.send(f'Player ID {player_id} already exists with name **{player_name}**.')
        else:
            is_valid, player_name = await is_valid_player_id(player_id)
            if is_valid:
                player_data[player_id] = player_name
                await save_player_data('players.json', player_data)
                await interaction.followup.send(f'Player ID {player_id} with name **{player_name}** added.')
            else:
                await interaction.followup.send(f'Player ID {player_id} is not valid.')
    except Exception as e:
        await interaction.followup.send(f'Something went wrong: {e}')

@bot.tree.command(name="remove_id", description="Removes player IDs. R4+ only. Usage: /remove_id <player_id, player_id>")
@app_commands.checks.has_any_role(*allowed_roles)
async def remove_id(interaction: discord.Interaction, player_ids: str):
    await log_commands(interaction)
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
        removed_msg = "\n".join([f"Player ID {player_id} with name {player_name} removed." for player_id, player_name in removed_players])
    
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
            await interaction.response.send_message(embed=embeds[0])
        else:
            await interaction.response.send_message(embed=embeds[0])
            for e in embeds[1:]:
                await interaction.followup.send(embed=e)
    else:
        await interaction.response.send_message("There are no player IDs in the database.")



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

class PlayerActionView(discord.ui.View):
    def __init__(self, player_id, player_name, file_name):
        super().__init__()
        self.player_id = player_id
        self.player_name = player_name
        self.file_name = file_name

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.remove_player(interaction, delete=True)

    @discord.ui.button(label="Keep", style=discord.ButtonStyle.success)
    async def retain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.remove_player(interaction, delete=False)

    async def remove_player(self, interaction: discord.Interaction, delete: bool):
        player_data = await load_player_data(self.file_name)
        if delete:
            if self.player_id in player_data:
                del player_data[self.player_id]
                await save_player_data(self.file_name, player_data)
                await interaction.response.send_message(f"Player {self.player_name} (ID: {self.player_id}) has been deleted.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Player {self.player_name} (ID: {self.player_id}) was not found.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Player {self.player_name} (ID: {self.player_id}) has been retained.", ephemeral=True)

        self.delete.disabled = True
        self.retain.disabled = True
        await interaction.message.edit(view=self)

@bot.tree.command(name="update_player", description="Updates all player data to ensure validity.")
@app_commands.checks.has_any_role(*allowed_roles)
async def update_players(interaction: discord.Interaction):
    await log_commands(interaction)
    try:
        await interaction.response.send_message("Updating players. This could take a while...", ephemeral=True)

        updated_players, invalid_players = await update_player_data('players.json')
        changes_summary = "Player data update completed.\n"

        if updated_players:
            changes_summary += "Updated players:\n"
            for player_id, old_name, new_name in updated_players:
                changes_summary += f"ID: {player_id}, Old Name: {old_name}, New Name: {new_name}\n"

        if invalid_players:
            changes_summary += "Error in proccess or unkown ID (pending review):\n"
            for player_id, player_name in invalid_players:
                await interaction.followup.send(f"ID: {player_id}, Name: {player_name}\nWhat do you want to do with this player?",
                                                view=PlayerActionView(player_id, player_name, 'players.json'))
        
        if not updated_players and not invalid_players:
            changes_summary = "No changes detected."

        await interaction.followup.send(changes_summary)

    except Exception as e:
        await interaction.followup.send(f'Something went wrong while updating player data', ephemeral=True)
        await log_commands(e)