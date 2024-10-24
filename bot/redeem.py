import discord
import hashlib
import json
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter, Retry
from .player_management import load_player_data, update_player_data
from bot import bot, SELENIUM

wos_player_info_url = "https://wos-giftcode-api.centurygame.com/api/player"
wos_giftcode_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
wos_giftcode_redemption_url = "https://wos-giftcode.centurygame.com"
wos_encrypt_key = "tB87#kPtkxqOS2"

retry_config = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429],
    allowed_methods=["POST"]
)


def get_session():
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry_config))

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/x-www-form-urlencoded",
        "origin": wos_giftcode_redemption_url,
    }
    session.headers.update(headers)
    return session

def authenticate(player_id):
    session = get_session()
    data_to_encode = {
        "fid": f"{player_id}",
        "time": f"{int(datetime.now().timestamp())}",
    }
    data = encode_data(data_to_encode)
    response_stove_info = session.post(
        wos_player_info_url,
        data=data,
    )
    return session, response_stove_info

def encode_data(data):
    sorted_keys = sorted(data.keys())
    encoded_data = "&".join(
        [
            f"{key}={json.dumps(data[key]) if isinstance(data[key], dict) else data[key]}"
            for key in sorted_keys
        ]
    )
    sign = hashlib.md5(f"{encoded_data}{wos_encrypt_key}".encode()).hexdigest()
    return {"sign": sign, **data}

def claim_giftcode(player_id, giftcode):
    session, response_stove_info = authenticate(player_id)
    if response_stove_info.json().get("msg") == "success":
        data_to_encode = {
            "fid": f"{player_id}",
            "cdk": giftcode,
            "time": f"{int(datetime.now().timestamp())}",
        }
        data = encode_data(data_to_encode)
        response_giftcode = session.post(
            wos_giftcode_url,
            data=data,
        )
        response_json = response_giftcode.json()
        print(f"Response for {player_id}: {response_json}")
        if response_json.get("msg") == "SUCCESS":
            return session, "SUCCESS"
        elif response_json.get("msg") == "RECEIVED." and response_json.get("err_code") == 40008:
            return session, "ALREADY_RECEIVED"
        else:
            return session, "ERROR"
    else:
        return session, 

async def use_codes(ctx, code, player_ids=None):
    success_results = []
    received_results = []
    failure_results = []

    if player_ids is None:
        player_data = await load_player_data('players.json')
        player_ids = list(player_data.keys())

    playercount = len(player_ids)
    thread = await ctx.channel.create_thread(name=f'Code: {code}', auto_archive_duration=4320, type=discord.ChannelType.public_thread)
    starting_info = f'Starting to redeem code **{code}** for {playercount} players. This could take up to {(12*playercount)/60} minutes'
    await thread.send(starting_info)

    for pid in player_ids:
        try:
            session, response_status = claim_giftcode(pid, code)

            if response_status == "SUCCESS":
                print(f'{pid} SUCCESS')
                success_results.append(pid)
            elif response_status == "ALREADY_RECEIVED":
                received_results.append(pid)
                print(f'{pid} ALREADY CLAIMED')
            else:
                failure_results.append(pid)
                print(f'{pid} FAILED')
        except Exception as e:
            print(e)
            failure_results.append(pid)
    
    redeem_success = len(success_results)
    redeem_failed = len(failure_results)
    await send_summary(thread, code, playercount, redeem_success, redeem_failed)
 


async def send_summary(channel, code, playercount, redeem_success, redeem_failed):
    embed = discord.Embed(title=f"Stats for giftcode: {code}")
    embed.add_field(name="Players in database: ", value=f"{playercount}", inline=False)
    embed.add_field(name="Successfully redeemed for", value=f"{redeem_success} players", inline=True)
    embed.add_field(name="Already used or failed for", value=f"{redeem_failed} players", inline=True)
    #embed.set_footer(text=f"Redeemed in {total_attempts} tries. Updated {updated_player_count} names.")
    #if code_invalid:
    #    embed.set_footer(text="Code did not exist. Exited early.")
    #elif code_expired:
    #    embed.set_footer(text="Code expired. Exited early.")
    #elif no_worker:
    #    embed.set_footer(text="Can´t do this at the moment. Please try again later.")
    await channel.send(embed=embed)
    print("Done")