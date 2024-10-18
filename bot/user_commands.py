import discord
from discord import app_commands
from bot import bot, allowed_roles
from .custom_logging import log_commands
from .redeem import use_codes

@bot.tree.command(name="info", description="What this bot is about")
async def info(interaction: discord.Interaction):
    description = ("This bot monitors the gift code channel of the official WOS Discord server. "
                "If a gift code is found, it is automatically redeemed for all deposited players. "
                "If you find a new code on Facebook or elsewhere R4+ can use /code <code> to start manually."
                "\n\nFor more information and to view the source code, visit the [GitHub repository](https://github.com/GFXSpeed/wos_mom_discord).")
    await log_commands(interaction)
    await interaction.response.send_message(description)


@bot.tree.command(name="code", description="Starts process with manual giftcode. R4+ only. Usage: /code <code>")
async def code(interaction: discord.Interaction, code: str):
    print(f'Starting with manual code {code}')
    await log_commands(interaction)
    await interaction.response.send_message(f"Processing started. See further details in the new thread.")
    await use_codes(interaction, code)
    

@code.error
async def code_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message("Sorry, you are not allowed to do this")
