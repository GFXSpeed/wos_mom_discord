import os
import sqlite3
from dotenv import load_dotenv, find_dotenv
from discord.ext import commands
from discord import Intents, app_commands
from . import custom_logging

load_dotenv(find_dotenv())
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
WHO_IS = int(os.getenv("WHO_IS_CHANNEL"))
ANNOUNCEMENT = int(os.getenv("ANNOUNCEMENT_CHANNEL"))
NEWS = int(os.getenv("NEWS_CHANNEL"))

DB_PATH = 'players.db'

intents = Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

allowed_roles = ["Admin", "R4", "R5"]

bot = commands.Bot(command_prefix="/", intents=intents)

def load_modules():
    from . import events, guesswho, player_management, user_commands, redeem, ui, wos_api 
    print("Modules loaded")

def initialize_database():
    if not os.path.isfile(DB_PATH):
        print("Database not found. Creating a new 'players.db'...")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                state INTEGER,
                furnance_level INTEGER,
                redeem BOOLEAN DEFAULT 0
            )
        ''')

        conn.commit()
        conn.close()
        print("'players.db' created successfully with the 'players' table.")
    else:
        print("'players.db' already exists.")

def run():
    initialize_database()
    load_modules()
    bot.run(TOKEN)
