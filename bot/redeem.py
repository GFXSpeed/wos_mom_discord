import random
import asyncio
import time
import discord
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from concurrent.futures import ThreadPoolExecutor
from .logging import log_redeem_attempt
from .player_management import load_player_data
from bot import bot, SELENIUM

op = Options()
op.add_argument("--disable-gpu")
op.add_argument("--ignore-ssl-errors=yes")
op.add_argument("--ignore-certificate-errors")

def redeem_code_for_player(code, pid):
    driver = webdriver.Remote(command_executor="SELENIUM", options=op)
    randomtime = random.uniform(1.0, 2.0)
    try:
        driver.get("https://wos-giftcode.centurygame.com/")
        time.sleep(2)
        driver.find_element(By.XPATH, "//input[@placeholder='Player ID']").send_keys(pid)
        print(f'Used PlayerID: {pid}')
        driver.find_element(By.XPATH, "//*[@id='app']/div/div/div[3]/div[2]/div[1]/div[1]/div[2]/span").click()
        time.sleep(1)
        player = driver.find_element(By.XPATH, "/html/body/div/div/div/div[3]/div[2]/div[1]/div[1]/p[1]").text
        print(f'PlayerID is: {player}')
        time.sleep(randomtime)
        driver.find_element(By.XPATH, "//input[@placeholder='Enter Gift Code']").send_keys(code)
        print('Entered code')
        time.sleep(randomtime)
        driver.find_element(By.XPATH, "//*[@id='app']/div/div/div[3]/div[2]/div[3]").click()
        time.sleep(randomtime)
        result = driver.find_element(By.XPATH, "/html/body/div/div/div[2]/div[2]/p").text
        print(f'{player}s result {result}')
    except NoSuchElementException:
        result = "Element not found"
    finally:
        driver.quit()
    return result, player

async def use_codes(ctx, code, player_ids=None, retry_limit=1):
    if player_ids is None:
        player_data = await load_player_data('players.json')
        player_ids = list(player_data.keys())
    
    redeem_success = 0
    redeem_failed = 0
    redeem_error = 0
    retry_ids = []

    playercount = len(player_ids)

    thread = await ctx.channel.create_thread(name=f'Code: {code}', auto_archive_duration=4320, type=discord.ChannelType.public_thread)
    starting_info = f'Starting to redeem code **{code}** for {playercount} players. This could take up to {(12*playercount)/60} minutes'
    await thread.send(starting_info)

    async def worker(queue):
        nonlocal redeem_success, redeem_failed, redeem_error, retry_ids
        while True:
            pid = await queue.get()
            if pid is None:
                break

            result, player = await loop.run_in_executor(executor, redeem_code_for_player, code, pid)
            try:
                if "not found" in result:
                    redeem_error = 1
                elif "Expired" in result:
                    redeem_error = 2                
                elif "Redeemed" in result:
                    redeem_success += 1                
                elif "Already claimed" in result:
                    redeem_failed += 1                
                else:
                    redeem_failed += 1
                    redeem_error = 3
                    retry_ids.append(pid)
                await log_redeem_attempt(pid, player, code, result)
                queue.task_done()

                if redeem_error == 1 or redeem_error == 2:
                    while not queue.empty():
                        queue.get_nowait()
                        queue.task_done()
                    break

            except Exception as e:
                await log_redeem_attempt(pid, player, code, e)
                break

    queue = asyncio.Queue()
    for pid in player_ids:
        await queue.put(pid)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        workers = [asyncio.create_task(worker(queue)) for _ in range(4)]
        await queue.join()

        for worker in workers:
            queue.put_nowait(None)
        await asyncio.gather(*workers)

    await send_summary(thread, code, playercount, redeem_success, redeem_failed, redeem_error)
    
    if retry_ids and retry_limit > 0 and redeem_error != 1 and redeem_error != 2:
        await use_codes(ctx, code, player_ids=retry_ids, retry_limit=retry_limit-1)

async def send_summary(channel, code, playercount, redeem_success, redeem_failed, redeem_error):
    embed = discord.Embed(title=f"Stats for giftcode: {code}")
    embed.add_field(name="Players in database: ", value=f"{playercount}", inline=False)
    embed.add_field(name="Successfully redeemed for", value=f"{redeem_success} players", inline=True)
    embed.add_field(name="Already used or failed for", value=f"{redeem_failed} players", inline=True)

    if redeem_error == 1:
        embed.set_footer(text="Code did not exist. Exited early.")
    elif redeem_error == 2:
        embed.set_footer(text="Code expired. Exited early.")
    elif redeem_error == 3:
        embed.set_footer(text="Unknown status for one or more ID. Will retry one time")

    await channel.send(embed=embed)