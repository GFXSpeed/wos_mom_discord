import discord
import httpx
import sqlite3
from datetime import datetime
from bot import bot
from .wos_api import get_playerdata, encode_data
from .player_management import update_player_data
from .custom_logging import log_redeem_attempt, log_event

WOS_GIFTCODE_URL = 'https://wos-giftcode-api.centurygame.com/api/gift_code'

async def claim_giftcode(player_id, giftcode):
    async with httpx.AsyncClient() as client:
        playerdata = await get_playerdata(player_id, client)
        
        if playerdata is None:
            return "ERROR", None

        data = await encode_data({
            "fid": player_id,
            "cdk": giftcode,
            "time": str(int(datetime.now().timestamp()))
        })
        player_name = playerdata.get("nickname")
        response = await client.post(WOS_GIFTCODE_URL, data=data)

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("msg") == "SUCCESS":
                return "SUCCESS", player_name
            elif response_data.get("msg") == "RECEIVED." and response_data.get("err_code") == 40008:
                return "ALREADY_RECEIVED", player_name
            elif response_data.get("msg") == "TIME ERROR." and response_data.get("err_code") == 40007:
                return "EXPIRED", player_name
            elif response_data.get("msg") == "CDK NOT FOUND." and response_data.get("err_code") == 40014:
                return "INVALID", player_name
            else:
                return "ERROR", player_name
        else:
            print(f"Error: Received status code {response.status_code}")
            return "ERROR", player_name


async def use_codes(ctx, code, player_ids=None):
    redeem_success = []
    redeem_failed = []
    code_invalid = False
    code_expired = False
    total_attempts = 0
    max_attempts = 5

    # Spieler-IDs aus der SQLite-Datenbank laden, falls keine spezifischen IDs übergeben wurden
    if player_ids is None:
        conn = sqlite3.connect('players.db')
        cursor = conn.cursor()
        cursor.execute("SELECT player_id FROM players WHERE redeem IS TRUE")
        player_ids = [str(row[0]) for row in cursor.fetchall()]
        conn.close()

    playercount = len(player_ids)
    thread = await ctx.channel.create_thread(name=f'Code: {code}', auto_archive_duration=4320, type=discord.ChannelType.public_thread)
    starting_info = f'Starting to redeem code **{code}** for {playercount} players. This could take up to {(12 * playercount) / 60:.1f} minutes'
    await thread.send(starting_info)

    while player_ids and total_attempts < max_attempts:
        total_attempts += 1
        failed_ids = []

        for pid in player_ids:
            try:
                response_status, player_name = await claim_giftcode(pid, code)

                if response_status == "SUCCESS":
                    print(f'Try no. {total_attempts}, ID: {pid}, Name: {player_name}, Result: SUCCESS')
                    await log_redeem_attempt(pid, player_name, code, "SUCCESS")
                    redeem_success.append(pid)
                elif response_status == "ALREADY_RECEIVED":
                    print(f'Try no. {total_attempts}, ID: {pid}, Name: {player_name}, Result: ALREADY CLAIMED')
                    redeem_failed.append(pid)
                elif response_status == "EXPIRED":
                    print(f'Code expired')
                    await log_redeem_attempt(pid, player_name, code, "EXPIRED")
                    code_expired = True
                    break
                elif response_status == "INVALID":
                    print(f'Code invalid')
                    await log_redeem_attempt(pid, player_name, code, "INVALID")
                    code_invalid = True
                    break
                else:
                    failed_ids.append(pid)
                    print(f'Try no. {total_attempts}, ID: {pid}, Name: {player_name}, Result: FAILED, adding to retry')
                    await log_redeem_attempt(pid, player_name, code, "ERROR")
            except Exception as e:
                print(e)
                failed_ids.append(pid)

        if not failed_ids:
            break
        player_ids = failed_ids.copy()
    

    await send_summary(thread, code, playercount, len(redeem_success), len(redeem_failed), total_attempts, code_invalid, code_expired)



async def send_summary(channel, code, playercount, redeem_success, redeem_failed, total_attempts, code_invalid, code_expired):
    embed = discord.Embed(title=f"Stats for giftcode: {code}")
    embed.add_field(name="Players in database", value=f"{playercount}", inline=False)
    embed.add_field(name="Successfully redeemed for", value=f"{redeem_success} players", inline=True)
    embed.add_field(name="Already used or failed for", value=f"{redeem_failed} players", inline=True)
    footer_text = f"Redeemed in {total_attempts} tries."
    if code_invalid:
        footer_text = "Code did not exist. Exited early."
    elif code_expired:
        footer_text = "Code expired. Exited early."
    embed.set_footer(text=footer_text)
    await channel.send(embed=embed)
    print("Done")
