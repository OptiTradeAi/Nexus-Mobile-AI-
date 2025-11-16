import asyncio
import json
import websockets
from datetime import datetime
from playwright.async_api import async_playwright

from backend.navigator.login import NavigatorLogin
from backend.navigator.switch_pairs import NavigatorSwitchPairs
from backend.navigator.capture import NavigatorCapture

BACKEND_WS_URL = "wss://nexus-mobile-ai.onrender.com/ws/stream"
AGENT_ID = "agent-navigator-01"

class NexusNavigator:
    def __init__(self):
        self.ws = None
        self.page = None
        self.browser = None

    async def connect_ws(self):
        self.ws = await websockets.connect(BACKEND_WS_URL)
        await self.ws.send(json.dumps({"type": "hello", "agent_id": AGENT_ID, "ts": datetime.utcnow().isoformat()}))

    async def send_frame(self, pair, img_b64):
        payload = {
            "type": "frame",
            "data": img_b64,
            "mime": "image/webp",
            "pair": pair,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": AGENT_ID
        }
        await self.ws.send(json.dumps(payload))

    async def run(self):
        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            login = NavigatorLogin(self.page)
            await login.do_login()
            switcher = NavigatorSwitchPairs(self.page)
            capturer = NavigatorCapture(self.page)
            await self.connect_ws()

            while True:
                pair = await switcher.switch_to_next_pair()
                img_b64 = await capturer.capture_chart()
                await self.send_frame(pair, img_b64)
                # Intervalo entre pares, ajuste conforme necessidade
                await asyncio.sleep(10)

if __name__ == "__main__":
    navigator = NexusNavigator()
    asyncio.run(navigator.run())
