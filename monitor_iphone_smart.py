"""
MONITOR DE iPHONES - OLX Portugal
- So notifica anuncios publicados nos ultimos 8 minutos
- Compara preco com tabela de referencia por modelo e storage
- Classifica: Excelente Negocio / Muito Bom Deal / Acima do Ideal
"""

import requests
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico.json"
MINUTOS_MAXIMO     = 8

# Filtra acessorios/spam se preco for 85%+ abaixo da referencia media
FILTRO_ACESSORIO_PCT = 85

# Margem acima da referencia para "negociar" (em %)
MARGEM_ACIMA = 5

# Margem abaixo da referencia para "excelente negocio" (em %)
MARGEM_ABAIXO = 10


# ======================================================================
#  TABELA DE PRECOS DE REFERENCIA (mercado usado PT)
# ======================================================================

PRECOS = {
    "iPhone 13 Mini": {
        128: 154, 256: 227, 512: 353,
    },
    "iPhone 13": {
        128: 195, 256: 236, 512: 300,
    },
    "iPhone 13 Pro": {
        128: 302, 256: 332, 512: 368, 1024: 434,
    },
    "iPhone 13 Pro Max": {
        128: 309, 256: 349, 512: 389, 1024: 464,
    },
    "iPhone 14": {
        128: 247, 256: 304, 512: 391,
    },
    "iPhone 14 Plus": {
        128: 298, 256: 347, 512: 417,
    },
    "iPhone 14 Pro": {
        128: 390, 256: 428, 512: 502, 1024: 533,
    },
    "iPhone 14 Pro Max": {
        128: 436, 256: 474, 512: 547, 1024: 611,
    },
    "iPhone 15": {
        128: 370, 256: 440, 512: 515,
    },
    "iPhone 15 Plus": {
        128: 381, 256: 467, 512: 580,
    },
    "iPhone 15 Pro": {
        128: 470, 256: 520, 512: 569, 1024: 670,
    },
    "iPhone 15 Pro Max": {
        256: 551, 512: 605, 1024: 630,
    },
    "iPhone 16": {
        256: 511, 512: 604, 1024: 670,
    },
    "iPhone 16e": {
        128: 355, 256: 429, 512: 535,
    },
    "iPhone 16 Plus": {
        128: 545, 256: 640, 512: 725,
    },
    "iPhone 16 Pro": {
        128: 667, 256: 702, 512: 820, 1024: 930,
    },
    "iPhone 16 Pro Max": {
        256: 746, 512: 831, 1024: 960,
    },
}

# ======================================================================
#  MODELOS A MONITORIZAR
# ======================================================================

