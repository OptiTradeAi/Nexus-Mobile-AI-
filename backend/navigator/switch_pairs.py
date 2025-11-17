import asyncio

class NavigatorSwitchPairs:
    def __init__(self, page):
        self.page = page
        # Lista dos pares OTC para varrer
        self.pairs = ["EUR/USD", "GBP/JPY", "AUD/USD", "USD/JPY", "USD/CAD"]
        self.current_index = 0

    async def switch_to_next_pair(self):
        if not self.pairs:
            raise Exception('Lista de pares vazia')
        pair = self.pairs[self.current_index]
        print(f"🔄 Trocando para o par: {pair}")
        # Clica no dropdown de pares - ajuste o seletor conforme a corretora
        await self.page.click('button[data-testid="dropdown-pairs"]')
        await asyncio.sleep(0.5)
        # Seleciona o par na lista
        await self.page.click(f'text="{pair}"')
        await asyncio.sleep(1)  # espera o gráfico atualizar
        self.current_index = (self.current_index + 1) % len(self.pairs)
        return pair
