import discord
import httpx
import sqlite3
import asyncio
from datetime import datetime
from bot import bot
from typing import List, Tuple
from .wos_api import get_playerdata, encode_data, WOS_HEADERS
from .custom_logging import log_redeem_attempt
from .captcha import CaptchaSolver
from .giftcode_manager import record_giftcode_attempt

WOS_GIFTCODE_URL = 'https://wos-giftcode-api.centurygame.com/api/gift_code'


async def claim_giftcode(player_id: str, giftcode: str, client: httpx.AsyncClient):
    solver = CaptchaSolver()
    playerdata = await get_playerdata(player_id, client)
    if not playerdata:
        return "ERROR"

    captcha_code = await solver.solve(player_id, client)

    payload = {
        "fid": player_id,
        "cdk": giftcode,
        "captcha_code": captcha_code,
        "time": str(int(datetime.now().timestamp()))
    }
    data = await encode_data(payload)
    response = await client.post(WOS_GIFTCODE_URL, headers=WOS_HEADERS, data=data)

    print(f"[GIFTCODE] player={player_id} code={giftcode} captcha={captcha_code}")
    print(f"[GIFTCODE] status_code={response.status_code}")
    print(f"[GIFTCODE] raw_response={response.text}")

    if response.status_code != 200:
        print(f"[GIFTCODE] Non-200 status for {player_id}: {response.status_code}")
        return "ERROR"

    obj = response.json()
    print(f"[GIFTCODE] parsed_json={obj}")

    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    msg = obj.get("msg")
    err = obj.get("err_code")

    print(f"[GIFTCODE] msg={msg!r} err_code={err!r}")

    if msg == "SUCCESS":
        return "SUCCESS"
    if msg == "RECEIVED." and err == 40008:
        return "ALREADY_RECEIVED"
    if msg == "TIME ERROR." and err == 40007:
        return "EXPIRED"
    if msg == "CDK NOT FOUND." and err == 40014:
        return "INVALID"
    if msg == "USED." and err == 40005:
        return "CLAIM_LIMIT"
    if msg == "RECHARGE_MONEY ERROR." and err == 40017:
        return "REQUIREMENT"
    if msg == "RECHARGE_MONEY_VIP ERROR." and err == 40018:
        return "REQUIREMENT"
    if msg == "CAPTCHA CHECK ERROR." and err == 40103:
        return "CAPTCHA_ERROR"

    print(f"[GIFTCODE] ⚠️ UNHANDLED CASE: msg={msg!r} err_code={err!r} full_obj={obj}")
    return "ERROR"

async def filter_players(code: str, player_ids: List[str] = None, force: bool = False) -> Tuple[List[str], int, int]:
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    try:
        if player_ids is None:
            cursor.execute("SELECT player_id FROM players WHERE redeem IS TRUE")
            player_ids = [str(row[0]) for row in cursor.fetchall()]

        original_count = len(player_ids)

        if force:
            print(f"[FORCE] Loaded {original_count} players; skipping disabled for code {code}.")
            return player_ids, original_count, 0

        cursor.execute("""
            SELECT DISTINCT player_id
            FROM giftcode_attempts
            WHERE giftcode = ? AND status IN ('SUCCESS', 'ALREADY_RECEIVED')
        """, (code,))
        successful_players = {str(row[0]) for row in cursor.fetchall()}

        filtered_players = [pid for pid in player_ids if pid not in successful_players]
        skipped_count = len(successful_players)

        print(f"Loaded {original_count} players; skipped {skipped_count} who already redeemed {code}.")
        print(f"{len(filtered_players)} players remain to process.")
        return filtered_players, original_count, skipped_count

    except Exception as e:
        print(f"Error in filter_players: {e}")
        return player_ids or [], len(player_ids or []), 0
    finally:
        conn.close()


