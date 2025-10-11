# Termux streamer: usa adb para tirar screenshots e enviar ao backend via WebSocket
# Requisitos no Termux: python, android-tools (adb), pip install websockets pillow
import os, subprocess, asyncio, websockets

async def main():
    uri = os.environ.get("NEXUS_WS", "ws://localhost:8000/ws/stream")
    print("Conectando em", uri)
    async with websockets.connect(uri) as ws:
        while True:
            p = subprocess.run(["adb","exec-out","screencap","-p"], stdout=subprocess.PIPE)
            img = p.stdout
            try:
                await ws.send(img)  # envia bytes
                resp = await ws.recv()
                print("ACK:", resp)
            except Exception as e:
                print("Erro envio:", e)
                break
            await asyncio.sleep(1.0)  # 1 frame por segundo

if __name__ == "__main__":
    asyncio.run(main())
