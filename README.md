# wos_mom_discord
Bot running on Minions of Madness (MOM) Discord server

Welcome to wos_mom_discord, a Discord bot designed to enhance your server experience with a variety of fun and useful features. This bot is built to integrate seamlessly with your Discord server, providing automation, interaction, and entertainment.


## Requirements
- Python 3.11
- For Giftcode Redemption: Trained Keras Modell 

## Features
- Giftcode Redemption: Redeem giftcodes for multiple players using Centurygames-API. To keep things clean, a new thread will be created
- Automatic Redemption: Automatically redeem giftcodes if you have integrated the giftcode-channel of the official Whiteout Survival Discord
- Player Management: Manage players effectively using convenient Slash-Commands
- Event Reminders: Send reminders to players for upcoming events to keep everyone informed

## How to use
1. Fill .env-file with your API-Key and desired channel/guild-IDs
2. Edit "allowed_roles" in /bot/__init__.py according to your Discord-Roles (default is "Admin", "R4", "R5")
3. Start main.py
4. (Optional: Subscribe to offical WOS-Discord-Giftcode-Channel for automatic redeem)

## Available Commands
- /add_id - Adds a player ID. Player will recieve gifts and will be included in daily updates. Usage: `/add_id <player_id>`
- /watch - Same as add_id but players wont recieve gifts. `/watch <player_id>`
- /remove_id - Removes player IDs. (Allowed Roles only) Usage: `/remove_id <player_id, player_id>`
- /list_ids - Lists all player IDs and names. Usage: `/list_ids`
- /watchlist - Lists all player IDs and names on the watchlist. Usage: `/watchlist`
- /details - Shows details of a player. Usage: `/details <player_id>`
- /update_player - Updates all player data to ensure validity. (Allowed Roles only) Usage `/update_player`
- /info - Shows what this bot is about 
- /code - Starts process with manual giftcode. (Allowed Roles only). Usage: `/code <code>`
- /guess - **ONLY WORKS IF BOT IS DM'ed. Send a picture anonymously so others can guess who you are. Usage: `/guess <image>`

## Available Actions
- Automatic redemption of giftcodes officals pattern is recognized
- Event-Announcements. Send a reminder with `@everyone` 10 miuntes before your Discord-Events starts
- Daily updates. Playerdata will be updated every 24 hours. Updates will be sent to your news-channel

## Logging:
Logs of Bot, used commands, events and redeem-events can be found in ./logs Folder

## Preview
![Commands Preview](https://github.com/user-attachments/assets/61655145-b5e0-4cb6-9eab-a245a57ac84b)
![Redeem Preview](https://github.com/user-attachments/assets/70c70e58-e241-4813-b7c7-f984a9776f10)
![Various Commands Preview](https://github.com/user-attachments/assets/ccc4ad80-18cc-4c95-b297-bc07c0573edd)
![Update News Preview](https://github.com/user-attachments/assets/5a3263bd-919e-40e0-ab72-13ecd3d1d0cc)
![Event Announcement](https://github.com/user-attachments/assets/2b2ce1df-bc73-4345-9f8e-fd6888911b58)


## Contact
Feel free to reach out if you find bugs or have ideas for new features. Find me on discord: `gfxspeed` 
