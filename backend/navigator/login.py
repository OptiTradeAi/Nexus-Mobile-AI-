from playwright.async_api import async_playwright

class NavigatorLogin:
    def __init__(self, page):
        self.page = page
        self.username = "diegobino342@gmail.com"
        self.password = "Thiago1010*"

    async def do_login(self):
        await self.page.goto('https://www.homebroker.com/pt/login')
        # Aguarda o campo email
        await self.page.wait_for_selector('input#email')
        # Preenche usuário e senha
        await self.page.fill('input#email', self.username)
        await self.page.fill('input#password', self.password)
        # Clica no botão de login
        await self.page.click('button[type="submit"]')
        # Espera a página carregar após login
        await self.page.wait_for_load_state('networkidle')
        # Verifica se houve erro de login
        if await self.page.query_selector('text=Usuário ou senha inválidos'):
            raise Exception('Falha no login: credenciais inválidas')
        print("✅ Login realizado com sucesso")
        return True
