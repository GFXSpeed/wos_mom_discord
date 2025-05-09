import discord
import httpx
import sqlite3
from datetime import datetime
from bot import bot
from .wos_api import get_playerdata, encode_data
from .custom_logging import log_redeem_attempt
from .captcha import CaptchaSolver

WOS_GIFTCODE_URL = 'https://wos-giftcode-api.centurygame.com/api/gift_code'

async def claim_giftcode(player_id: str, giftcode: str):
    solver = CaptchaSolver()
    async with httpx.AsyncClient() as client:
        playerdata = await get_playerdata(player_id, client)
        if not playerdata:
            return "ERROR", None
        
        captcha_code = await solver.solve(player_id, client)

        payload = {
            "fid": player_id,
            "cdk": giftcode,
            "captcha_code": captcha_code,
            "time": str(int(datetime.now().timestamp()))
        }
        data = await encode_data(payload)
        response = await client.post(WOS_GIFTCODE_URL, data=data)

    if response.status_code != 200:
        return "ERROR", None

    obj = response.json()
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    msg = obj.get("msg")
    err = obj.get("err_code")
    nickname = obj.get("nickname")

    if msg == "SUCCESS":
        return "SUCCESS", nickname
    if msg == "RECEIVED." and err == 40008:
        return "ALREADY_RECEIVED", nickname
    if msg == "TIME ERROR." and err == 40007:
        return "EXPIRED", nickname
    if msg == "CDK NOT FOUND." and err == 40014:
        return "INVALID", nickname
    if msg == "CAPTCHA CHECK ERROR." and err == 40103:
        return "CAPTCHA_ERROR", nickname
    return "ERROR", nickname

async def use_codes(ctx, code: str, player_ids=None):
    redeem_success = []
    redeem_failed = []
    code_invalid = False
    code_expired = False
    total_rounds = 0
    max_rounds = 5
    captcha_solved = 0
    captcha_failed = 0

    # Load player IDs from database if not provided
    if player_ids is None:
        conn = sqlite3.connect('players.db')
        cursor = conn.cursor()
        cursor.execute("SELECT player_id FROM players WHERE redeem IS TRUE")
        player_ids = [str(row[0]) for row in cursor.fetchall()]
        conn.close()

    playercount = len(player_ids)
    thread = await ctx.channel.create_thread(
        name=f'Code: {code}',
        auto_archive_duration=4320,
        type=discord.ChannelType.public_thread
    )
    await thread.send(
        f'Starting to redeem code **{code}** for {playercount} players. '
        f'Approximate time: {(12 * playercount) / 60:.1f} minutes.'
    )

    pending_ids = player_ids.copy()
    # Main retry rounds
    while pending_ids and total_rounds < max_rounds and not (code_invalid or code_expired):
        total_rounds += 1
        new_pending = []
        for pid in pending_ids:
            # fetch player info
            try:
                playerdata = await get_playerdata(pid, httpx.AsyncClient())
            except Exception as e:
                print(f"Error fetching data for {pid}: {e}")
                new_pending.append(pid)
                continue
            if not playerdata:
                redeem_failed.append(pid)
                await log_redeem_attempt(pid, None, code, "ERROR")
                continue
            nickname = playerdata.get("nickname")

            # up to 3 captcha attempts
            solved = False
            for _ in range(3):
                try:
                    status, _ = await claim_giftcode(pid, code)
                except Exception as e:
                    print(f"Error in redeem for {pid}: {e}")
                    captcha_failed += 1
                    continue

                if status == "SUCCESS":
                    redeem_success.append(pid)
                    captcha_solved += 1
                    await log_redeem_attempt(pid, nickname, code, "SUCCESS")
                    print(f"Success: {pid}, {nickname}")
                    solved = True
                    break
                if status == "ALREADY_RECEIVED":
                    redeem_failed.append(pid)
                    captcha_solved += 1
                    await log_redeem_attempt(pid, nickname, code, "ALREADY_RECEIVED")
                    print(f"Already received: {pid}, {nickname}")
                    solved = True
                    break
                if status == "EXPIRED":
                    code_expired = True
                    await log_redeem_attempt(pid, nickname, code, "EXPIRED")
                    print(f"Code expired: {pid}, {nickname}, {code}")
                    solved = True
                    break
                if status == "INVALID":
                    code_invalid = True
                    await log_redeem_attempt(pid, nickname, code, "INVALID")
                    print(f"Code invalid: {pid}, {nickname}, {code}")
                    solved = True
                    break
                if status == "CAPTCHA_ERROR":
                    print(f"Captcha incorrect for {pid}, trying next/retry")
                    continue

                # captcha error
                captcha_failed += 1
            # end attempts

            if not solved:
                new_pending.append(pid)
        # end for
        pending_ids = new_pending

    # Calculate captcha success rate
    total_captcha = captcha_solved + captcha_failed
    captcha_rate = (captcha_solved / total_captcha * 100) if total_captcha else 0

    await send_summary(
        thread, code, playercount,
        len(redeem_success), len(redeem_failed),
        total_rounds, code_invalid, code_expired, captcha_rate
    )

async def send_summary(channel, code, playercount, redeemed, failed, rounds, invalid, expired, captcha_pct):
    embed = discord.Embed(title=f"Stats for giftcode: {code}")
    embed.add_field(name="Players in DB", value=str(playercount), inline=False)
    embed.add_field(name="Redeemed", value=f"{redeemed} players", inline=True)
    embed.add_field(name="Failed/Skipped", value=f"{failed} players", inline=True)
    footer = f"Rounds: {rounds}. Captcha success rate: {captcha_pct:.1f}%"
    if invalid:
        footer = "Code invalid. Exited early."
    elif expired:
        footer = "Code expired. Exited early."
    embed.set_footer(text=footer)
    await channel.send(embed=embed)
    print("Done")
