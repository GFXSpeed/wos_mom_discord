import hashlib
import json
import httpx
import asyncio
from datetime import datetime

WOS_PLAYER_INFO_URL = 'https://wos-giftcode-api.centurygame.com/api/player'
WOS_ENCRYPT_KEY = "tB87#kPtkxqOS2"
WOS_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://wos-giftcode.centurygame.com",
    "referer": "https://wos-giftcode.centurygame.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}

async def encode_data(data):
    encoded_data = "&".join(
        f"{key}={json.dumps(value) if isinstance(value, dict) else value}"
        for key, value in sorted(data.items())
    )
    sign = hashlib.md5(f"{encoded_data}{WOS_ENCRYPT_KEY}".encode()).hexdigest()
    return {"sign": sign, **data}


async def get_playerdata(player_id, client, max_retries=5, initial_wait=5):
    from .custom_logging import log_event

    data_to_encode = {
        "fid": str(player_id),
        "time": str(int(datetime.now().timestamp())),
    }
    encoded_data = await encode_data(data_to_encode)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.post(WOS_PLAYER_INFO_URL, headers=WOS_HEADERS, data=encoded_data)
            response.raise_for_status()

            player_data = response.json()
            if player_data.get("msg") == "success" and "data" in player_data:
                player_info = player_data["data"]
                print(f'pid {player_id} response: {player_data}')
                return {
                    "avatar_image": player_info.get("avatar_image"),
                    "fid": player_info.get("fid"),
                    "kid": player_info.get("kid"),
                    "nickname": player_info.get("nickname"),
                    "stove_lv": player_info.get("stove_lv"),
                    "stove_lv_content": player_info.get("stove_lv_content"),
                    "total_recharge_amount": player_info.get("total_recharge_amount"),
                }
            else:
                error_msg = f"Invalid response data format for player ID {player_id}"
                await log_event("PLAYER_DATA_ERROR", error=error_msg, player_id=player_id)
                last_error = ValueError(error_msg)
                continue

        except httpx.HTTPStatusError as e:
            response = e.response
            if response.status_code == 429:
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
