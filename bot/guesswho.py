import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from bot import bot, WHO_IS
from .logging import log_commands

@bot.tree.command(name="guess", description="**USE IN PRIVATE** Send a picture anonymously so others can guess who you are. Usage: /guess <image>")
@app_commands.describe(image="Attach an image (png, jpg, jpeg, gif)")
async def guess_slash(interaction: discord.Interaction, image: discord.Attachment):
    await log_commands(interaction)
    
    if isinstance(interaction.channel, discord.DMChannel):
        if image.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif')):
            channel = bot.get_channel(WHO_IS)
            thread = await channel.create_thread(name="Who is this?", type=discord.ChannelType.public_thread)
            await thread.send(file=await image.to_file())
            
            delete_date = thread.created_at + timedelta(weeks=1)
            delete_date_str = delete_date.strftime("%d.%m.%Y at %H:%M UTC")
            await thread.send(f'This thread will be deleted on {delete_date_str}.')
            
            await interaction.response.send_message("Success! See the thread for details.", ephemeral=True)
        else:
            await interaction.response.send_message("I couldn't find a valid image. Please try again.", ephemeral=True)
    else:
        await interaction.response.send_message("This command can only be used in private messages.", ephemeral=True)
