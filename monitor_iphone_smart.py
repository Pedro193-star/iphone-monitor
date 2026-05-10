"""
MONITOR DE iPHONES - OLX Portugal
Notifica quando o preco esta abaixo do teu limite maximo
e acima de 50 euros (filtra capas e acessorios)
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from datetime import datetime


# ======================================================================
#  CONFIGURACOES - EDITA APENAS ESTA SECCAO
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico.json"

PRECO_MINIMO_GLOBAL = 50  # Filtra capas, peliculas e acessorios

# ----------------------------------------------------------------------
# MODELOS A MONITORIZAR
# Altera apenas o "preco_max" de cada modelo ao teu gosto
# ----------------------------------------------------------------------
MODELOS = {
    "iPhone 14":         {"preco_max": 300,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14/"},
    "iPhone 14 Pro":     {"preco_max": 380,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14-pro/"},
    "iPhone 14 Pro Max": {"preco_max": 420,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14-pro-max/"},
    "iPhone 15":         {"preco_max": 450,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15/"},
    "iPhone 15 Pro":     {"preco_max": 550,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15-pro/"},
    "iPhone 15 Pro Max": {"preco_max": 620,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15-pro-max/"},
    "iPhone 16":         {"preco_max": 600,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16/"},
    "iPhone 16 Pro":     {"preco_max": 700,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16-pro/"},
    "iPhone 16 Pro Max": {"preco_max": 800,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16-pro-max/"},
    "iPhone 17":         {"preco_max": 750,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17/"},
    "iPhone 17 Pro":     {"preco_max": 900,  "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17-pro/"},
    "iPhone 17 Pro Max": {"preco_max": 1000, "url": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17-pro-max/"},
}

# ======================================================================
#  FIM DAS CONFIGURACOES
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


# ----------------------------------------------------------------------
# HISTORICO  — garante que e sempre uma lista simples de strings
# ----------------------------------------------------------------------

def carregar_historico():
    if not os.path.exists(FICHEIRO_HISTORICO):
        return []
    try:
        with open(FICHEIRO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        # Compatibilidade: se vier um dict do script antigo, extrai a lista
        if isinstance(dados, dict):
            ids = dados.get("vistos", [])
        elif isinstance(dados, list):
            ids = dados
        else:
            ids = []
        # Garante que todos os elementos sao strings
        return [str(i) for i in ids]
    except Exception:
        return []


def guardar_historico(historico):
    try:
        # Guarda apenas os ultimos 5000 (lista simples de strings)
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
        "\U0001f4b0 <b>Poupas:</b> " + str(poupanca) + "\u20ac abaixo do teu limite\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver anuncio no OLX</a>"
    )


# ----------------------------------------------------------------------
# SCRAPING
# ----------------------------------------------------------------------

def scrape_olx(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        log("  Erro ao aceder OLX: " + str(e))
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

    log("Verificar: " + modelo + " | max: " + str(preco_max) + "eur")

    anuncios = scrape_olx(url)
    if not anuncios:
        log("  Sem anuncios encontrados.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s) recolhido(s).")
    alertas = 0

    for anuncio in anuncios:
        aid = str(anuncio["id"])
        preco = anuncio["preco"]

        # Ja foi visto antes?
        if aid in historico:
            continue

        # Marca sempre como visto
        historico.append(aid)

        # Filtra acessorios e capas (abaixo do minimo global)
        if preco < PRECO_MINIMO_GLOBAL:
            log("  Ignorado (capa/acessorio " + str(preco) + "eur): " + anuncio["titulo"])
            continue

        # Nao e negocio suficiente
        if preco >= preco_max:
            continue

        poupanca = preco_max - preco
        log("  NEGOCIO: " + anuncio["titulo"] + " | " + str(preco) + "eur (poupa " + str(poupanca) + "eur)")

        msg = montar_alerta(modelo, anuncio["titulo"], preco, preco_max, anuncio["link"])
        if enviar_telegram(msg):
            alertas += 1
            log("  Alerta Telegram enviado.")
        else:
            log("  Falha ao enviar Telegram.")

        time.sleep(1)

    return alertas


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 50)
    log("MONITOR DE iPHONES INICIADO")
    log(str(len(MODELOS)) + " modelos | minimo global: " + str(PRECO_MINIMO_GLOBAL) + "eur")
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
            log("Erro ao processar " + modelo + ": " + str(e))
        guardar_historico(historico)
        time.sleep(3)

    log("=" * 50)
    log("CONCLUIDO - " + str(total_alertas) + " alerta(s) enviado(s).")
    log("Historico: " + str(len(historico)) + " anuncios no total.")
    log("=" * 50)


if __name__ == "__main__":
    main()
