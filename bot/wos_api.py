import hashlib
import json
import httpx
import asyncio
from datetime import datetime

WOS_PLAYER_INFO_URL = 'https://wos-giftcode-api.centurygame.com/api/player'
WOS_ENCRYPT_KEY = "tB87#kPtkxqOS2"

async def encode_data(data):
    encoded_data = "&".join(
        f"{key}={json.dumps(value) if isinstance(value, dict) else value}"
        for key, value in sorted(data.items())
    )
    sign = hashlib.md5(f"{encoded_data}{WOS_ENCRYPT_KEY}".encode()).hexdigest()
    return {"sign": sign, **data}

async def get_playerdata(player_id, client, max_retries=5, initial_wait=5):
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/x-www-form-urlencoded",
        "origin": WOS_PLAYER_INFO_URL,
    }
    data_to_encode = {
        "fid": str(player_id),
        "time": str(int(datetime.now().timestamp())),
    }
    data = await encode_data(data_to_encode)
    
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.post(WOS_PLAYER_INFO_URL, headers=headers, data=data)
            response.raise_for_status()  # Raise error for non-200 responses
            
            player_data = response.json()
            if player_data.get("msg") == "success" and "data" in player_data:
                data = player_data["data"]
                return {
                    "avatar_image": data.get("avatar_image"),
                    "fid": data.get("fid"),
                    "kid": data.get("kid"),
                    "nickname": data.get("nickname"),
                    "stove_lv": data.get("stove_lv"),
                    "stove_lv_content": data.get("stove_lv_content"),
                    "total_recharge_amount": data.get("total_recharge_amount"),
                }
            else:
                print(f"Error: Data not found in response for player ID {player_id}")
                return None

        except httpx.HTTPStatusError as e:
            if response.status_code == 429:  # Rate limit exceeded
                retry_after = int(response.headers.get("Retry-After", initial_wait * (2 ** (attempt - 1))))
                print(f"Rate limit exceeded for player ID {player_id}. Retrying in {retry_after} seconds...")
                await asyncio.sleep(retry_after)
            else:
                print(f"Request failed for player ID {player_id} with error: {e}")
                return None

    print(f"Max retries reached for player ID {player_id}. Request failed.")
    return None
