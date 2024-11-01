import discord
from bot import bot

class PlayerActionView(discord.ui.View):
    def __init__(self, player_id, player_name, file_name):
        super().__init__(timeout=180)  #3 minutes to timeout
        self.player_id = player_id
        self.player_name = player_name
        self.file_name = file_name

    @discord.ui.button(label="Keep", style=discord.ButtonStyle.success)
    async def retain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_interaction(interaction, delete=False)
        
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_interaction(interaction, delete=True)

    async def handle_interaction(self, interaction: discord.Interaction, delete: bool):
        await interaction.response.defer()  # Defer response to avoid timeouts

        from .player_management import load_player_data, save_player_data
        player_data = await load_player_data(self.file_name)

        if delete:
            if self.player_id in player_data:
                del player_data[self.player_id]
                await save_player_data(self.file_name, player_data)
                response_text = f"Player {self.player_name} (ID: {self.player_id}) has been deleted."
            else:
                response_text = f"Player {self.player_name} (ID: {self.player_id}) was not found."
        else:
            response_text = f"Player {self.player_name} (ID: {self.player_id}) has been retained."

        self.delete.disabled = True
        self.retain.disabled = True
        await interaction.message.edit(content=response_text, view=self)
        self.stop()
