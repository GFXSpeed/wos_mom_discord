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
    from .custom_logging import log_event
    
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
    
    last_error = None
    response = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.post(WOS_PLAYER_INFO_URL, headers=headers, data=data)
            response.raise_for_status()
            
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
                error_msg = f"Invalid response data format for player ID {player_id}"
                await log_event("PLAYER_DATA_ERROR", error=error_msg, player_id=player_id)
                last_error = ValueError(error_msg)
                continue
            
            

        except httpx.HTTPStatusError as e:
            response = e.response
            if response.status_code == 429:  # Rate limit exceeded
                retry_after = int(response.headers.get("Retry-After", initial_wait * (2 ** (attempt - 1))))
                await log_event("RATE_LIMIT", player_id=player_id, retry_after=retry_after, attempt=attempt)
                await asyncio.sleep(retry_after)
                last_error = e
                continue
            else:
                error_msg = f"HTTP error {response.status_code} for player ID {player_id}: {e}"
                await log_event("HTTP_ERROR", error=error_msg, player_id=player_id)
                last_error = e
                continue
                
        except Exception as e:
            error_msg = f"Unexpected error for player ID {player_id}: {str(e)}"
            await log_event("UNEXPECTED_ERROR", error=error_msg, player_id=player_id)
            last_error = e
            continue

    # If we got here, we failed all retries
    final_error = f"Max retries ({max_retries}) reached for player ID {player_id}."
    if last_error:
        final_error += f" Last error: {str(last_error)}"
    await log_event("MAX_RETRIES", error=final_error, player_id=player_id)
    return None
