"""
MONITOR DE iPHONES - OLX Portugal
Envia notificacao para TODOS os anuncios novos (sem filtro de preco)
"""

import requests
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import quote


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico.json"

MODELOS = {
    "iPhone 14":         "iphone 14",
    "iPhone 14 Pro":     "iphone 14 pro",
    "iPhone 14 Pro Max": "iphone 14 pro max",
    "iPhone 15":         "iphone 15",
    "iPhone 15 Pro":     "iphone 15 pro",
    "iPhone 15 Pro Max": "iphone 15 pro max",
    "iPhone 16":         "iphone 16",
    "iPhone 16 Pro":     "iphone 16 pro",
    "iPhone 16 Pro Max": "iphone 16 pro max",
}

# ======================================================================

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://www.olx.pt/",
}

HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
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
            return [str(i) for i in dados.get("vistos", [])]
        if isinstance(dados, list):
            return [str(i) for i in dados]
    except Exception:
        pass
    return []


def guardar_historico(historico):
    try:
        with open(FICHEIRO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump([str(i) for i in historico][-5000:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("Erro historico: " + str(e))


# ----------------------------------------------------------------------
# UTILS
# ----------------------------------------------------------------------

def log(msg):
    print("[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] " + str(msg))


def extrair_preco(valor):
    if not valor:
        return None
    limpo = re.sub(r"[^\d]", "", str(valor))
    try:
        v = int(limpo[:6])
        return v if 1 <= v <= 99999 else None
    except Exception:
        return None


# ----------------------------------------------------------------------
# TELEGRAM
# ----------------------------------------------------------------------

def enviar_telegram(texto):
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=10)
        return r.ok
    except Exception as e:
        log("Telegram erro: " + str(e))
        return False


def montar_mensagem(modelo, titulo, preco, link):
    preco_txt = str(preco) + "\u20ac" if preco else "Preco nao indicado"
    return (
        "\U0001f4f1 <b>Novo anuncio OLX!</b>\n\n"
        "\U0001f50d <b>Modelo:</b> " + modelo + "\n"
        "\U0001f4cc <b>" + titulo + "</b>\n"
        "\U0001f4b6 <b>Preco:</b> " + preco_txt + "\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver anuncio no OLX</a>"
    )


# ----------------------------------------------------------------------
# METODO 1: API interna OLX
# ----------------------------------------------------------------------

def buscar_api(query):
    url = "https://www.olx.pt/api/v1/offers/?offset=0&limit=40&query=" + quote(query) + "&currency=EUR"
    try:
        r = requests.get(url, headers=HEADERS_API, timeout=15)
        log("  API: HTTP " + str(r.status_code))
        if r.status_code != 200:
            return None
        data = r.json()
        ofertas = data.get("data", [])
        log("  API: " + str(len(ofertas)) + " ofertas recebidas")
        anuncios = []
        for o in ofertas:
            try:
                titulo = o.get("title", "")
                link = o.get("url", "")
                aid = str(o.get("id", ""))
                preco = None
                for p in o.get("params", []):
                    if "price" in str(p.get("key", "")).lower():
                        preco = extrair_preco(p.get("value", {}).get("value", ""))
                        break
                if preco is None:
                    preco = extrair_preco(o.get("price", {}).get("value", "") if isinstance(o.get("price"), dict) else o.get("price", ""))
                if titulo and link and aid:
                    anuncios.append({"id": aid, "titulo": titulo, "preco": preco, "link": link})
            except Exception:
                pass
        return anuncios
    except Exception as e:
        log("  API erro: " + str(e))
        return None


# ----------------------------------------------------------------------
# METODO 2: __NEXT_DATA__ no HTML
# ----------------------------------------------------------------------

def buscar_nextdata(query):
    slug = query.replace(" ", "-")
    url = "https://www.olx.pt/ads/q-" + slug + "/"
    try:
        r = requests.get(url, headers=HEADERS_HTML, timeout=20)
        log("  HTML: HTTP " + str(r.status_code))
        if r.status_code != 200:
            return None
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
        if not match:
            log("  __NEXT_DATA__ nao encontrado")
            # Debug: mostra primeiros 300 chars do HTML
            log("  HTML inicio: " + r.text[:300].replace("\n", " "))
            return None
        data = json.loads(match.group(1))
        log("  __NEXT_DATA__ encontrado!")
        anuncios = []
        # Tenta varios caminhos no JSON
        ads = []
        try:
            pp = data["props"]["pageProps"]
            ads = (pp.get("ads") or
                   pp.get("listing", {}).get("ads") or
                   pp.get("initialState", {}).get("listing", {}).get("listing", {}).get("ads") or
                   [])
        except Exception:
            pass
        log("  Anuncios no JSON: " + str(len(ads)))
        for ad in ads:
            try:
                titulo = ad.get("title", "")
                link = ad.get("url", "")
                aid = str(ad.get("id", ""))
                preco = None
                p_raw = ad.get("price", {})
                if isinstance(p_raw, dict):
                    preco = extrair_preco(p_raw.get("value") or p_raw.get("regularPrice", {}).get("value"))
                else:
                    preco = extrair_preco(p_raw)
                if titulo and link and aid:
                    anuncios.append({"id": aid, "titulo": titulo, "preco": preco, "link": link})
            except Exception:
                pass
        return anuncios
    except Exception as e:
        log("  HTML erro: " + str(e))
        return None


# ----------------------------------------------------------------------
# PROCESSAMENTO
# ----------------------------------------------------------------------

def processar_modelo(modelo, query, historico):
    log("--- " + modelo + " ---")

    anuncios = buscar_api(query)
    if anuncios is None:
        log("  API falhou, a tentar HTML...")
        anuncios = buscar_nextdata(query)

    if not anuncios:
        log("  Sem anuncios encontrados.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s) encontrado(s).")
    enviados = 0
    novos = 0

    for anuncio in anuncios:
        aid = str(anuncio["id"])

        if aid in historico:
            continue

        historico.append(aid)
        novos += 1

        # Envia para TODOS os anuncios novos
        msg = montar_mensagem(modelo, anuncio["titulo"], anuncio["preco"], anuncio["link"])
        if enviar_telegram(msg):
            enviados += 1
            log("  Enviado: " + anuncio["titulo"] + " | " + str(anuncio["preco"]) + "eur")
        else:
            log("  Falha Telegram: " + anuncio["titulo"])

        time.sleep(1)

    log("  Novos: " + str(novos) + " | Enviados: " + str(enviados))
    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 50)
    log("MONITOR DE iPHONES - TODOS OS ANUNCIOS")
    log(str(len(MODELOS)) + " modelos a monitorizar")
    log("=" * 50)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("ERRO: Credenciais Telegram nao definidas!")
        return

    historico = carregar_historico()
    log("Historico: " + str(len(historico)) + " anuncios ja vistos.")

    total = 0
    for modelo, query in MODELOS.items():
        try:
            total += processar_modelo(modelo, query, historico)
        except Exception as e:
            log("Erro em " + modelo + ": " + str(e))
        guardar_historico(historico)
        time.sleep(4)

    log("=" * 50)
    log("CONCLUIDO - " + str(total) + " notificacoes enviadas.")
    log("=" * 50)


if __name__ == "__main__":
    main()
