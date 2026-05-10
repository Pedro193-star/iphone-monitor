"""
╔══════════════════════════════════════════════════════════════════════╗
║        MONITOR DE iPHONES — OLX Portugal                           ║
║        Alerta quando o preço está abaixo do teu limite             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from datetime import datetime
from typing import Optional


# ======================================================================
#  ⚙️  CONFIGURAÇÕES — EDITA APENAS ESTA SECÇÃO
# ======================================================================

# Lê automaticamente os secrets do GitHub Actions
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# Ficheiro de persistência (IDs já notificados)
FICHEIRO_DADOS = "dados_mercado.json"

# -----------------------------------------------------------------------
# 💶 PREÇOS MÁXIMOS POR MODELO
# Se um anúncio aparecer ABAIXO deste valor → recebes notificação
# Muda os valores à tua vontade!
# -----------------------------------------------------------------------
MODELOS = {
    "iPhone 14":         {"preco_max": 300, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14/"},
    "iPhone 14 Pro":     {"preco_max": 380, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14-pro/"},
    "iPhone 14 Pro Max": {"preco_max": 420, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14-pro-max/"},
    "iPhone 15":         {"preco_max": 450, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15/"},
    "iPhone 15 Pro":     {"preco_max": 550, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15-pro/"},
    "iPhone 15 Pro Max": {"preco_max": 620, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15-pro-max/"},
    "iPhone 16":         {"preco_max": 600, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16/"},
    "iPhone 16 Pro":     {"preco_max": 700, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16-pro/"},
    "iPhone 16 Pro Max": {"preco_max": 800, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16-pro-max/"},
    "iPhone 17":         {"preco_max": 750, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17/"},
    "iPhone 17 Pro":     {"preco_max": 900, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17-pro/"},
    "iPhone 17 Pro Max": {"preco_max": 1000, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17-pro-max/"},
}

# ======================================================================
#  FIM DAS CONFIGURAÇÕES
# ======================================================================


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def carregar_vistos() -> list:
    if os.path.exists(FICHEIRO_DADOS):
        try:
            with open(FICHEIRO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def guardar_vistos(vistos: list):
    with open(FICHEIRO_DADOS, "w", encoding="utf-8") as f:
        json.dump(vistos[-5000:], f, ensure_ascii=False, indent=2)


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def enviar_telegram(texto: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except requests.RequestException as e:
        log(f"[Telegram] Erro: {e}")
        return False


def montar_alerta(modelo: str, anuncio: dict, preco_max: int) -> str:
    poupanca = preco_max - anuncio["preco_num"]
    estrelas = "🔥🔥" if poupanca > 100 else ("🔥" if poupanca > 50 else "✅")
    return (
        f"{estrelas} <b>NEGÓCIO ABAIXO DO TEU LIMITE!</b>\n\n"
        f"📱 <b>Modelo:</b> {modelo}\n"
        f"📌 <b>{anuncio['titulo']}</b>\n\n"
        f"💶 <b>Preço anúncio:</b> {anuncio['preco_num']}€\n"
        f"🎯 <b>Teu limite:</b> {preco_max}€\n"
        f"💰 <b>Poupança:</b> {poupanca}€ abaixo do limite\n\n"
        f"🔗 <a href=\"{anuncio['link']}\">Ver anúncio no OLX</a>"
    )


def extrair_preco(texto: str) -> Optional[int]:
    if not texto:
        return None
    limpo = texto.strip().lower()
    if any(p in limpo for p in ["grátis", "troca", "ver desc"]):
        return None
    sem_milhar = re.sub(r"\.(?=\d{3})", "", limpo)
    sem_decimal = re.sub(r",\d{1,2}$", "", sem_milhar)
    numeros = re.findall(r"\d+", sem_decimal)
    if numeros:
        valor = int(numeros[0])
        if 50 <= valor <= 5000:
            return valor
    return None


def extrair_id(link: str) -> str:
    match = re.search(r"ID(\w+)", link)
    if match:
        return match.group(1)
    return str(abs(hash(link)) % (10 ** 10))


def scrape_olx(url: str) -> list:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"  [OLX] Erro HTTP: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.find_all("div", {"data-cy": "l-card"})
    if not cards:
        cards = soup.find_all("li", class_=re.compile(r"css-\w+"))

    anuncios = []
    for card in cards:
        try:
            titulo_el = card.find("h6") or card.find("h4") or card.find("h3")
            if not titulo_el:
                continue
            titulo = titulo_el.get_text(strip=True)

            link_el = card.find("a", href=True)
            if not link_el:
                continue
            link = link_el["href"]
            if not link.startswith("http"):
                link = "https://www.olx.pt" + link
            link = link.split("?")[0]

            anuncio_id = extrair_id(link)

            preco_el = (
                card.find("p", {"data-testid": "ad-price"})
                or card.find("p", class_=re.compile(r"price|Price", re.I))
                or card.find("strong")
            )
            preco_texto = preco_el.get_text(strip=True) if preco_el else ""
            preco_num = extrair_preco(preco_texto)

            if preco_num is None:
                continue

            anuncios.append({
                "id": anuncio_id,
                "titulo": titulo,
                "preco_num": preco_num,
                "link": link,
            })
        except Exception as e:
            log(f"  Erro num card: {e}")

    return anuncios


def processar_modelo(modelo: str, config: dict, vistos: list) -> int:
    preco_max = config["preco_max"]
    url = config["url"]

    log(f"\n🔍 {modelo} — limite: {preco_max}€")

    anuncios = scrape_olx(url)
    if not anuncios:
        log(f"  Sem anúncios encontrados.")
        return 0

    log(f"  {len(anuncios)} anúncio(s) recolhido(s).")
    alertas = 0

    for anuncio in anuncios:
        aid = anuncio["id"]

        if aid in vistos:
            continue

        vistos.append(aid)

        if anuncio["preco_num"] >= preco_max:
            continue

        poupanca = preco_max - anuncio["preco_num"]
        log(f"  🔥 {anuncio['titulo']} — {anuncio['preco_num']}€ (limite {preco_max}€, poupa {poupanca}€)")

        if enviar_telegram(montar_alerta(modelo, anuncio, preco_max)):
            alertas += 1
            log(f"  ✅ Alerta enviado.")
        else:
            log(f"  ❌ Falha ao enviar.")

        time.sleep(1)

    return alertas


def main():
    log("=" * 60)
    log("▶️  MONITOR DE iPHONES INICIADO")
    log(f"   {len(MODELOS)} modelos a monitorizar")
    log("=" * 60)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("❌ ERRO: Credenciais Telegram não definidas!")
        return

    vistos = carregar_vistos()
    total_alertas = 0

    for modelo, config in MODELOS.items():
        alertas = processar_modelo(modelo, config, vistos)
        total_alertas += alertas
        guardar_vistos(vistos)
        time.sleep(3)

    log("\n" + "=" * 60)
    log(f"✔️  CONCLUÍDO — {total_alertas} alerta(s) enviado(s).")
    log("=" * 60 + "\n")


if __name__ == "__main__":
    main()
