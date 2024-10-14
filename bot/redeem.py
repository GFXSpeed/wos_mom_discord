import time
import random
import asyncio
import logging
import discord
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from concurrent.futures import ThreadPoolExecutor
from .logging import log_redeem_attempt
from .player_management import load_player_data, update_player_data
from bot import bot, SELENIUM

# Selenium settings
op = Options()
op.add_argument("--disable-gpu")
op.add_argument("--ignore-ssl-errors=yes")
op.add_argument("--ignore-certificate-errors")

# Function to redeem code for 1 player id 
def redeem_code_for_player(code, pid):
    driver = webdriver.Remote(command_executor=SELENIUM, options=op)
    randomtime = random.uniform(1.0, 2.0)

    result = "Unknown error"
    player = "Unknown player"

    try:
        driver.get("https://wos-giftcode.centurygame.com/")
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Player ID']")))
        driver.find_element(By.XPATH, "//input[@placeholder='Player ID']").send_keys(pid)
        logging.info(f'Used PlayerID: {pid}')
        driver.find_element(By.XPATH, "//*[@id='app']/div/div/div[3]/div[2]/div[1]/div[1]/div[2]/span").click()
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.XPATH, "//*[@id='app']/div/div/div[3]/div[2]/div[1]/img")))
        player = driver.find_element(By.XPATH, "/html/body/div/div/div/div[3]/div[2]/div[1]/div[1]/p[1]").text
        logging.info(f'PlayerID is: {player}')
        time.sleep(randomtime)
        driver.find_element(By.XPATH, "//input[@placeholder='Enter Gift Code']").send_keys(code)
        logging.info(f'PID: {pid}, Player: {player}, Entered code')
        time.sleep(randomtime)
        driver.find_element(By.XPATH, "//*[@id='app']/div/div/div[3]/div[2]/div[3]").click()
        result = WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.XPATH, "//*[@id='app']/div/div[2]/div[2]/p"))).text

        logging.info(f'{player}s result {result}')
    except NoSuchElementException:
        result = "Element not found"
    except Exception as e:
        result = f'Error: {str(e)}'   
    finally:
        time.sleep(2)
        driver.quit()
    return result, player

class RedeemStatus:
    def __init__(self):
        self.redeem_success = 0
        self.redeem_failed = 0
        self.code_invalid = False
        self.code_expired = False
        self.retry_ids = []
        self.update_player = {}

#worker to redeem ids in multiple instances
async def redeem_worker(queue, executor, loop, code, status):
    while True:
        pid = await queue.get()
        if pid is None:
            print('Worker received stop signal, terminating.')
            queue.task_done()
            break
        result, player = await loop.run_in_executor(executor, redeem_code_for_player, code, pid)
        try:
            status.update_player[pid] = player
            logging.info(f'Updating player: {player} with result: {result}')
            if "not found" in result:
                status.code_invalid = True
            elif "Expired" in result:
                status.code_expired = True
            elif "Redeemed" in result:
                status.redeem_success += 1
            elif "Already claimed" in result:
                status.redeem_failed += 1
            else:
                status.redeem_failed += 1
                status.retry_ids.append(pid)
            if status.code_invalid or status.code_expired:
                while not queue.empty():
                    queue.get_nowait()
                    queue.task_done()
                break
        except Exception as e:
            await log_redeem_attempt(pid, player, code, e)
            queue.task_done()
            break
        finally:
            await log_redeem_attempt(pid, player, code, result)
            queue.task_done()

# Function to start worker, update and summary
async def use_codes(ctx, code, player_ids=None, retry_limit=4):
    if player_ids is None:
        player_data = await load_player_data('players.json')
        player_ids = list(player_data.keys())

    total_attempts = 1
    max_attempts = retry_limit + 1
    status = RedeemStatus()
    playercount = len(player_ids)
    thread = await ctx.channel.create_thread(name=f'Code: {code}', auto_archive_duration=4320, type=discord.ChannelType.public_thread)
    starting_info = f'Starting to redeem code **{code}** for {playercount} players. This could take up to {(12*playercount)/60} minutes'
    await thread.send(starting_info)
    queue = asyncio.Queue()

    while total_attempts <= max_attempts:
        loop = asyncio.get_event_loop()
        if not player_ids:
            print('No players left to process.')
            break
        print(f"Adding {len(player_ids)} players to the queue for attempt {total_attempts}.")
        for pid in player_ids:
            await queue.put(pid)
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = [asyncio.create_task(redeem_worker(queue, executor, loop, code, status)) for _ in range(4)]
            print(f'Worker task created, waiting for queue to be processed')
            await queue.join()
            for _ in range(4):
                await queue.put(None)
            print("Waiting for all worker tasks to complete")
            await asyncio.gather(*tasks)
        if status.retry_ids and total_attempts < max_attempts:
            print(f'Starting next try with {len(status.retry_ids)} players. It´s the {total_attempts} try')
            player_ids = status.retry_ids.copy()
            print(f'playerids: {player_ids}')
            status.retry_ids.clear()
            print(f'retry ids: {status.retry_ids}')
        else:
            print(f'No player left or max attempts reached after {total_attempts} tries')
            break
        total_attempts += 1

    print(f'Summary for code: {code}, success: {status.redeem_success}, failed: {status.redeem_failed}, attempts: {total_attempts}')
    print(f'Updating players')
    try:
        print(f'Input: {status.update_player}')
        updated_players, _ = await update_player_data(player_data=status.update_player)
        updated_player_count = len(updated_players)
    except Exception as e:
        print(f'Error while updating players: {e}')
        return
    finally:
        print("Sending summary")
        await send_summary(thread, code, playercount, status.redeem_success, status.redeem_failed, status.code_invalid, status.code_expired, total_attempts, updated_player_count)

async def send_summary(channel, code, playercount, redeem_success, redeem_failed, code_invalid, code_expired, total_attempts, updated_player_count):
    embed = discord.Embed(title=f"Stats for giftcode: {code}")
    embed.add_field(name="Players in database: ", value=f"{playercount}", inline=False)
    embed.add_field(name="Successfully redeemed for", value=f"{redeem_success} players", inline=True)
    embed.add_field(name="Already used or failed for", value=f"{redeem_failed} players", inline=True)
    embed.set_footer(text=f"Redeemed in {total_attempts} tries. Updated {updated_player_count} names.")
    if code_invalid:
        embed.set_footer(text="Code did not exist. Exited early.")
    elif code_expired:
        embed.set_footer(text="Code expired. Exited early.")
    await channel.send(embed=embed)
    print("Done")