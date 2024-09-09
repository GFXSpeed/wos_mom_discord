import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot import bot, WHO_IS
from .logging import log_commands

@bot.command(help="Send a picture in private so others can guess who you are. Usage: /guess <attach image>")
async def guess(ctx):
    await log_commands(ctx)
    if isinstance(ctx.channel, discord.DMChannel):
        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                if attachment.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif')):
                    channel = bot.get_channel(WHO_IS)
                    thread = await channel.create_thread(name = "Who is this?", type = discord.ChannelType.public_thread)
                    await thread.send(file = await attachment.to_file())
                    delete_date = thread.created_at + timedelta(weeks=1)
                    delete_date_str = delete_date.strftime("%d.%m.%Y at %H:%M UTC")
                    await thread.send(f'This thread will be deleted on {delete_date_str}.')
                    await ctx.send("Success!")
        else:
            await ctx.send("I couldnt find an image. Please try again")
    else:
        await ctx.reply("Watch out! This command only works in private chat. I deleted your message", delete_after = 5)
        await ctx.message.delete()

@bot.tree.command(name="guess", description="Send a picture anonymously. **CAN ONLY BE USED IN PRIVAT**. Usage: /guess <image>")
async def guess_slash(interaction: discord.Interaction):
    await interaction.response.send_message(f"This command can only be used in private chat. Send /guess <image>",ephemeral=True)
