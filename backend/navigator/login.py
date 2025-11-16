import asyncio
from playwright.async_api import async_playwright

class NavigatorLogin:
    def __init__(self, page):
        self.page = page
        self.username = "diegobino342@gmail.com"
        self.password = "Thiago1010*"

    async def do_login(self):
        await self.page.goto('https://www.homebroker.com/pt/login')
        await self.page.wait_for_selector('input#email')
        await self.page.fill('input#email', self.username)
        await self.page.fill('input#password', self.password)
        await self.page.click('button[type="submit"]')
        await self.page.wait_for_load_state('networkidle')
        if await self.page.query_selector('text=Usuário ou senha inválidos'):
            raise Exception('Falha no login: credenciais inválidas')
        return True
