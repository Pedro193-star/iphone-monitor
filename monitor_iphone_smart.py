"""
MONITOR DE iPHONES - OLX Portugal
- So notifica anuncios publicados nos ultimos 8 minutos
- Calcula media de mercado dinamicamente
- Classifica cada anuncio vs a media
"""

import requests
import json
import os
import re
import time
import statistics
from datetime import datetime, timezone
from urllib.parse import quote


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico.json"
FICHEIRO_MEDIAS    = "medias.json"

# So notifica anuncios publicados nos ultimos X minutos
MINUTOS_MAXIMO = 6

# Quantas horas a media e valida antes de recalcular
HORAS_VALIDADE_MEDIA = 6

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
# MEDIAS
# ----------------------------------------------------------------------

def carregar_medias():
    if not os.path.exists(FICHEIRO_MEDIAS):
        return {}
    try:
        with open(FICHEIRO_MEDIAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_medias(medias):
    try:
        with open(FICHEIRO_MEDIAS, "w", encoding="utf-8") as f:
            json.dump(medias, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("Erro medias: " + str(e))


def obter_media(modelo, anuncios, medias):
    """
    Devolve a media de mercado para o modelo.
    Usa cache se ainda for valida (HORAS_VALIDADE_MEDIA).
    Caso contrario recalcula a partir dos anuncios atuais.
    """
    entrada = medias.get(modelo, {})
    timestamp = entrada.get("timestamp", "")
    valor = entrada.get("valor")

    # Verifica se a media em cache ainda e valida
    if timestamp and valor:
        try:
            guardada = datetime.fromisoformat(timestamp)
            horas = (datetime.now() - guardada).total_seconds() / 3600
            if horas < HORAS_VALIDADE_MEDIA:
                log("  Media em cache: " + str(round(valor)) + "eur (" + str(round(horas, 1)) + "h atras)")
                return valor
        except Exception:
            pass

    # Recalcula com os anuncios atuais
    precos = [a["preco"] for a in anuncios if a.get("preco") and 50 <= a["preco"] <= 5000]

    if len(precos) < 3:
        log("  Amostras insuficientes para calcular media (" + str(len(precos)) + ")")
        return valor  # Usa o valor antigo se houver

    # Remove outliers (fora de 2 desvios padrao)
    media_bruta = statistics.mean(precos)
    if len(precos) > 2:
        desvio = statistics.stdev(precos)
        precos = [p for p in precos if abs(p - media_bruta) <= 2 * desvio]

    nova_media = round(statistics.median(precos), 2)
    medias[modelo] = {
        "valor": nova_media,
        "amostras": len(precos),
        "timestamp": datetime.now().isoformat(),
    }
    log("  Media calculada: " + str(nova_media) + "eur (" + str(len(precos)) + " amostras)")
    return nova_media


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


def minutos_desde(created_at_str):
    """Devolve quantos minutos passaram desde created_at, ou None se falhar."""
    if not created_at_str:
        return None
    try:
        ts = created_at_str.replace("Z", "+00:00")
        criado_em = datetime.fromisoformat(ts)
        return (datetime.now(timezone.utc) - criado_em).total_seconds() / 60
    except Exception:
        return None


def e_recente(created_at_str):
    mins = minutos_desde(created_at_str)
    if mins is None:
        return True  # sem timestamp, aceita
    return mins <= MINUTOS_MAXIMO


# ----------------------------------------------------------------------
# CLASSIFICACAO DO NEGOCIO
# ----------------------------------------------------------------------

def classificar(preco, media):
    """
    Devolve (icone, label, desconto_pct) com base na diferenca ao preco medio.
    """
    if media is None or media == 0:
        return "\U0001f4f1", "Sem media disponivel", None

    diff_pct = ((media - preco) / media) * 100  # positivo = abaixo da media

    if diff_pct >= 25:
        return "\U0001f525\U0001f525", "EXCELENTE DEAL", diff_pct
    elif diff_pct >= 15:
        return "\U0001f525", "BOM DEAL", diff_pct
    elif diff_pct >= 0:
        return "\U0001f7e1", "NA MEDIA — nao vale a pena", diff_pct
    else:
        return "\U0001f534", "ACIMA DA MEDIA — nao vale a pena", diff_pct


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


def montar_mensagem(modelo, titulo, preco, link, media, mins):
    icone, label, diff_pct = classificar(preco, media)
    preco_txt = str(preco) + "\u20ac" if preco else "Nao indicado"
    media_txt = str(round(media)) + "\u20ac" if media else "N/D"
    tempo_txt = str(round(mins)) + " min atras" if mins is not None else "Agora"

    if diff_pct is not None:
        diff_txt = ("-" if diff_pct >= 0 else "+") + str(round(abs(diff_pct), 1)) + "% vs media"
    else:
        diff_txt = ""

    msg = (
        icone + " <b>" + label + "</b>\n\n"
        "\U0001f4f1 <b>Modelo:</b> " + modelo + "\n"
        "\U0001f4cc <b>" + titulo + "</b>\n\n"
        "\U0001f4b6 <b>Preco:</b> " + preco_txt + "\n"
        "\U0001f4ca <b>Media mercado:</b> " + media_txt + "\n"
    )
    if diff_txt:
        msg += "\U0001f4c9 <b>Diferenca:</b> " + diff_txt + "\n"
    msg += (
        "\U0001f55b <b>Publicado:</b> " + tempo_txt + "\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver anuncio no OLX</a>"
    )
    return msg


# ----------------------------------------------------------------------
# SCRAPING OLX
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
            log("  __NEXT_DATA__ nao encontrado")
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
                created_at = ad.get("created_at") or ad.get("last_refresh_time", "")
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

def processar_modelo(modelo, query, historico, medias):
    log("--- " + modelo + " ---")

    anuncios = buscar_api(query)
    if anuncios is None:
        log("  API falhou, a tentar HTML...")
        anuncios = buscar_nextdata(query)

    if not anuncios:
        log("  Sem anuncios encontrados.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s) encontrado(s).")

    # Calcula/atualiza media de mercado com todos os anuncios da pagina
    media = obter_media(modelo, anuncios, medias)

    enviados = 0
    for anuncio in anuncios:
        aid = str(anuncio["id"])

        if aid in historico:
            continue
        historico.append(aid)

        # Filtra por tempo de publicacao
        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        preco = anuncio.get("preco")
        if not preco:
            continue

        log("  Novo: " + anuncio["titulo"] + " | " + str(preco) + "eur")

        msg = montar_mensagem(modelo, anuncio["titulo"], preco, anuncio["link"], media, mins)
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
    log("=" * 50)
    log("MONITOR iPHONES - ultimos " + str(MINUTOS_MAXIMO) + " min + classificacao")
    log(str(len(MODELOS)) + " modelos")
    log("=" * 50)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("ERRO: Credenciais Telegram nao definidas!")
        return

    historico = carregar_historico()
    medias = carregar_medias()
    log("Historico: " + str(len(historico)) + " anuncios ja vistos.")

    total = 0
    for modelo, query in MODELOS.items():
        try:
            total += processar_modelo(modelo, query, historico, medias)
        except Exception as e:
            log("Erro em " + modelo + ": " + str(e))
        guardar_historico(historico)
        guardar_medias(medias)
        time.sleep(4)

    log("=" * 50)
    log("CONCLUIDO - " + str(total) + " notificacoes enviadas.")
    log("=" * 50)


if __name__ == "__main__":
    main()
