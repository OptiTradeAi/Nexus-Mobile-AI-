# Guia simples para iniciantes — Como subir no GitHub e testar

1) Criar repositório no GitHub
   - Abra github.com no navegador (ou app).
   - Clique em "+" → New repository.
   - Dê um nome (ex.: Nexus-AI) → Create repository.

2) Adicionar arquivos
   - No repositório, clique em "Add file" → "Create new file".
   - No campo "Name", escreva o caminho do arquivo, por ex: `extension/manifest.json`.
   - Cole o conteúdo do arquivo (do guia que você recebeu).
   - Commit (preencha mensagem curta como "add manifest") → Commit new file.
   - Repita para todos os arquivos listados.

3) Configurar backend (com Render — recomendado para quem não tem PC)
   - Crie conta em render.com (pode usar celular).
   - New → Web Service → Connect to GitHub → escolha o repositório.
   - Se houver Dockerfile, escolha Deploy with Docker; ou use build command `pip install -r backend/requirements.txt` e start `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
   - Depois de deploy bem-sucedido, anote a URL pública, ex: `https://meu-backend.onrender.com`. Use `wss://meu-backend.onrender.com/ws/stream` no extension popup.

4) Testar extensão (recomendado em desktop para primeiro teste)
   - No Firefox: abra `about:debugging` → "This Firefox" → "Load Temporary Add-on" → escolha `extension/manifest.json` na pasta que você fez upload/clonou.
   - No Chrome: abra `chrome://extensions` → Ativar 'Developer mode' → Load unpacked → selecione a pasta `extension/`.
   - Abra a aba da corretora `https://app.homebroker.com/trade`.
   - Abra o popup da extensão, coloque o WSS do backend e clique "Start Tab Stream". Aceite o pedido de captura (escolha *somente a aba da corretora*).

5) Se estiver sem PC (mobile-only): usar Termux fallback
   - Instale Termux via F-Droid.
   - Dentro do Termux:
     ```
     pkg update && pkg upgrade -y
     pkg install python -y
     pkg install android-tools -y  # fornece adb
     pip install websockets pillow
     ```
   - Ligue a Depuração (Opções do desenvolvedor → Depuração Wi-Fi ou USB).
   - Quando conectado/pareado, exporte a variável se quiser:
     ```
     export NEXUS_WS="ws://SEU_BACKEND/ws/stream"
     python scripts/termux_stream.py
     ```
   - Abra o app da corretora no celular: o Termux vai enviar screenshots ao backend.

6) App mobile (Expo)
   - Recomendado: usar Expo/EAS para gerar APK sem PC.
   - Siga `docs/ci_eas.md` para configurar Expo e gerar APK (é necessário criar conta Expo e token).
   - Depois de gerar o APK, instale no celular e abra; coloque a URL do backend nas configurações do app.

7) Observações finais
   - O sistema só envia "sinais" se a confiança >= 0.8 (80%).
   - Para usar apenas espelhamento e não leitura, configure o engine para apenas encaminhar frames para tela do app e só emitir sinais quando desejado.
