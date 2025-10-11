Passo-a-passo rápido de deploy (Resumo técnico fácil):

1. Push do repo para GitHub (já feito via copiar/colar).
2. Deploy backend:
   - Usar Render: criar Web Service, conectar GitHub, Build (Dockerfile ou pip install), Start: uvicorn backend.main:app --host 0.0.0.0 --port 8000
   - Ou rodar localmente (PC): python -m pip install -r backend/requirements.txt ; python backend/main.py

3. Atualizar extensão com BACKEND WSS:
   - No popup, preencha wss://SEU_BACKEND/ws/stream

4. Teste fluxo:
   - Start extension → selecionar aba HomeBroker → backend deve receber frames → app deve receber sinais.

5. Gerar APK (Expo/EAS):
   - Criar conta expo.dev → criar EXPO_TOKEN → adicionar no GitHub Secrets → usar workflow `ci/github-actions-eas.yml` para rodar `eas build --platform android`.
