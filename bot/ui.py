import discord
import sqlite3

class PlayerActionView(discord.ui.View):
    def __init__(self, player_id, player_name):
        super().__init__(timeout=180)  # 3 minutes to timeout
        self.player_id = player_id
        self.player_name = player_name

    @discord.ui.button(label="Keep", style=discord.ButtonStyle.success)
    async def retain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_interaction(interaction, delete=False)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_interaction(interaction, delete=True)

    async def handle_interaction(self, interaction: discord.Interaction, delete: bool):
        await interaction.response.defer()  # Defer response to avoid timeouts

        response_text = ""
        
        conn = sqlite3.connect('players.db')
        cursor = conn.cursor()

        if delete:
            cursor.execute("DELETE FROM players WHERE player_id = ?", (self.player_id,))
            if cursor.rowcount > 0:
                response_text = f"Player {self.player_name} (ID: {self.player_id}) has been deleted."
            else:
                response_text = f"Player {self.player_name} (ID: {self.player_id}) was not found."
        else:
            response_text = f"Player {self.player_name} (ID: {self.player_id}) has been retained."

        conn.commit()
        conn.close()

        self.delete.disabled = True
        self.retain.disabled = True
        await interaction.message.edit(content=response_text, view=self)
        self.stop()
