import re
import discord
from bot import bot
from .redeem import use_codes
from .tasks import check_guesswho, check_event_reminder
from .logging import log_event

@bot.event
async def on_ready():
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game("Whiteout Survival"), status=discord.Status.online)
    check_guesswho.start()
    check_event_reminder.start()
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    print(f'Message from {message.author}: {message.content}')
    pattern = r'📌 Code: (.*?)\s+⏰Valid Until:'
    match = re.search(pattern, message.content)
    if match:
        code = match.group(1)
        print("Found Code:", code)
        ctx = await bot.get_context(message)
        await use_codes(ctx, code)
    else:
        print("No code found")
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    await log_event("ON_JOIN", new = member.name, id = member.id)
#    OLD_MOM_ID = 
#    OLD_MOM_DC = bot.get_guild(OLD_MOM_ID)
#
#    transfer_role = "R2/3"
#    OLD_MEMBER = OLD_MOM_DC.get_member(member.id)
#
#    if OLD_MEMBER:
#        role_to_assign = discord.utils.get(member.guild.roles, name = "R2/3")
#        if role_to_assign:
#            await member.add_roles(role_to_assign)
#            print(f'{member.name} got role {transfer_role}')
#            await log_event("SET_ROLE", member = member.name, role = {transfer_role})
#        else:
#            print(f'{member.name} is not on the old discord. Skipping')
