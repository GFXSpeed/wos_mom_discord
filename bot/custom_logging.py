import os
import logging

# Verzeichnis für Logs
log_directory = "./logs/"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Globale Logging-Konfiguration
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Funktion zur Erstellung eines Loggers mit spezifischem Namen und Datei
def create_logger(name, filename, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.FileHandler(os.path.join(log_directory, filename))
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)
    return logger

# Logger erstellen
general_logger = create_logger('general_logger', 'bot.log', logging.WARNING)
redeem_logger = create_logger('redeem_logger', 'giftcode_redeem.log')
commands_logger = create_logger('commands_logger', 'commands.log')
event_logger = create_logger('event_logger', 'events.log')

# Asynchrone Log-Funktionen
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
