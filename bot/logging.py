import os
import logging

log_directory = "./logs/"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

general_handler = logging.FileHandler(os.path.join(log_directory, 'bot.log'))
general_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
logging.getLogger().addHandler(general_handler)

# Redeem Log
redeem_logger = logging.getLogger('redeem_logger')
redeem_logger.setLevel(logging.INFO)
redeem_handler = logging.FileHandler(os.path.join(log_directory, 'giftcode_redeem.log'))
redeem_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
redeem_logger.addHandler(redeem_handler)

# Commands Log
commands_logger = logging.getLogger('commands_logger')
commands_logger.setLevel(logging.INFO)
commands_handler = logging.FileHandler(os.path.join(log_directory, 'commands.log'))
commands_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
commands_logger.addHandler(commands_handler)

# Event Log
event_logger = logging.getLogger('event_logger')
event_logger.setLevel(logging.INFO)
event_handler = logging.FileHandler(os.path.join(log_directory, 'events.log'))
event_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
event_logger.addHandler(event_handler)

async def log_redeem_attempt(player_id, player_name, code, result):
    redeem_logger.info(f"Player ID: {player_id}, Player Name: {player_name}, Code: {code}, Result: {result}")

async def log_commands(interaction, **kwargs):
    extra_info = ' '.join([f'{key}={value}' for key, value in kwargs.items()])
    user = interaction.user
    command_name = interaction.command.name if hasattr(interaction, 'command') else 'Unknown Command'
    commands_logger.info(f"{user} (ID: {user.id}) has used {command_name} {extra_info}")

async def log_event(event, **kwargs):
    extra_info = ' '.join([f'{key}={value}' for key, value in kwargs.items()])
    event_logger.info(f"{event} triggered: {extra_info}")
