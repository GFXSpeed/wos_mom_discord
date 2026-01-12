import discord
from discord import app_commands
from bot import bot

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    err = getattr(error, "original", error)

    if isinstance(err, app_commands.MissingAnyRole):
        roles = ", ".join(f"`{r}`" for r in err.missing_roles)
        msg = f"You are not allowed to use this command."
        print(f'[ERROR] Missing roles: {roles}')

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    if isinstance(err, app_commands.MissingPermissions):
        perms = ", ".join(err.missing_permissions)
        msg = f"You are missing permissions to use this command."
        print(f'[ERROR] Missing permissions: {perms}')
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    print(f"[APP_CMD_ERROR] {interaction.command} -> {repr(err)}")
    if not interaction.response.is_done():
        await interaction.response.send_message("Something went wrong", ephemeral=True)
