import discord
from bot import bot

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
        from .player_management import load_player_data, save_player_data
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