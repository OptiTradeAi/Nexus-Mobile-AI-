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
        # Ajuste o seletor para o dropdown de pares na corretora
        # Exemplo: clicar no dropdown e selecionar o par
        await self.page.click('css=selector_do_dropdown_de_pares')  # <<< ATENÇÃO: ajustar seletor real
        await asyncio.sleep(0.5)
        await self.page.click(f'text="{pair}"')
        await asyncio.sleep(1)  # espera o gráfico atualizar
        self.current_index = (self.current_index + 1) % len(self.pairs)
        return pair
