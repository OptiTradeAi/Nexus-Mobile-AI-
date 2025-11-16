import base64

class NavigatorCapture:
    def __init__(self, page):
        self.page = page

    async def capture_chart(self):
        # Ajuste o seletor para o canvas ou elemento do gráfico na corretora
        canvas = await self.page.query_selector('canvas')
        if not canvas:
            raise Exception('Canvas do gráfico não encontrado')
        # Captura screenshot do canvas em webp
        img_bytes = await canvas.screenshot(type='webp')
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        return img_b64
