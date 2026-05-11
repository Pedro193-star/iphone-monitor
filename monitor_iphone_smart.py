"""
MONITOR DE iPHONES - OLX Portugal
URLs corrigidos + headers melhorados para evitar bloqueios
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from datetime import datetime


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico.json"
PRECO_MINIMO_GLOBAL = 50

# ----------------------------------------------------------------------
# MODELOS - URLs corrigidos para o novo formato OLX Portugal
# ----------------------------------------------------------------------
MODELOS = {
    "iPhone 14":         {"preco_max": 300,  "url": "https://www.olx.pt/ads/q-iphone-14/"},
    "iPhone 14 Pro":     {"preco_max": 380,  "url": "https://www.olx.pt/ads/q-iphone-14-pro/"},
    "iPhone 14 Pro Max": {"preco_max": 420,  "url": "https://www.olx.pt/ads/q-iphone-14-pro-max/"},
    "iPhone 15":         {"preco_max": 450,  "url": "https://www.olx.pt/ads/q-iphone-15/"},
    "iPhone 15 Pro":     {"preco_max": 550,  "url": "https://www.olx.pt/ads/q-iphone-15-pro/"},
    "iPhone 15 Pro Max": {"preco_max": 620,  "url": "https://www.olx.pt/ads/q-iphone-15-pro-max/"},
    "iPhone 16":         {"preco_max": 600,  "url": "https://www.olx.pt/ads/q-iphone-16/"},
    "iPhone 16 Pro":     {"preco_max": 700,  "url": "https://www.olx.pt/ads/q-iphone-16-pro/"},
    "iPhone 16 Pro Max": {"preco_max": 800,  "url": "https://www.olx.pt/ads/q-iphone-16-pro-max/"},
    "iPhone 17":         {"preco_max": 750,  "url": "https://www.olx.pt/ads/q-iphone-17/"},
    "iPhone 17 Pro":     {"preco_max": 900,  "url": "https://www.olx.pt/ads/q-iphone-17-pro/"},
    "iPhone 17 Pro Max": {"preco_max": 1000, "url": "https://www.olx.pt/ads/q-iphone-17-pro-max/"},
}

# ======================================================================

# Headers que imitam um browser real para evitar bloqueios
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


# ----------------------------------------------------------------------
# HISTORICO
# ----------------------------------------------------------------------

def carregar_historico():
    if not os.path.exists(FICHEIRO_HISTORICO):
        return []
    try:
        with open(FICHEIRO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict):
            ids = dados.get("vistos", [])
        elif isinstance(dados, list):
            ids = dados
        else:
            ids = []
        return [str(i) for i in ids]
    except Exception:
        return []


def guardar_historico(historico):
    try:
        lista = [str(i) for i in historico][-5000:]
        with open(FICHEIRO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("Erro ao guardar historico: " + str(e))


# ----------------------------------------------------------------------
# UTILS
# ----------------------------------------------------------------------

def log(msg):
    print("[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] " + str(msg))


def extrair_preco(texto):
    if not texto:
        return None
    limpo = texto.strip().lower()
    if any(p in limpo for p in ["gratis", "grátis", "troca", "ver desc"]):
        return None
    sem_milhar = re.sub(r"\.(?=\d{3})", "", limpo)
    sem_decimal = re.sub(r",\d{1,2}$", "", sem_milhar)
    numeros = re.findall(r"\d+", sem_decimal)
    if numeros:
        try:
            return int(numeros[0])
        except Exception:
            return None
    return None


def extrair_id(link):
    match = re.search(r"ID(\w+)", link)
    if match:
        return match.group(1)
    return str(abs(hash(link)) % (10 ** 10))


# ----------------------------------------------------------------------
# TELEGRAM
# ----------------------------------------------------------------------

def enviar_telegram(texto):
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception as e:
        log("Telegram erro: " + str(e))
        return False


def montar_alerta(modelo, titulo, preco, preco_max, link):
    poupanca = preco_max - preco
    if poupanca > 150:
        icone = "\U0001f525\U0001f525"
        label = "NEGOCIO INCRIVEL"
    elif poupanca > 80:
        icone = "\U0001f525"
        label = "EXCELENTE NEGOCIO"
    else:
        icone = "\u2705"
        label = "BOM NEGOCIO"

    return (
        icone + " <b>" + label + "!</b>\n\n"
        "\U0001f4f1 <b>Modelo:</b> " + modelo + "\n"
        "\U0001f4cc <b>" + titulo + "</b>\n\n"
        "\U0001f4b6 <b>Preco:</b> " + str(preco) + "\u20ac\n"
        "\U0001f3af <b>Teu limite:</b> " + str(preco_max) + "\u20ac\n"
        "\U0001f4b0 <b>Poupas:</b> " + str(poupanca) + "\u20ac abaixo do limite\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver anuncio no OLX</a>"
    )


# ----------------------------------------------------------------------
# SCRAPING
# ----------------------------------------------------------------------

def scrape_olx(url):
    session = requests.Session()
    session.headers.update(HEADERS)

    # Visita a pagina principal primeiro (simula comportamento humano)
    try:
        session.get("https://www.olx.pt", timeout=15)
        time.sleep(2)
    except Exception:
        pass

    try:
        r = session.get(url, timeout=20)
        log("  HTTP " + str(r.status_code) + " — " + url)
        r.raise_for_status()
    except Exception as e:
        log("  Erro ao aceder OLX: " + str(e))
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Tenta varios seletores conhecidos do OLX
    cards = (
        soup.find_all("div", {"data-cy": "l-card"}) or
        soup.find_all("div", {"data-testid": "listing-grid-item"}) or
        soup.find_all("li", {"data-cy": "l-card"}) or
        soup.find_all("article") or
        soup.find_all("li", class_=re.compile(r"css-\w{5,}"))
    )

    log("  Cards encontrados: " + str(len(cards)))

    # Debug: mostra o titulo da pagina para confirmar que carregou
    title = soup.find("title")
    if title:
        log("  Pagina: " + title.get_text(strip=True)[:60])

    anuncios = []
    for card in cards:
        try:
            titulo_el = (
                card.find("h6") or card.find("h4") or card.find("h3") or
                card.find("h2") or
                card.find(class_=re.compile(r"title|titulo|name", re.I))
            )
            if not titulo_el:
                continue
            titulo = titulo_el.get_text(strip=True)
            if not titulo:
                continue

            link_el = card.find("a", href=True)
            if not link_el:
                continue
            link = link_el["href"]
            if not link.startswith("http"):
                link = "https://www.olx.pt" + link
            link = link.split("?")[0]

            anuncio_id = extrair_id(link)

            preco_el = (
                card.find("p", {"data-testid": "ad-price"}) or
                card.find("p", class_=re.compile(r"price|Price", re.I)) or
                card.find("span", class_=re.compile(r"price|Price", re.I)) or
                card.find("strong")
            )
            preco_texto = preco_el.get_text(strip=True) if preco_el else ""
            preco_num = extrair_preco(preco_texto)

            if preco_num is None:
                continue

            anuncios.append({
                "id": anuncio_id,
                "titulo": titulo,
                "preco": preco_num,
                "link": link,
            })
        except Exception as e:
            log("  Erro num card: " + str(e))

    return anuncios


# ----------------------------------------------------------------------
# PROCESSAMENTO
# ----------------------------------------------------------------------

def processar_modelo(modelo, config, historico):
    preco_max = config["preco_max"]
    url = config["url"]

    log("--- " + modelo + " | max: " + str(preco_max) + "eur ---")

    anuncios = scrape_olx(url)
    if not anuncios:
        log("  Nenhum anuncio valido encontrado.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s) com preco valido.")
    alertas = 0

    for anuncio in anuncios:
        aid = str(anuncio["id"])
        preco = anuncio["preco"]

        if aid in historico:
            continue

        historico.append(aid)

        if preco < PRECO_MINIMO_GLOBAL:
            log("  Ignorado (acessorio " + str(preco) + "eur): " + anuncio["titulo"])
            continue

        if preco >= preco_max:
            continue

        poupanca = preco_max - preco
        log("  NEGOCIO: " + anuncio["titulo"] + " | " + str(preco) + "eur (poupa " + str(poupanca) + "eur)")

        msg = montar_alerta(modelo, anuncio["titulo"], preco, preco_max, anuncio["link"])
        if enviar_telegram(msg):
            alertas += 1
            log("  Alerta enviado!")
        else:
            log("  Falha ao enviar alerta.")

        time.sleep(1)

    return alertas


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 50)
    log("MONITOR DE iPHONES INICIADO")
    log(str(len(MODELOS)) + " modelos | minimo: " + str(PRECO_MINIMO_GLOBAL) + "eur")
    log("=" * 50)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("ERRO: Credenciais Telegram nao definidas!")
        return

    historico = carregar_historico()
    log("Historico: " + str(len(historico)) + " anuncios ja vistos.")

    total_alertas = 0

    for modelo, config in MODELOS.items():
        try:
            alertas = processar_modelo(modelo, config, historico)
            total_alertas += alertas
        except Exception as e:
            log("Erro em " + modelo + ": " + str(e))
        guardar_historico(historico)
        time.sleep(4)

    log("=" * 50)
    log("CONCLUIDO - " + str(total_alertas) + " alerta(s) enviado(s).")
    log("Historico: " + str(len(historico)) + " anuncios no total.")
    log("=" * 50)


if __name__ == "__main__":
    main()