async def use_codes(ctx, code: str, player_ids=None, force: bool = False):
    redeem_success = []
    redeem_failed = []
    already_received = []
    code_invalid = False
    code_expired = False
    total_rounds = 0
    max_rounds = 5
    captcha_solved = 0
    captcha_failed = 0
    processed_count = 0
    status_message = None

    async with httpx.AsyncClient() as client:

        player_ids, original_count, already_successful_count = await filter_players(code, player_ids, force=force)
        print(f"After filter_players: found {len(player_ids)} players")

        thread = await ctx.channel.create_thread(
            name=f'Code: {code}',
            auto_archive_duration=4320,
            type=discord.ChannelType.public_thread
        )
        playercount = len(player_ids)
        if playercount == 0:
            await thread.send(f"All {original_count} players have already successfully redeemed code **{code}**! Nothing to do.")
            return

        init_message = f'Starting to redeem code **{code}** for {playercount} players.'
        if already_successful_count > 0:
            init_message += f' ({already_successful_count} players already successfully redeemed this code and were skipped.)'
        init_message += f' Approximate time: {(12 * playercount) / 60:.1f} minutes.'
        await thread.send(init_message)

        def create_progress_message(processed, total, success, already_received, failed):
            progress = processed / total
            bar_length = 20
            filled = int(bar_length * progress)
            bar = "█" * filled + "░" * (bar_length - filled)
            return f"`{bar}` {processed}/{total} ({progress*100:.1f}%)\n\n✅ Success: {success} 🔄 Already Received: {already_received} ❌ Failed: {failed}"

        status_message = await thread.send(create_progress_message(0, playercount, 0, 0, 0))
        pending_ids = player_ids.copy()

        while pending_ids and total_rounds < max_rounds and not (code_invalid or code_expired):
            total_rounds += 1
            new_pending = []
            round_start_count = len(pending_ids)
            print(f"Starting round {total_rounds} with {round_start_count} pending players")

            for pid in pending_ids:
                processed_count += 1

                if processed_count % 5 == 0 or (
                    len(redeem_success) + len(already_received) + len(redeem_failed) > 0
                ):
                    await status_message.edit(content=create_progress_message(
                        processed_count,
                        playercount,
                        len(redeem_success),
                        len(already_received),
                        len(redeem_failed)
                    ))

                try:
                    playerdata = await get_playerdata(pid, client)
                    if not playerdata:
                        print(f"Could not get player data for {pid}")
                        new_pending.append(pid)
                        continue

                    nickname = playerdata.get("nickname")
                    await record_giftcode_attempt(pid, nickname, code, "PENDING")
                except Exception as e:
                    print(f"Error fetching data for {pid}: {e}")
                    new_pending.append(pid)
                    await asyncio.sleep(1)
                    continue

                print(f"Processing player {pid} ({nickname})")
                solved = False

                for attempt in range(3):
                    try:
                        status = await claim_giftcode(pid, code, client)

                        if status == "SUCCESS":
                            redeem_success.append(pid)
                            captcha_solved += 1
                            await log_redeem_attempt(pid, nickname, code, status)
                            await record_giftcode_attempt(pid, nickname, code, status)
                            print(f"Success: {pid}, {nickname}")
                            solved = True
                            break

                        elif status == "ALREADY_RECEIVED":
                            already_received.append(pid)
                            captcha_solved += 1
                            await log_redeem_attempt(pid, nickname, code, status)
                            await record_giftcode_attempt(pid, nickname, code, status)
                            print(f"Already received: {pid}, {nickname}")
                            solved = True
                            break

                        elif status == "REQUIREMENT":
                            redeem_failed.append(pid)
                            captcha_solved += 1
                            await log_redeem_attempt(pid, nickname, code, status)
                            await record_giftcode_attempt(pid, nickname, code, status)
                            print(f"Requirement error: {pid}, {nickname}")
                            solved = True
                            break

                        elif status == "EXPIRED":
                            code_expired = True
                            redeem_failed.extend(pending_ids)
                            for remaining_pid in pending_ids:
                                try:
                                    remaining_data = await get_playerdata(remaining_pid, client)
                                    if remaining_data:
                                        remaining_name = remaining_data.get("nickname")
                                        await log_redeem_attempt(remaining_pid, remaining_name, code, status)
                                        await record_giftcode_attempt(remaining_pid, remaining_name, code, status)
                                except Exception as e:
                                    print(f"Error setting expired status for {remaining_pid}: {e}")
                            print(f"Code expired while processing {pid}, {nickname}")
                            await thread.send("⚠️ **Processing stopped - Code is expired**")
                            return

                        elif status == "INVALID":
                            code_invalid = True
                            print(f"Code invalid: {pid}, {nickname}, {code}")
                            await log_redeem_attempt(pid, nickname, code, status)
                            await thread.send("⚠️ **Processing stopped - Invalid code entered**")
                            return

                        elif status == "CLAIM_LIMIT":
                            code_invalid = True
                            redeem_failed.extend(pending_ids)
                            for remaining_pid in pending_ids:
                                try:
                                    remaining_data = await get_playerdata(remaining_pid, client)
                                    if remaining_data:
                                        remaining_name = remaining_data.get("nickname")
                                        await log_redeem_attempt(remaining_pid, remaining_name, code, status)
                                        await record_giftcode_attempt(remaining_pid, remaining_name, code, status)
                                except Exception as e:
                                    print(f"Error setting claim limit status for {remaining_pid}: {e}")
                            print(f"Code claim limit reached while processing {pid}, {nickname}")
                            await thread.send("⚠️ **Processing stopped - Code reached claim limit**")
                            return

                        elif status == "CAPTCHA_ERROR":
                            print(f"Captcha incorrect for {pid}, trying next/retry")
                            captcha_failed += 1
                            if attempt == 2:
                                await record_giftcode_attempt(pid, nickname, code, status)
                            continue

                        else:
                            print(f"Unknown status '{status}' for {pid}")
                            captcha_failed += 1
                            if attempt == 2:
                                await record_giftcode_attempt(pid, nickname, code, "ERROR")
                            continue

                    except Exception as e:
                        print(f"Error in claim attempt {attempt + 1} for {pid}: {e}")
                        captcha_failed += 1
                        if attempt == 2:
                            await record_giftcode_attempt(pid, nickname, code, "ERROR")
                        await asyncio.sleep(1)
                        continue

                if not solved:
                    new_pending.append(pid)
                else:
                    current_success = len(redeem_success)
                    current_already_received = len(already_received)
                    current_failed = len(redeem_failed)
                    print(f"Current status: {current_success} successful, {current_failed} failed, {current_already_received} already received")
                    await status_message.edit(content=create_progress_message(
                        processed_count,
                        playercount,
                        current_success,
                        current_already_received,
                        current_failed,
                    ))

                await asyncio.sleep(1)

            if code_invalid or code_expired:
                print(f"Code marked as invalid/expired, stopping further processing")
                await thread.send("⚠️ **Processing stopped due to code being invalid or expired**")
                break

            round_end_count = len(new_pending)
            print(f"Round {total_rounds} completed: {round_start_count - round_end_count} players processed, {round_end_count} remaining")
            pending_ids = new_pending

        total_captcha = captcha_solved + captcha_failed
        captcha_rate = (captcha_solved / total_captcha * 100) if total_captcha else 0
        await send_summary(
            thread, code, playercount,
            len(redeem_success), len(already_received), len(redeem_failed),
            total_rounds, code_invalid, code_expired, captcha_rate
        )


