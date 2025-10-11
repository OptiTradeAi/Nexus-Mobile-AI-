Expo/EAS build (sem PC — usando GitHub Actions):

1. Crie conta em https://expo.dev e gere um token (Account -> Access Tokens).
2. No GitHub, entre no repositório -> Settings -> Secrets -> New repository secret:
   - Name: EXPO_TOKEN
   - Value: seu token do Expo
3. Verifique o arquivo `.github/workflows` ou `ci/github-actions-eas.yml` neste repositório (já incluído).
4. Ao dar push na branch `main`, o workflow vai executar o EAS build (se você ajustar o script para rodar via CLI).
5. Quando o build terminar, baixe o APK do Expo (ou dos artifacts do Action).
