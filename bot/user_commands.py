from discord import app_commands
from discord.ext import commands
from bot import bot, allowed_roles
from .logging import log_commands
from .redeem import use_codes

@bot.command(help="What this bot is about", category="General")
async def info(ctx):
    description = ("This bot monitors the gift code channel of the official WOS Discord server. "
                "If a gift code is found, it is automatically redeemed for all deposited players. "
                "If you find a new code on Facebook or elsewhere R4+ can use /code <code> to start manually. "
                "For an overview of all commands use !help")
    await log_commands(ctx)
    await ctx.send(description)


@bot.command(help="Starts process with manual giftcode. R4+ only. Usage: !code <code>", category="Giftcode")
@commands.has_any_role(*allowed_roles)
async def code(ctx, code: str):
    print(f'Starting with manual code {code}')
    await log_commands(ctx)
    await use_codes(ctx, code)
    
@code.error
async def code_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("Sorry, you are not allowed to do this")
