import os
from dotenv import load_dotenv, find_dotenv
from discord.ext import commands
from discord import Intents, app_commands

from . import custom_logging

load_dotenv(find_dotenv())
TOKEN = os.getenv("DISCORD_TOKEN")
SELENIUM = os.getenv("SELENIUM_URL")
GUILD_ID = int(os.getenv("GUILD_ID"))
WHO_IS = int(os.getenv("WHO_IS_CHANNEL"))
ANNOUNCEMENT = int(os.getenv("ANNOUNCEMENT_CHANNEL"))

intents = Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

allowed_roles = ["Admin", "R4", "R5"]

bot = commands.Bot(command_prefix="/", intents=intents)

def load_modules():
    from . import events, guesswho, player_management, user_commands, redeem, ui 
    print("Module geladen")

def run():
    load_modules()
    bot.run(TOKEN)
