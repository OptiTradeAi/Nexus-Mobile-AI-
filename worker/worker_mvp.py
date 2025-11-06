# worker/worker_mvp.py
import asyncio
import base64
import json
import math
from collections import deque, defaultdict
from datetime import datetime, timezone
import aiohttp
import numpy as np
from PIL import Image
import io
import time
import websockets

BACKEND_WS = "wss://nexus-mobile-ai.onrender.com/ws?token=d33144d6cb84fe05bf38bb9f22591683"
BACKEND_SIGNALS_URL = "https://nexus-mobile-ai.onrender.com/signals?token=d33144d6cb84fe05bf38bb9f22591683"

# params
FRAMES_HISTORY = 12  # keep last N frames per pair
TREND_SLOPE_THRESHOLD = 0.6  # heuristic threshold for slope -> confidence
MIN_LEAD_TIME = 40  # seconds before open to emit signal
CANCEL_WINDOW = 10   # seconds before open to allow cancel
TIMEFRAME = "M5"

# state
frames_by_pair = defaultdict(lambda: deque(maxlen=FRAMES_HISTORY))
candidates = {}  # key = (pair, open_ts) -> dict {rid, action, sent_at, confirmed}

def next_m5_open_ts(now_ts=None):
    from datetime import datetime, timedelta
    if now_ts is None:
        now = datetime.utcnow()
    else:
        now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    minute = now.minute
    add = (5 - (minute % 5)) % 5
    if add == 0 and now.second == 0:
        target = now
    else:
        target = (now.replace(second=0, microsecond=0) + timedelta(minutes=add if add>0 else 5))
    return int(target.replace(tzinfo=timezone.utc).timestamp())

def image_brightness(jpeg_bytes):
    try:
        im = Image.open(io.BytesIO(jpeg_bytes)).convert("L").resize((64,64))
        arr = np.array(im).astype(float)
        return float(arr.mean())
    except Exception as e:
        return None

async def post_signal_to_backend(sig: dict):
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.post(BACKEND_SIGNALS_URL, json=sig) as resp:
                text = await resp.text()
                print("POST signal resp:", resp.status, text[:200])
                return resp.status, text
        except Exception as e:
            print("POST error", e)
            return None, str(e)

async def process_meta_with_binary(meta, binary_bytes):
    # meta: contains pair, method, rid, client_ts
    pair = meta.get('pair') or 'AUTO'
    b = binary_bytes
    brightness = image_brightness(b)
    if brightness is None:
        return
    frames_by_pair[pair].append((int(time.time()), brightness, b))
    # compute trend slope over brightnesss
    hist = frames_by_pair[pair]
    if len(hist) < 4:
        return
    xs = np.arange(len(hist))
    ys = np.array([h[1] for h in hist])
    # linear fit
    A = np.vstack([xs, np.ones(len(xs))]).T
    m, c = np.linalg.lstsq(A, ys, rcond=None)[0]
    # normalize slope to confidence heuristic
    confidence = min(0.99, max(0.05, abs(m) / 20.0))
    action = "CALL" if m > 0 else "PUT"
    now_ts = int(time.time())
    open_ts = next_m5_open_ts(now_ts)
    time_to_open = open_ts - now_ts
    key = (pair, open_ts)
    # only emit if >= MIN_LEAD_TIME and not already emitted
    if time_to_open >= MIN_LEAD_TIME and key not in candidates:
        rid = meta.get('rid') or str(uuid.uuid4())
        sig = {
            "type": "signal",
            "rid": rid,
            "pair": pair,
            "timeframe": TIMEFRAME,
            "open_ts": open_ts,
            "sent_at": now_ts,
            "action": action,
            "confidence": float(confidence),
            "reason": f"Simple brightness-trend slope {m:.4f}",
            "expires_at": open_ts + 60,
            "preview_image": None,
            "audio_url": None,
            "note": None
        }
        print("Emitting signal", sig)
        status, text = await post_signal_to_backend(sig)
        candidates[key] = {"rid": rid, "action": action, "sent_at": now_ts, "status": status}
    # if already emitted, check for cancellation window
    if key in candidates:
        # if we are within CANCEL_WINDOW and action flips, send cancel
        sent = candidates[key]
        if (open_ts - now_ts) <= CANCEL_WINDOW:
            prev_action = sent.get('action')
            if action != prev_action:
                # send cancel
                cancel_sig = {
                    "type": "signal",
                    "rid": sent.get('rid'),
                    "pair": pair,
                    "timeframe": TIMEFRAME,
                    "open_ts": open_ts,
                    "sent_at": int(time.time()),
                    "action": "CANCELLED",
                    "confidence": 0.0,
                    "reason": f"Analysis changed {prev_action} -> {action} within {CANCEL_WINDOW}s",
                    "expires_at": open_ts + 60,
                    "preview_image": None,
                    "audio_url": None,
                    "note": "CANCELLED"
                }
                print("Sending CANCEL", cancel_sig)
                await post_signal_to_backend(cancel_sig)
                # mark as cancelled so we don't repeatedly cancel
                candidates.pop(key, None)

async def ws_consumer():
    async with websockets.connect(BACKEND_WS, max_size=2**25) as ws:
        print("Worker connected to backend WS")
        last_meta = None
        async for message in ws:
            # message can be text or bytes
            if isinstance(message, bytes):
                # pair binary with last_meta
                if last_meta:
                    try:
                        await process_meta_with_binary(last_meta, message)
                    except Exception as e:
                        print("process binary error", e)
                    last_meta = None
                else:
                    # ignore or could attempt to process
                    pass
            else:
                # text
                try:
                    obj = json.loads(message)
                except Exception:
                    continue
                if obj.get('type') == 'meta':
                    last_meta = obj
                elif obj.get('type') == 'frame':
                    # may contain data_b64
                    b64 = obj.get('data_b64')
                    if b64:
                        try:
                            b = base64.b64decode(b64)
                            await process_meta_with_binary(obj, b)
                        except:
                            pass
                else:
                    pass

async def main():
    while True:
        try:
            await ws_consumer()
        except Exception as e:
            print("Worker WS connection error:", e)
            await asyncio.sleep(2)

if __name__ == "__main__":
    import uuid, os
    print("Starting worker MVP")
    asyncio.run(main())
