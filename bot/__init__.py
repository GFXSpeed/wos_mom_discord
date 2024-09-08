import os
from dotenv import load_dotenv, find_dotenv
from discord.ext import commands
from discord import Intents

load_dotenv(find_dotenv())
TOKEN = os.getenv("REDEEM_TOKEN")
SELENIUM = os.getenv("SELENIUM_URL")
GUILD_ID = os.getenv("GUILD_ID")
WHO_IS = os.getenv("WHO_IS_CHANNEL")
ANNOUNCEMENT = os.getenv("ANNOUNCEMENT_CHANNEL")

intents = Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=commands.DefaultHelpCommand())

allowed_roles = ["Admin", "R4", "R5"]

def load_modules():
    from . import logging, user_commands, events, player_management, redeem, guesswho, tasks
    print("Module geladen")

def run():
    load_modules()
    bot.run(TOKEN)
