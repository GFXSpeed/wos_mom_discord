import sqlite3
import discord
from datetime import datetime
from discord import app_commands
from bot import bot, allowed_roles
from .player_management import get_player_autocomplete
from .custom_logging import log_commands

DB_PATH = 'players.db'

async def get_giftcode_autocomplete(interaction: discord.Interaction, current: str):
    #Autocomplete for giftcodes
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT giftcode, MAX(attempt_time) as latest_attempt
            FROM giftcode_attempts 
            WHERE giftcode LIKE ?
            GROUP BY giftcode
            ORDER BY latest_attempt DESC
            LIMIT 25
        ''', (f'%{current}%',))
        
        results = cursor.fetchall()
        choices = [
            app_commands.Choice(name=giftcode[0], value=giftcode[0])
            for giftcode in results
        ]
        return choices
    except Exception as e:
        print(f"Error in giftcode autocomplete: {e}")
        return []
    finally:
        conn.close()

async def record_giftcode_attempt(player_id: str, player_name: str, giftcode: str, status: str):
    """
    Log giftcode attempts in the database.
    Possible status: SUCCESS, ALREADY_RECEIVED, EXPIRED, INVALID, CLAIM_LIMIT, REQUIREMENT, CAPTCHA_ERROR, ERROR, PENDING
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO giftcode_attempts 
            (player_id, giftcode, status, attempt_time, player_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (int(player_id), giftcode, status, datetime.now().isoformat(), player_name))
        conn.commit()
    except Exception as e:
        print(f"Error recording giftcode attempt: {e}")
    finally:
        conn.close()

async def get_giftcode_status(player_id: str = None, giftcode: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if player_id and giftcode:
            cursor.execute('''
                SELECT player_id, giftcode, status, attempt_time, player_name
                FROM giftcode_attempts 
                WHERE player_id = ? AND giftcode = ?
            ''', (int(player_id), giftcode))
        elif player_id:
            cursor.execute('''
                SELECT player_id, giftcode, status, attempt_time, player_name
                FROM giftcode_attempts 
                WHERE player_id = ?
                ORDER BY attempt_time DESC
            ''', (int(player_id),))
        elif giftcode:
            cursor.execute('''
                SELECT player_id, giftcode, status, attempt_time, player_name
                FROM giftcode_attempts 
                WHERE giftcode = ?
                ORDER BY attempt_time DESC
            ''', (giftcode,))
        else:
            cursor.execute('''
                SELECT player_id, giftcode, status, attempt_time, player_name
                FROM giftcode_attempts 
                ORDER BY attempt_time DESC
                LIMIT 100
            ''')
        
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting giftcode status: {e}")
        return []
    finally:
        conn.close()

async def get_giftcode_summary(giftcode: str):
    # Create summary for a specific giftcode
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM giftcode_attempts 
            WHERE giftcode = ?
            GROUP BY status
        ''', (giftcode,))
        
        status_counts = dict(cursor.fetchall())
        
        cursor.execute('''
            SELECT COUNT(*) as total_attempts
            FROM giftcode_attempts 
            WHERE giftcode = ?
        ''', (giftcode,))
        
        total_attempts = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) as total_players
            FROM players 
            WHERE redeem = 1
        ''')
        
        total_players = cursor.fetchone()[0]
        
        return {
            'status_counts': status_counts,
            'total_attempts': total_attempts,
            'total_players': total_players,
            'pending_players': total_players - total_attempts
        }
    except Exception as e:
        print(f"Error getting giftcode summary: {e}")
        return None
    finally:
        conn.close()

@bot.tree.command(name="giftcode_status", description="Show details of giftcode attempts.")
@app_commands.autocomplete(giftcode=get_giftcode_autocomplete, player_id=get_player_autocomplete)
@app_commands.describe(
    giftcode="Giftcode to check the status of",
    player_id="Player ID to check the status of (optional, if not provided, shows all attempts for the giftcode)"
)
async def giftcode_status(interaction: discord.Interaction, giftcode: str = None, player_id: str = None):
    await log_commands(interaction, giftcode=giftcode, player_id=player_id)
    await interaction.response.defer()
    
    if giftcode and not player_id:
        summary = await get_giftcode_summary(giftcode)
        if not summary:
            await interaction.followup.send(f"No stats found for `{giftcode}`.")
            return
        
        embed = discord.Embed(title=f"Giftcode Status: {giftcode}", color=discord.Color.blue())
        
        status_text = ""
        for status, count in summary['status_counts'].items():
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
            status_text += f"{emoji} {status}: {count}\n"
        
        embed.add_field(name="Status Overview", value=status_text, inline=False)
        embed.add_field(name="Total attempts", value=str(summary['total_attempts']), inline=True)
        embed.add_field(name="Total players", value=str(summary['total_players']), inline=True)
        embed.add_field(name="Pending players", value=str(summary['pending_players']), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    else:
        results = await get_giftcode_status(player_id, giftcode)

        if not results:
            search_desc = ""
            if player_id and giftcode:
                search_desc = f"Player `{player_id}` and giftcode `{giftcode}`"
            elif player_id:
                search_desc = f"Player `{player_id}`"
            elif giftcode:
                search_desc = f"Giftcode `{giftcode}`"
            else:
                search_desc = "the last attempts"

            await interaction.followup.send(f"No tries found for {search_desc}.")
            return

        in_dm = interaction.guild is None or isinstance(interaction.channel, discord.DMChannel)
        in_thread = isinstance(interaction.channel, discord.Thread)

        target = None

        if in_dm:
            # We're already in DMs: send details here
            target = interaction.channel
            await interaction.followup.send("Sending the detailed results here")
        elif in_thread:
            # Command used inside a thread: send details via DM to the user
            try:
                target = await interaction.user.create_dm()
                await interaction.followup.send("Sending you the results via DM.")
            except discord.Forbidden:
                await interaction.followup.send(
                    "I couldn't DM you the details (DMs are disabled). Please enable DMs or run the command in a normal channel."
                )
                return
        else:
            # Normal guild channel: create a thread and post details there
            try:
                thread = await interaction.channel.create_thread(
                    name="Giftcode Status Details",
                    auto_archive_duration=60,
                    type=discord.ChannelType.public_thread
                )
                target = thread
                thread_url = f"https://discord.com/channels/{interaction.guild.id}/{thread.id}"
                await interaction.followup.send(f"Detailed results will be in this [Thread]({thread_url}).")
            except discord.Forbidden:
                # fallback to DM if we lack permissions
                try:
                    target = await interaction.user.create_dm()
                    await interaction.followup.send(
                        "I'm unable to create a thread here (missing permissions). Sending you the details via DM."
                    )
                except discord.Forbidden:
                    await interaction.followup.send(
                        "I'm unable to create a thread here (missing permissions) and I can't DM you (Are your DMs disabled?)."
                    )
                    return
            except discord.HTTPException:
                # fallback to DM on thread creation failure
                try:
                    target = await interaction.user.create_dm()
                    await interaction.followup.send(
                        "Thread creation is not possible here. Sending you the details via DM."
                    )
                except discord.Forbidden:
                    await interaction.followup.send(
                        "Thread creation is not possible here and your DMs are disabled."
                    )
                    return

        embed = discord.Embed(title="Giftcode Attempt Details", color=discord.Color.blue())
        field_count = 0

        status_emoji = {
            'SUCCESS': '✅',
            'ALREADY_RECEIVED': '🔄',
            'EXPIRED': '⏰',
            'INVALID': '❌',
            'REQUIREMENT': '🤷‍♂️',
            'CLAIM_LIMIT': '🚫',
            'CAPTCHA_ERROR': '🔤',
            'ERROR': '⚠️',
            'PENDING': '⏳'
        }

        for result in results[:25]:
            player_id_val, giftcode_val, status, attempt_time, player_name = result
            emoji = status_emoji.get(status, '❓')

            try:
                dt = datetime.fromisoformat(attempt_time)
                time_str = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                time_str = attempt_time

            embed.add_field(
                name=f"{emoji} {player_name or 'Unknown'} (ID: {player_id_val})",
                value=f"Code: `{giftcode_val}`\nStatus: {status}\nTime: {time_str}",
                inline=True
            )
            field_count += 1

            if field_count == 25:
                await target.send(embed=embed)
                embed = discord.Embed(title="Giftcode Attempt Details (cont.)", color=discord.Color.blue())
                field_count = 0

        if field_count > 0:
            await target.send(embed=embed)

@bot.tree.command(name="giftcode_history", description="Show history of recent giftcodes. R4+ only.")
@app_commands.checks.has_any_role(*allowed_roles)
async def giftcode_history(interaction: discord.Interaction):
    await log_commands(interaction)
    await interaction.response.defer()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT giftcode, 
                   COUNT(*) as total_attempts,
                   SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
                   MIN(attempt_time) as first_attempt,
                   MAX(attempt_time) as last_attempt
            FROM giftcode_attempts 
            GROUP BY giftcode
            ORDER BY MAX(attempt_time) DESC
            LIMIT 20
        ''')
        
        results = cursor.fetchall()
        
        if not results:
            await interaction.followup.send("No history found.")
            return
        
        embed = discord.Embed(title="Giftcode History (latest 20)", color=discord.Color.green())
        
        for giftcode, total, successful, first_time, last_time in results:
            try:
                last_dt = datetime.fromisoformat(last_time)
                last_str = last_dt.strftime("%d.%m.%Y %H:%M")
            except:
                last_str = last_time
            
            success_rate = (successful / total * 100) if total > 0 else 0
            
            embed.add_field(
                name=f"📦 {giftcode}",
                value=f"Tries: {total}\n✅ Successfull: {successful} ({success_rate:.1f}%)\n⏰ Last try: {last_str}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"Error on getting giftcode history")
        print(e)
    finally:
        conn.close()
