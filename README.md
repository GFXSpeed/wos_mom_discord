# wos_mom_discord
Bot running on Minions of Madness (MOM) Discord server

Welcome to wos_mom_discord, a Discord bot designed to enhance your server experience with a variety of fun and useful features. This bot is built to integrate seamlessly with your Discord server, providing automation, interaction, and entertainment.

## Features
- Giftcode Redemption: Redeem giftcodes for multiple players using Centurygames-API. To keep things clean, a new thread will be created
- Automatic Redemption: Automatically redeem giftcodes if you have integrated the giftcode-channel of the official Whiteout Survival Discord
- Player Management: Manage players effectively using convenient Slash-Commands
- Event Reminders: Send reminders to players for upcoming events to keep everyone informed

## How to use
1. Fill .env-file with your API-Key and desired channel/guild-IDs
2. Start main.py
3. (Optional: Subscribe to offical WOS-Discord-Giftcode-Channel for automatic redeem)

## Available Commands
- /add_id - Adds a player ID. Usage: `/add_id <player_id>`
- /remove_id - Removes player IDs. Usage: `/remove_id <player_id, player_id>`
- /list_ids - Lists all player IDs and names. Usage: `/list_ids`
- /details - Shows details of a player. Usage: `/details <player_id>`
- /update_player - Updates all player data to ensure validity. Usage `/update_player`
- /info - Shows what this bot is about 
- /code - Starts process with manual giftcode. R4+ only. Usage: `/code <code>`
- /guess - **ONLY WORKS IF BOT IS DM'ed. Send a picture anonymously so others can guess who you are. Usage: `/guess <image>`

## Available Actions
- Automatic redemption of giftcodes officals pattern is recognized
- Event-Announcements. Send a reminder with `@everyone` 10 miuntes before your Discord-Events starts

## Logging:
Logs of Bot, used commands, events and redeem-events can be found in ./logs Folder

## Preview
![Commands Preview](https://github.com/user-attachments/assets/61655145-b5e0-4cb6-9eab-a245a57ac84b)
![Redeem Preview](https://github.com/user-attachments/assets/70c70e58-e241-4813-b7c7-f984a9776f10)
![Various Commands Preview](https://github.com/user-attachments/assets/2d65336b-3429-42be-b96b-84c3c8338f43)


## Contact
Feel free to reach out if you find bugs or have ideas for new features. Find me on discord: `gfxspeed` 
