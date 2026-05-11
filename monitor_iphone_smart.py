"""
MONITOR DE iPHONES - OLX Portugal
So notifica anuncios publicados nos ultimos 8 minutos
(corre a cada 5 min via cron-job.org + GitHub Actions)
"""

import requests
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico.json"

# Anuncios com mais de X minutos sao ignorados
MINUTOS_MAXIMO = 8

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
    "iPhone 17":         "iphone 17",
    "iPhone 17 Pro":     "iphone 17 pro",
    "iPhone 17 Pro Max": "iphone 17 pro max",
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


def anuncio_e_recente(created_at_str):
    """
    Devolve True se o anuncio foi publicado nos ultimos MINUTOS_MAXIMO minutos.
    O OLX devolve timestamps em formato ISO 8601, ex: "2026-05-11T15:30:00+00:00"
    """
    if not created_at_str:
        # Se nao tem timestamp, aceita (nao queremos perder anuncios)
        return True
    try:
        # Parse do timestamp com timezone
        ts = created_at_str.replace("Z", "+00:00")
        criado_em = datetime.fromisoformat(ts)

        # Hora atual em UTC
        agora = datetime.now(timezone.utc)

        # Diferenca em minutos
        diff = (agora - criado_em).total_seconds() / 60

        log("  Publicado ha " + str(round(diff, 1)) + " min")
        return diff <= MINUTOS_MAXIMO

    except Exception as e:
        log("  Erro ao ler timestamp (" + str(created_at_str) + "): " + str(e))
        return True  # Em caso de erro, aceita o anuncio


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


def montar_mensagem(modelo, titulo, preco, link, minutos):
    preco_txt = str(preco) + "\u20ac" if preco else "Preco nao indicado"
    tempo_txt = str(round(minutos, 0)) + " min atras" if minutos is not None else "Agora"
    return (
        "\U0001f195 <b>NOVO ANUNCIO OLX!</b>\n\n"
        "\U0001f4f1 <b>Modelo:</b> " + modelo + "\n"
        "\U0001f4cc <b>" + titulo + "</b>\n"
        "\U0001f4b6 <b>Preco:</b> " + preco_txt + "\n"
        "\U0001f55b <b>Publicado:</b> " + tempo_txt + "\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver anuncio no OLX</a>"
    )


# ----------------------------------------------------------------------
# METODO 1: API interna OLX
# ----------------------------------------------------------------------

def buscar_api(query):
    url = ("https://www.olx.pt/api/v1/offers/"
           "?offset=0&limit=40"
           "&query=" + quote(query) +
           "&currency=EUR"
           "&sort_by=created_at%3Adesc")  # Ordena do mais recente para o mais antigo
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
                created_at = o.get("created_at") or o.get("last_refresh_time", "")

                preco = None
                for p in o.get("params", []):
                    if "price" in str(p.get("key", "")).lower():
                        preco = extrair_preco(p.get("value", {}).get("value", ""))
                        break
                if preco is None:
                    p_raw = o.get("price", {})
                    preco = extrair_preco(p_raw.get("value") if isinstance(p_raw, dict) else p_raw)

                if titulo and link and aid:
                    anuncios.append({
                        "id": aid,
                        "titulo": titulo,
                        "preco": preco,
                        "link": link,
                        "created_at": created_at,
                    })
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

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            r.text, re.DOTALL
        )
        if not match:
            log("  __NEXT_DATA__ nao encontrado")
            return None

        data = json.loads(match.group(1))
        log("  __NEXT_DATA__ encontrado!")

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
        anuncios = []
        for ad in ads:
            try:
                titulo = ad.get("title", "")
                link = ad.get("url", "")
                aid = str(ad.get("id", ""))
                created_at = ad.get("created_at") or ad.get("last_refresh_time", "")

                preco = None
                p_raw = ad.get("price", {})
                if isinstance(p_raw, dict):
                    preco = extrair_preco(p_raw.get("value") or p_raw.get("regularPrice", {}).get("value"))
                else:
                    preco = extrair_preco(p_raw)

                if titulo and link and aid:
                    anuncios.append({
                        "id": aid,
                        "titulo": titulo,
                        "preco": preco,
                        "link": link,
                        "created_at": created_at,
                    })
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

    for anuncio in anuncios:
        aid = str(anuncio["id"])

        # Ja visto antes?
        if aid in historico:
            continue

        # Marca como visto SEMPRE (mesmo que nao notifique)
        historico.append(aid)

        # Verifica se foi publicado nos ultimos MINUTOS_MAXIMO minutos
        created_at = anuncio.get("created_at", "")
        recente = anuncio_e_recente(created_at)

        if not recente:
            log("  Ignorado (muito antigo): " + anuncio["titulo"])
            continue

        # Calcula minutos para mostrar na mensagem
        minutos = None
        try:
            ts = created_at.replace("Z", "+00:00")
            criado_em = datetime.fromisoformat(ts)
            minutos = (datetime.now(timezone.utc) - criado_em).total_seconds() / 60
        except Exception:
            pass

        msg = montar_mensagem(modelo, anuncio["titulo"], anuncio["preco"], anuncio["link"], minutos)
        if enviar_telegram(msg):
            enviados += 1
            log("  Enviado: " + anuncio["titulo"])
        else:
            log("  Falha Telegram.")

        time.sleep(1)

    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 50)
    log("MONITOR iPHONES - anuncios dos ultimos " + str(MINUTOS_MAXIMO) + " min")
    log(str(len(MODELOS)) + " modelos")
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
