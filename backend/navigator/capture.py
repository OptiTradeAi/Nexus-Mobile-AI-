import base64

class NavigatorCapture:
    def __init__(self, page):
        self.page = page

    async def capture_chart(self):
        # Captura o canvas do gráfico - ajuste o seletor conforme a corretora
        canvas = await self.page.query_selector('canvas.chart-canvas')
        if not canvas:
            raise Exception('Canvas do gráfico não encontrado')
        img_bytes = await canvas.screenshot(type='webp')
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        print("📸 Gráfico capturado")
        return img_b64