MODELOS = {
    "iPhone 13 Mini":    "iphone 13 mini",
    "iPhone 13":         "iphone 13",
    "iPhone 13 Pro":     "iphone 13 pro",
    "iPhone 13 Pro Max": "iphone 13 pro max",
    "iPhone 14":         "iphone 14",
    "iPhone 14 Plus":    "iphone 14 plus",
    "iPhone 14 Pro":     "iphone 14 pro",
    "iPhone 14 Pro Max": "iphone 14 pro max",
    "iPhone 15":         "iphone 15",
    "iPhone 15 Plus":    "iphone 15 plus",
    "iPhone 15 Pro":     "iphone 15 pro",
    "iPhone 15 Pro Max": "iphone 15 pro max",
    "iPhone 16":         "iphone 16",
    "iPhone 16e":        "iphone 16e",
    "iPhone 16 Plus":    "iphone 16 plus",
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


def extrair_storage(titulo):
    """Extrai a capacidade de armazenamento do titulo do anuncio."""
    t = titulo.lower()
    if "1024" in t or "1 024" in t or "1tb" in t or "1 tb" in t:
        return 1024
    if "512" in t:
        return 512
    if "256" in t:
        return 256
    if "128" in t:
        return 128
    if "64" in t:
        return 64
    return None


def obter_preco_ref(modelo, storage):
    """
    Devolve o preco de referencia para o modelo e storage.
    Se o storage nao for reconhecido, usa a media de todos os storages.
    """
    tabela = PRECOS.get(modelo)
    if not tabela:
        return None
    if storage and storage in tabela:
        return tabela[storage]
    return round(sum(tabela.values()) / len(tabela))


def minutos_desde(created_at_str):
    if not created_at_str:
        return None
    try:
        ts = str(created_at_str).replace("Z", "+00:00")
        criado_em = datetime.fromisoformat(ts)
        return (datetime.now(timezone.utc) - criado_em).total_seconds() / 60
    except Exception:
        return None


# ----------------------------------------------------------------------
# CLASSIFICACAO
# ----------------------------------------------------------------------

def classificar(preco, preco_ref):
    """
    > MARGEM_ACIMA% acima  -> Acima do ideal, negoceia
    dentro de +-margem     -> Muito bom deal
    > MARGEM_ABAIXO% baixo -> Excelente negocio
    """
    if preco_ref is None:
        return "\U0001f4f1", "SEM REFERENCIA", None

    diff_pct = ((preco_ref - preco) / preco_ref) * 100  # positivo = abaixo da ref

    if diff_pct >= MARGEM_ABAIXO:
        return "\U0001f525\U0001f525", "EXCELENTE NEGOCIO", diff_pct
    elif diff_pct >= -MARGEM_ACIMA:
        return "\u2705", "MUITO BOM DEAL", diff_pct
    else:
        return "\U0001f7e1", "ACIMA DO IDEAL - tenta negociar", diff_pct


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


def montar_mensagem(modelo, titulo, preco, link, storage, icone, label, diff_pct, preco_ref, mins):
    preco_txt   = str(preco) + "\u20ac"
    ref_txt     = str(preco_ref) + "\u20ac" if preco_ref else "N/D"
    storage_txt = str(storage) + "GB" if storage else "storage desconhecido"
    tempo_txt   = str(round(mins)) + " min atras" if mins is not None else "Agora"

    if diff_pct is not None:
        sinal    = "-" if diff_pct >= 0 else "+"
        diff_txt = sinal + str(round(abs(diff_pct), 1)) + "% vs referencia"
    else:
        diff_txt = ""

    msg = (
        icone + " <b>" + label + "</b>\n\n"
        "\U0001f4f1 <b>" + modelo + "</b> | " + storage_txt + "\n"
        "\U0001f4cc <b>" + titulo + "</b>\n\n"
        "\U0001f4b6 <b>Preco anuncio:</b> " + preco_txt + "\n"
        "\U0001f3af <b>Preco referencia:</b> " + ref_txt + "\n"
    )
    if diff_txt:
        msg += "\U0001f4c9 <b>Diferenca:</b> " + diff_txt + "\n"
    msg += (
        "\U0001f55b <b>Publicado:</b> " + tempo_txt + "\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver anuncio no OLX</a>"
    )
    return msg


# ----------------------------------------------------------------------
# SCRAPING
# ----------------------------------------------------------------------

def buscar_api(query):
    url = ("https://www.olx.pt/api/v1/offers/"
           "?offset=0&limit=40"
           "&query=" + quote(query) +
           "&currency=EUR"
           "&sort_by=created_at%3Adesc")
    try:
        r = requests.get(url, headers=HEADERS_API, timeout=15)
        log("  API: HTTP " + str(r.status_code))
        if r.status_code != 200:
            return None
        data = r.json()
        ofertas = data.get("data", [])
        log("  API: " + str(len(ofertas)) + " ofertas")
        anuncios = []
        for o in ofertas:
            try:
                titulo = o.get("title", "")
                link = o.get("url", "")
                aid = str(o.get("id", ""))
                created_at = o.get("created_at") or o.get("last_refresh_time") or o.get("pushup_time") or ""
                preco = None
                for p in o.get("params", []):
                    if "price" in str(p.get("key", "")).lower():
                        preco = extrair_preco(p.get("value", {}).get("value", ""))
                        break
                if preco is None:
                    p_raw = o.get("price", {})
                    preco = extrair_preco(p_raw.get("value") if isinstance(p_raw, dict) else p_raw)
                if titulo and link and aid:
                    anuncios.append({"id": aid, "titulo": titulo, "preco": preco, "link": link, "created_at": created_at})
            except Exception:
                pass
        return anuncios
    except Exception as e:
        log("  API erro: " + str(e))
        return None


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
            return None
        data = json.loads(match.group(1))
        ads = []
        try:
            pp = data["props"]["pageProps"]
            ads = (pp.get("ads") or pp.get("listing", {}).get("ads") or
                   pp.get("initialState", {}).get("listing", {}).get("listing", {}).get("ads") or [])
        except Exception:
            pass
        log("  HTML: " + str(len(ads)) + " anuncios")
        anuncios = []
        for ad in ads:
            try:
                titulo = ad.get("title", "")
                link = ad.get("url", "")
                aid = str(ad.get("id", ""))
                created_at = ad.get("created_at") or ad.get("last_refresh_time") or ""
                preco = None
                p_raw = ad.get("price", {})
                if isinstance(p_raw, dict):
                    preco = extrair_preco(p_raw.get("value") or p_raw.get("regularPrice", {}).get("value"))
                else:
                    preco = extrair_preco(p_raw)
                if titulo and link and aid:
                    anuncios.append({"id": aid, "titulo": titulo, "preco": preco, "link": link, "created_at": created_at})
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
        log("  Sem anuncios.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s)")

    tabela = PRECOS.get(modelo, {})
    ref_media = round(sum(tabela.values()) / len(tabela)) if tabela else None

    enviados = 0

    for anuncio in anuncios:
        aid = str(anuncio["id"])

        if aid in historico:
            continue
        historico.append(aid)

        # Filtro de tempo
        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        preco = anuncio.get("preco")
        if not preco:
            continue

        # Filtro de acessorios
        if ref_media and ((ref_media - preco) / ref_media) * 100 >= FILTRO_ACESSORIO_PCT:
            log("  Ignorado (acessorio " + str(preco) + "eur): " + anuncio["titulo"][:40])
            continue

        # Detecta storage e obtem preco de referencia
        storage = extrair_storage(anuncio["titulo"])
        preco_ref = obter_preco_ref(modelo, storage)

        icone, label, diff_pct = classificar(preco, preco_ref)

        log("  " + label + ": " + anuncio["titulo"][:40] + " | " + str(preco) + "eur (ref: " + str(preco_ref) + "eur)")

        msg = montar_mensagem(modelo, anuncio["titulo"], preco, anuncio["link"],
                              storage, icone, label, diff_pct, preco_ref, mins)
        if enviar_telegram(msg):
            enviados += 1
            log("  Telegram enviado.")
        else:
            log("  Falha Telegram.")
        time.sleep(1)

    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 55)
    log("MONITOR iPHONES - ultimos " + str(MINUTOS_MAXIMO) + " min + tabela de precos")
    log(str(len(MODELOS)) + " modelos monitorizados")
    log("=" * 55)

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

    log("=" * 55)
    log("CONCLUIDO - " + str(total) + " notificacoes enviadas.")
    log("=" * 55)


if __name__ == "__main__":
    main()
