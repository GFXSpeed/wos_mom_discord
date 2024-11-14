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


class PlayerDetailsView(discord.ui.View):
    def __init__(self, player_id, player_name, state, stove_lv, player_exists):
        super().__init__(timeout=180)
        self.player_id = player_id
        self.player_name = player_name
        self.state = state
        self.stove_lv = stove_lv

        # Buttons deaktivieren, falls der Spieler bereits existiert
        if player_exists:
            self.add_to_database_button.disabled = True
            self.add_to_watchlist_button.disabled = True
        else:
            self.remove_player_button.disabled = True

    async def add_to_database(self, interaction: discord.Interaction, redeem: bool):
        conn = sqlite3.connect('players.db')
        cursor = conn.cursor()

        # Hinzufügen des Spielers zur Datenbank mit dem angegebenen `redeem`-Status
        cursor.execute('''
            INSERT OR REPLACE INTO players (player_id, name, state, furnance_level, redeem)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.player_id, self.player_name, self.state, self.stove_lv, redeem))

        conn.commit()
        conn.close()

        status = "Watchlist" if not redeem else "Database"
        await interaction.response.send_message(f"Player {self.player_name} (ID: {self.player_id}) has been added to the {status}.", ephemeral=True)
        await self.disable_buttons(interaction)

    @discord.ui.button(label="Add to Database", style=discord.ButtonStyle.success)
    async def add_to_database_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_database(interaction, redeem=True)

    @discord.ui.button(label="Add to Watchlist", style=discord.ButtonStyle.primary)
    async def add_to_watchlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_to_database(interaction, redeem=False)

    @discord.ui.button(label="Remove Player", style=discord.ButtonStyle.danger)
    async def remove_player_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('players.db')
        cursor = conn.cursor()

        cursor.execute('DELETE FROM players WHERE player_id = ?', (self.player_id,))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"Player {self.player_name} (ID: {self.player_id}) has been removed from the database.", ephemeral=True)
        await self.disable_buttons(interaction)

    async def disable_buttons(self, interaction: discord.Interaction):
        # Alle Buttons nach Klick deaktivieren
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)