async def send_summary(channel, code, playercount, redeemed, already_received, failed, rounds, invalid, expired, captcha_pct):
    from .giftcode_manager import get_giftcode_summary
    db_summary = await get_giftcode_summary(code)

    embed = discord.Embed(title=f"Stats for giftcode: {code}")
    embed.add_field(name="Players in DB", value=str(playercount), inline=False)
    embed.add_field(name="Redeemed", value=f"{redeemed} players", inline=True)
    embed.add_field(name="Already received", value=f"{already_received} players", inline=True)
    embed.add_field(name="Failed", value=f"{failed} players", inline=True)

    if db_summary:
        status_text = ""
        for status, count in db_summary['status_counts'].items():
            emoji = {
                'SUCCESS': '✅',
                'ALREADY_RECEIVED': '🔄',
                'EXPIRED': '⏰',
                'INVALID': '❌',
                'REQUIREMENT': '🤷‍♂️',
                'CLAIM_LIMIT': '🚫',
                'CAPTCHA_ERROR': '🔤',
                'ERROR': '⚠️',
                'PENDING': '⏳'
            }.get(status, '❓')
            if status != 'PENDING':
                status_text += f"{emoji} {status}: {count}\n"

        if status_text:
            embed.add_field(name="Detailled Status", value=status_text, inline=False)

    footer = f"Rounds: {rounds}. Captcha success rate: {captcha_pct:.1f}%"
    if invalid:
        footer = "Code invalid. Exited early."
    elif expired:
        footer = "Code expired. Exited early."
    embed.set_footer(text=footer)
    await channel.send(embed=embed)

    await channel.send(f"💡 **Hint:** Use `/giftcode_status giftcode:{code}` for detailled statistics!")
    print("Done")
