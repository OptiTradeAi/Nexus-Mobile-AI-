import asyncio

class NavigatorSwitchPairs:
    def __init__(self, page):
        self.page = page
        self.pairs = ["EUR/USD", "GBP/JPY", "AUD/USD", "USD/JPY", "USD/CAD"]
        self.current_index = 0

    async def switch_to_next_pair(self):
        if not self.pairs:
            raise Exception('Lista de pares vazia')
        pair = self.pairs[self.current_index]
        await self.page.click('button[data-testid="dropdown-pairs"]')  # Ajuste conforme corretora
        await asyncio.sleep(0.5)
        await self.page.click(f'text="{pair}"')
        await asyncio.sleep(1)
        self.current_index = (self.current_index + 1) % len(self.pairs)
        return pair
