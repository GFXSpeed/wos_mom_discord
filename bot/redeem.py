import discord
import httpx
import sqlite3
import asyncio
from typing import List, Tuple
from .wos_api import redeem_request, DEFAULT_STATE
from .custom_logging import log_redeem_attempt
from .giftcode_manager import record_giftcode_attempt, STATUS_EMOJI

DB_PATH = 'players.db'

# Statuses that need no retry
FINAL_STATUSES = ("SUCCESS", "ALREADY_RECEIVED", "REQUIREMENT", "USER_INVALID")
# Statuses that make the whole run pointless
STOP_STATUSES = {
    "EXPIRED": "Code is expired",
    "INVALID": "Invalid code entered",
    "CLAIM_LIMIT": "Code reached claim limit",
}


async def filter_players(code: str, player_ids: List[str] = None, force: bool = False) -> Tuple[List[Tuple[str, str, int]], int, int]:
    """Returns [(player_id, name, state)] still to process, plus original and skipped counts."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        if player_ids is None:
            cursor.execute("SELECT player_id, name, state FROM players WHERE redeem IS TRUE")
        else:
            placeholders = ",".join("?" * len(player_ids))
            cursor.execute(
                f"SELECT player_id, name, state FROM players WHERE player_id IN ({placeholders})",
                tuple(player_ids)
            )
        players = [(str(pid), name, state or DEFAULT_STATE) for pid, name, state in cursor.fetchall()]
        original_count = len(players)

        if force:
            print(f"[FORCE] Loaded {original_count} players; skipping disabled for code {code}.")
            return players, original_count, 0

        cursor.execute("""
            SELECT DISTINCT player_id
            FROM giftcode_attempts
            WHERE giftcode = ? AND status IN ('SUCCESS', 'ALREADY_RECEIVED')
        """, (code,))
        already_done = {str(row[0]) for row in cursor.fetchall()}

        remaining = [p for p in players if p[0] not in already_done]
        skipped_count = original_count - len(remaining)

        print(f"Loaded {original_count} players; skipped {skipped_count} who already redeemed {code}.")
        print(f"{len(remaining)} players remain to process.")
        return remaining, original_count, skipped_count

    except Exception as e:
        print(f"Error in filter_players: {e}")
        return [], 0, 0
    finally:
        conn.close()


async def use_codes(ctx, code: str, player_ids=None, force: bool = False):
    redeem_success = []
    redeem_failed = []
    already_received = []
    total_rounds = 0
    max_rounds = 5
    processed_count = 0
    stop_reason = None

    players, original_count, already_successful_count = await filter_players(code, player_ids, force=force)

    thread = await ctx.channel.create_thread(
        name=f'Code: {code}',
        auto_archive_duration=4320,
        type=discord.ChannelType.public_thread
    )
    playercount = len(players)
    if playercount == 0:
        await thread.send(f"All {original_count} players have already successfully redeemed code **{code}**! Nothing to do.")
        return

    init_message = f'Starting to redeem code **{code}** for {playercount} players.'
    if already_successful_count > 0:
        init_message += f' ({already_successful_count} players already successfully redeemed this code and were skipped.)'
    init_message += f' Approximate time: {(2 * playercount) / 60:.1f} minutes.'
    await thread.send(init_message)

    def create_progress_message(processed):
        progress = processed / playercount
        bar_length = 20
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        return (f"`{bar}` {processed}/{playercount} ({progress*100:.1f}%)\n\n"
                f"✅ Success: {len(redeem_success)} 🔄 Already Received: {len(already_received)} "
                f"❌ Failed: {len(redeem_failed)}")

    status_message = await thread.send(create_progress_message(0))

    async with httpx.AsyncClient() as client:
        pending = players.copy()

        while pending and total_rounds < max_rounds and not stop_reason:
            total_rounds += 1
            new_pending = []
            print(f"Starting round {total_rounds} with {len(pending)} pending players")

            for index, (pid, name, state) in enumerate(pending):
                processed_count += 1

                try:
                    status = await redeem_request(client, pid, state, code)
                except Exception as e:
                    print(f"Error claiming code for {pid}: {e}")
                    status = "ERROR"

                if status in STOP_STATUSES:
                    stop_reason = STOP_STATUSES[status]
                    for rest_pid, rest_name, _ in pending[index:]:
                        redeem_failed.append(rest_pid)
                        await log_redeem_attempt(rest_pid, rest_name, code, status)
                        await record_giftcode_attempt(rest_pid, rest_name, code, status)
                    print(f"{stop_reason} while processing {pid}, {name}")
                    await thread.send(f"⚠️ **Processing stopped - {stop_reason}**")
                    break

                if status in FINAL_STATUSES:
                    if status == "SUCCESS":
                        redeem_success.append(pid)
                    elif status == "ALREADY_RECEIVED":
                        already_received.append(pid)
                    else:
                        redeem_failed.append(pid)
                    await log_redeem_attempt(pid, name, code, status)
                    await record_giftcode_attempt(pid, name, code, status)
                    print(f"{status}: {pid}, {name}")
                else:
                    print(f"Retrying {pid}, {name} in next round (status {status})")
                    new_pending.append((pid, name, state))
                    if total_rounds == max_rounds:
                        redeem_failed.append(pid)
                        await record_giftcode_attempt(pid, name, code, "ERROR")

                if processed_count % 5 == 0:
                    await status_message.edit(content=create_progress_message(processed_count))

                await asyncio.sleep(1)

            print(f"Round {total_rounds} completed: {len(new_pending)} players remaining")
            pending = new_pending

        await status_message.edit(content=create_progress_message(processed_count))
        await send_summary(
            thread, code, playercount,
            len(redeem_success), len(already_received), len(redeem_failed),
            total_rounds, stop_reason
        )


async def send_summary(channel, code, playercount, redeemed, already_received, failed, rounds, stop_reason):
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
            if status != 'PENDING':
                status_text += f"{STATUS_EMOJI.get(status, '❓')} {status}: {count}\n"

        if status_text:
            embed.add_field(name="Detailled Status", value=status_text, inline=False)

    embed.set_footer(text=f"{stop_reason}. Exited early." if stop_reason else f"Rounds: {rounds}")
    await channel.send(embed=embed)

    await channel.send(f"💡 **Hint:** Use `/giftcode_status giftcode:{code}` for detailled statistics!")
    print("Done")
