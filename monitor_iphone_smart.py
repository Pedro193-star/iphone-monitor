name: Monitor iPhones OLX

on:
  schedule:
    - cron: '*/7 * * * *'   # Corre a cada 7 minutos (com margem para atraso GitHub)
  workflow_dispatch:          # Permite correr manualmente

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout do repositorio
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Instalar dependencias
        run: pip install requests beautifulsoup4

      - name: Restaurar historico e medias
        uses: actions/cache@v4
        with:
          path: |
            historico.json
            medias.json
          key: dados-monitor-${{ github.run_id }}
          restore-keys: |
            dados-monitor-

      - name: Correr o monitor
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python monitor_iphone_smart.py

      - name: Guardar historico e medias
        uses: actions/cache/save@v4
        if: always()
        with:
          path: |
            historico.json
            medias.json
          key: dados-monitor-${{ github.run_id }}
