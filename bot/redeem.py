import discord
import httpx
import sqlite3
import asyncio
from datetime import datetime
from bot import bot
from typing import List, Tuple
from .wos_api import get_playerdata, encode_data
from .custom_logging import log_redeem_attempt
from .captcha import CaptchaSolver
from .giftcode_manager import record_giftcode_attempt

WOS_GIFTCODE_URL = 'https://wos-giftcode-api.centurygame.com/api/gift_code'

async def claim_giftcode(player_id: str, giftcode: str, client: httpx.AsyncClient):
    solver = CaptchaSolver()
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
    if msg == "USED." and err == 40005:
        return "CLAIM_LIMIT", nickname
    if msg == "RECHARGE_MONEY ERROR." and err == 40017:
        return "REQUIREMENT", nickname
    if msg == "CAPTCHA CHECK ERROR." and err == 40103:
        return "CAPTCHA_ERROR", nickname
    return "ERROR", nickname

async def filter_players(code: str, player_ids: List[str] = None) -> Tuple[List[str], int, int]:
    """
    Returns:
      filtered_players: List of all player-ids that havent been processed
      original_count:   Count of all players
      skipped_count:    Count of skipped players
    """
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()

    try:
        if player_ids is None:
            cursor.execute("SELECT player_id FROM players WHERE redeem IS TRUE")
            player_ids = [str(row[0]) for row in cursor.fetchall()]

        original_count = len(player_ids)

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

async def use_codes(ctx, code: str, player_ids=None):
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
        player_ids, original_count, already_successful_count = await filter_players(code, player_ids)
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

                # Update progress message every 5 players or when status changes
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

                # Up to 3 captcha attempts
                for attempt in range(3):
                    try:
                        status, _ = await claim_giftcode(pid, code, client)
                        print(f"Attempt {attempt + 1} for {pid}: {status}")

                        # Check for specific status results
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
                            redeem_failed.extend(pending_ids)  # Add all remaining players to failed list
                            # Set expired status for all remaining players
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
                            # No database entry or logging for invalid codes
                            print(f"Code invalid: {pid}, {nickname}, {code}")
                            await log_redeem_attempt(remaining_pid, remaining_name, code, status)
                            await thread.send("⚠️ **Processing stopped - Invalid code entered**")
                            return

                        elif status == "CLAIM_LIMIT":
                            code_invalid = True
                            redeem_failed.extend(pending_ids)  # Add all remaining players to failed list
                            # Set claim limit status for all remaining players
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
                            if attempt == 2:  # 
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

            # Round End
            round_end_count = len(new_pending)
            print(f"Round {total_rounds} completed: {round_start_count - round_end_count} players processed, {round_end_count} remaining")
            pending_ids = new_pending

        # Calculate captcha success rate
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
    embed.add_field(name="Failed/Skipped", value=f"{failed} players", inline=True)
    
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
