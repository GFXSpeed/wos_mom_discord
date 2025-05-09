import os
import asyncio
import base64
import json
from io import BytesIO
from datetime import datetime
import string

import numpy as np
import httpx
from PIL import Image
from tensorflow.keras.models import load_model
from bot.wos_api import encode_data

WOS_CAPTCHA_URL = 'https://wos-giftcode-api.centurygame.com/api/captcha'

CAPTCHA_DIR = os.path.join(os.path.dirname(__file__), '..', 'captcha')
MODEL_PATH = os.path.join(CAPTCHA_DIR, 'model.keras')
BASE64_STORE_PATH = os.path.join(CAPTCHA_DIR, 'base64_strings.txt')
os.makedirs(CAPTCHA_DIR, exist_ok=True)

class CaptchaSolver:
    def __init__(self, model_path: str = MODEL_PATH):
        self.model = load_model(model_path)
        dummy = np.zeros((1,
                          self.model.input_shape[1],
                          self.model.input_shape[2],
                          self.model.input_shape[3]), dtype=np.float32)
        self.model.predict(dummy)
        _, self.height, self.width, self.channels = self.model.input_shape

    async def _fetch_captcha(self, player_id: str, client: httpx.AsyncClient) -> bytes:
        payload = {'fid': str(player_id), 'time': str(int(datetime.now().timestamp()))}
        data = await encode_data(payload)
        resp = await client.post(WOS_CAPTCHA_URL, data=data)
        resp.raise_for_status()
        obj = resp.json()
        if obj.get('msg') != 'SUCCESS' or 'data' not in obj:
            raise RuntimeError(f"Captcha API error: {obj}")

        b64_field = obj['data'].get('img_code') or next(
            (v for v in obj['data'].values() if isinstance(v, str) and 'base64,' in v),
            None
        )
        if not b64_field:
            raise RuntimeError(f"Invalid captcha field: {obj['data']}")

        b64 = b64_field.split('base64,', 1)[1]
        with open(BASE64_STORE_PATH, 'a') as f:
            f.write(json.dumps({'b64': b64, 'time': datetime.now().isoformat()}) + '\n')
        return base64.b64decode(b64)

    def _preprocess(self, raw: bytes) -> np.ndarray:
        img = Image.open(BytesIO(raw)).convert('L')
        img = img.resize((self.width, self.height), Image.LANCZOS)
        arr = np.array(img, dtype=np.float32) / 255.0
        if self.channels == 3:
            arr = np.stack([arr] * 3, axis=-1)
        else:
            arr = arr[..., np.newaxis]
        return arr[np.newaxis, ...]

    def _predict_sync(self, raw: bytes) -> str:
        inp = self._preprocess(raw)
        preds = self.model.predict(inp)
        charset = list(string.ascii_letters + string.digits)
        code = ''
        for char_probs in preds:
            probs = char_probs[0]
            idx = np.argmax(probs)
            code += charset[idx] if 0 <= idx < len(charset) else ''
        print(f"Decoded captcha: {code}", flush=True)
        return code

    async def solve(self, player_id: str, client: httpx.AsyncClient) -> str:
        raw = await self._fetch_captcha(player_id, client)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._predict_sync, raw)
