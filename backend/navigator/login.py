import asyncio
from playwright.async_api import async_playwright

class NavigatorLogin:
    def __init__(self, page):
        # Credenciais embutidas para automação
        self.page = page
        self.username = "diegobino342@gmail.com"
        self.password = "Thiago1010*"

    async def do_login(self):
        # Ajuste os seletores conforme a corretora
        await self.page.goto('https://www.homebroker.com/pt/login')
        await self.page.wait_for_selector('input[name="username"]')
        await self.page.fill('input[name="username"]', self.username)
        await self.page.fill('input[name="password"]', self.password)
        await self.page.click('button[type="submit"]')
        # Espera página carregar após login
        await self.page.wait_for_load_state('networkidle')
        # Verifica se login foi bem sucedido
        if await self.page.query_selector('text=Login inválido'):
            raise Exception('Falha no login: credenciais inválidas')
        return True
