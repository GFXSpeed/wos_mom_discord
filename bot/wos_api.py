import hashlib
import json
from datetime import datetime

WOS_GIFTCODE_URL = 'https://wos-giftcode-api.centurygame.com/api/gift_code'
WOS_ENCRYPT_KEY = "tB87#kPtkxqOS2"
DEFAULT_STATE = 543
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

# API msg -> internal status. Anything unlisted becomes ERROR.
STATUS_BY_MSG = {
    "SUCCESS": "SUCCESS",
    "RECEIVED.": "ALREADY_RECEIVED",
    "TIME ERROR.": "EXPIRED",
    "CDK NOT FOUND.": "INVALID",
    "USED.": "CLAIM_LIMIT",
    "RECHARGE_MONEY ERROR.": "REQUIREMENT",
    "RECHARGE_MONEY_VIP ERROR.": "REQUIREMENT",
    "USER INFO ERROR.": "USER_INVALID",  # unknown player id or wrong state
}


async def encode_data(data):
    encoded_data = "&".join(
        f"{key}={json.dumps(value) if isinstance(value, dict) else value}"
        for key, value in sorted(data.items())
    )
    sign = hashlib.md5(f"{encoded_data}{WOS_ENCRYPT_KEY}".encode()).hexdigest()
    return {"sign": sign, **data}


async def redeem_request(client, player_id, state, giftcode):
    """One call to the gift code API. It validates fid+kid before it looks at the code."""
    payload = {
        "fid": str(player_id),
        "cdk": giftcode,
        "kid": str(state),
        "time": str(int(datetime.now().timestamp())),
    }
    data = await encode_data(payload)
    response = await client.post(WOS_GIFTCODE_URL, headers=WOS_HEADERS, data=data)

    if response.status_code != 200:
        print(f"[GIFTCODE] fid={player_id} kid={state} cdk={giftcode} http={response.status_code}")
        return "ERROR"

    obj = response.json()
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    status = STATUS_BY_MSG.get(obj.get("msg"), "ERROR")
    print(f"[GIFTCODE] fid={player_id} kid={state} cdk={giftcode} -> {status} {obj}")
    return status


async def verify_player(client, player_id, state):
    """
    True if the id+state pair is accepted, False if not, None if the API didn't tell us.

    ponytail: /api/player and /api/captcha are gone (404). The only remaining way to
    check a player is a redeem call with a bogus code - the API rejects the user first.
    """
    status = await redeem_request(client, player_id, state, "Test")
    if status == "USER_INVALID":
        return False
    if status == "INVALID":  # player accepted, only the dummy code was rejected
        return True
    return None
