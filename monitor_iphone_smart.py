"""
OLX TRACKER — Monitor de iPhones v3
Melhorias:
  - Tabela de preços com 3 colunas: iServices / Comprar / Vender
  - Leitura de descrição: bateria, danos, filtros de qualidade
  - Filtro: bateria >= 84%, sem peças, sem eSIM-only, desbloqueado
  - iPhone 12 Pro Max adicionado
  - Detecção rigorosa de modelo pelo título
"""

import requests
import json
import os
import re
import time
import math
from datetime import datetime, timezone
from urllib.parse import quote


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO   = "historico.json"
MINUTOS_MAXIMO       = 60
FILTRO_ACESSORIO_PCT = 60    # Ignora se preço < 40% do iServices

# Localização — Centro: Algés | Raio: 20km
CENTRO_LAT = 38.7057
CENTRO_LON = -9.2311
RAIO_KM    = 20

LOCAIS_ACEITES = [
    "lisboa", "lisbon", "alges", "algés", "oeiras", "cascais",
    "amadora", "odivelas", "loures", "sintra", "almada", "seixal",
    "barreiro", "estoril", "belem", "belém", "ajuda", "benfica",
    "carnaxide", "queijas", "linda-a-velha", "porto salvo",
    "paco de arcos", "paço de arcos", "caxias", "barcarena",
    "monte estoril", "alcabideche", "queluz", "massamá", "massama",
    "damaia", "pontinha", "sacavém", "sacavem", "moscavide",
    "olivais", "oriente", "parque das nacoes", "parque das nações",
    "mafra", "sesimbra", "palmela", "setúbal", "setubal",
]

# Palavras proibidas no TÍTULO
PALAVRAS_EXCLUIDAS = [
    "capa", "capas", "capinha", "capinhas",
    "pelicula", "peliculas", "película", "películas",
    "ecra", "ecras", "ecrã", "ecrãs", "display",
    "bateria", "baterias", "pecas", "peças",
    "caixa", "vazia", "vazio",
    "avariado", "avariada", "avaria",
    "partido", "partida",
    "bloqueado", "bloqueada",
    "icloud",
]

BATERIA_MINIMA = 84   # Rejeita se bateria < 84%


# ======================================================================
#  TABELA DE PRECOS — 3 colunas por storage
#  "is"  = iServices (preço de referência rápida)
#  "buy" = Comprar/negociar (preço alvo de compra)
#  "sel" = Vender (preço de venda esperado)
#  Condições: como novo, bateria 84-95%, desbloqueado
# ======================================================================

PRECOS = {
    "iPhone 12 Pro Max": {
        128:  {"is": 220, "buy": 240, "sel": 295},
        256:  {"is": 260, "buy": 270, "sel": 310},
        512:  {"is": 340, "buy": 320, "sel": 350},
    },
    "iPhone 13 Mini": {
        128:  {"is": 155, "buy": 210, "sel": 250},
        256:  {"is": 180, "buy": 220, "sel": 260},
    },
    "iPhone 13": {
        128:  {"is": 190, "buy": 230, "sel": 290},
        256:  {"is": 210, "buy": 240, "sel": 300},
        512:  {"is": 230, "buy": 250, "sel": 300},
    },
    "iPhone 13 Pro": {
        128:  {"is": 250, "buy": 270, "sel": 310},
        256:  {"is": 260, "buy": 280, "sel": 340},
        512:  {"is": 320, "buy": 390, "sel": 450},
    },
    "iPhone 13 Pro Max": {
        128:  {"is": 300, "buy": 350, "sel": 400},
        256:  {"is": 320, "buy": 360, "sel": 400},
        512:  {"is": 350, "buy": 440, "sel": 500},
    },
    "iPhone 14": {
        128:  {"is": 200, "buy": 250, "sel": 330},
        256:  {"is": 240, "buy": 300, "sel": 360},
        512:  {"is": 360, "buy": 380, "sel": 430},
    },
    "iPhone 14 Plus": {
        128:  {"is": 220, "buy": 280, "sel": 330},
        256:  {"is": 280, "buy": 300, "sel": 360},
    },
    "iPhone 14 Pro": {
        128:  {"is": 280, "buy": 310, "sel": 380},
        256:  {"is": 300, "buy": 360, "sel": 430},
        512:  {"is": 350, "buy": 420, "sel": 470},
    },
    "iPhone 14 Pro Max": {
        128:  {"is": 330, "buy": 390, "sel": 430},
        256:  {"is": 370, "buy": 400, "sel": 440},
        512:  {"is": 380, "buy": 460, "sel": 570},
        1024: {"is": 630, "buy": 480, "sel": 650},
    },
    "iPhone 15": {
        128:  {"is": 300, "buy": 430, "sel": 470},
        256:  {"is": 340, "buy": 450, "sel": 530},
        512:  {"is": 280, "buy": 360, "sel": 420},
    },
    "iPhone 15 Plus": {
        128:  {"is": 290, "buy": 430, "sel": 510},
        256:  {"is": 330, "buy": 490, "sel": 590},
        512:  {"is": 420, "buy": None, "sel": None},
    },
    "iPhone 15 Pro": {
        128:  {"is": 370, "buy": 470, "sel": 520},
        256:  {"is": 430, "buy": 520, "sel": 600},
        512:  {"is": 530, "buy": 600, "sel": 700},
        1024: {"is": 690, "buy": 720, "sel": 800},
    },
    "iPhone 15 Pro Max": {
        256:  {"is": 460, "buy": 500, "sel": 580},
        512:  {"is": 650, "buy": 700, "sel": 790},
        1024: {"is": 690, "buy": 750, "sel": 850},
    },
    "iPhone 16e": {
        128:  {"is": 280, "buy": 320, "sel": 380},
        256:  {"is": 310, "buy": 400, "sel": 440},
        512:  {"is": 320, "buy": None, "sel": None},
    },
    "iPhone 16": {
        128:  {"is": 400, "buy": 470, "sel": 540},
        256:  {"is": 440, "buy": 650, "sel": 760},
        512:  {"is": 490, "buy": 570, "sel": 600},
    },
    "iPhone 16 Plus": {
        128:  {"is": 440, "buy": 550, "sel": 650},
        256:  {"is": 520, "buy": 600, "sel": 750},
    },
    "iPhone 16 Pro": {
        128:  {"is": 460, "buy": 620, "sel": 700},
        256:  {"is": 520, "buy": 650, "sel": 760},
        512:  {"is": 530, "buy": 750, "sel": 830},
    },
    "iPhone 16 Pro Max": {
        256:  {"is": 560, "buy": 680, "sel": 750},
        512:  {"is": 610, "buy": 750, "sel": 850},
        1024: {"is": 870, "buy": 900, "sel": 960},
    },
}

# Ordem de prioridade — do mais específico para o menos específico
MODELOS_PRIORIDADE = [
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16 Plus", "iPhone 16e", "iPhone 16",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus", "iPhone 15",
    "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14 Plus", "iPhone 14",
    "iPhone 13 Pro Max", "iPhone 13 Pro", "iPhone 13 Mini", "iPhone 13",
    "iPhone 12 Pro Max",
]

MODELOS = {
    "iPhone 12 Pro Max": "iphone 12 pro max",
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


def minutos_desde(created_at_str):
    if not created_at_str:
        return None
    try:
        ts = str(created_at_str).replace("Z", "+00:00")
        criado_em = datetime.fromisoformat(ts)
        return (datetime.now(timezone.utc) - criado_em).total_seconds() / 60
    except Exception:
        return None


def detectar_modelo_real(titulo):
    titulo_lower = titulo.lower()
    if "iphone" not in titulo_lower:
        return None
    for modelo in MODELOS_PRIORIDADE:
        padrao = modelo.lower().replace(" ", r"[\s\-]+")
        if re.search(padrao, titulo_lower):
            return modelo
    return None


def titulo_tem_palavra_proibida(titulo):
    titulo_lower = titulo.lower()
    for palavra in PALAVRAS_EXCLUIDAS:
        if re.search(r"\b" + re.escape(palavra) + r"\b", titulo_lower):
            return True, palavra
    return False, None


# ----------------------------------------------------------------------
# ANALISE DE DESCRICAO
# ----------------------------------------------------------------------

def buscar_descricao(aid):
    """Busca a descrição completa do anúncio via API individual."""
    url = "https://www.olx.pt/api/v1/offers/" + str(aid) + "/"
    try:
        r = requests.get(url, headers=HEADERS_API, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("description", "")
    except Exception as e:
        log("  Erro descricao: " + str(e))
    return ""


def analisar_descricao(descricao):
    """
    Analisa a descrição do anúncio.

    Devolve:
      deve_filtrar (bool)  — True = rejeitar este anúncio
      motivo (str)         — razão do filtro (se aplicável)
      bateria_pct (int)    — percentagem da bateria ou None
      condicao_info (str)  — resumo legível do estado do aparelho
    """
    if not descricao:
        return False, None, None, "⚪ Sem descrição"

    d = descricao.lower()

    # ── FILTROS DUROS ────────────────────────────────────────────────

    # Para peças
    if re.search(r"\bpara\s+pe[çc]as?\b", d):
        return True, "Para peças", None, None

    # Apenas eSIM (phone only accepts eSIM — limitation)
    if re.search(r"\b(apenas\s+esim|s[oó]\s+esim|esim\s+only|n[aã]o\s+aceita?\s+sim\s+f[ií]sico)\b", d):
        return True, "Apenas eSIM", None, None

    # Bloqueado (sem "desbloqueado" na descrição)
    if re.search(r"\bbloqueado\b", d) and not re.search(r"\bdesbloqueado\b", d):
        return True, "Bloqueado/operadora", None, None

    # Peças trocadas / componentes substituídos
    if re.search(
        r"\b(pe[çc]as?\s+trocadas?|ecr[aã]\s+trocado|display\s+trocado"
        r"|bateria\s+trocada|touch\s+trocado|face\s+id\s+trocado"
        r"|componente\s+trocado|original\s+trocado)\b", d
    ):
        return True, "Peças trocadas", None, None

    # ── BATERIA ──────────────────────────────────────────────────────

    bateria_pct = None
    bat_match = (
        re.search(r"bateria[:\s\-]+(\d{2,3})\s*%", d) or
        re.search(r"(\d{2,3})\s*%\s*(?:de\s+)?bateria", d) or
        re.search(r"sa[uú]de[:\s]+(\d{2,3})\s*%", d) or
        re.search(r"capacidade[:\s]+(\d{2,3})\s*%", d) or
        re.search(r"(\d{2,3})\s*%\s*(?:de\s+)?capacidade", d)
    )
    if bat_match:
        pct = int(bat_match.group(1))
        if 50 <= pct <= 100:
            bateria_pct = pct
            if bateria_pct < BATERIA_MINIMA:
                return True, "Bateria " + str(bateria_pct) + "% (min. " + str(BATERIA_MINIMA) + "%)", bateria_pct, None

    # ── CONDICAO ─────────────────────────────────────────────────────

    partes = []

    # Positivos
    if re.search(r"\b(impec[áa]vel|perfeito\s+estado|como\s+novo|sem\s+danos?"
                 r"|sem\s+riscos?|sem\s+arranha[õo]es?|estado\s+impec)\b", d):
        partes.append("✅ Impecável")

    # Negativos — danos / riscos
    dano_match = re.search(
        r"\b(dano|danos|risco(?!metro)|riscos|arranha[õo]|arranhado"
        r"|parti[do]+|rachado|vidro\s+parti|ecr[aã]\s+parti|pequeno\s+risco)\b", d
    )
    if dano_match:
        partes.append("⚠️ Danos/riscos mencionados")

    condicao_info = " | ".join(partes) if partes else "⚪ Estado não mencionado"

    return False, None, bateria_pct, condicao_info


# ----------------------------------------------------------------------
# LOCALIZACAO
# ----------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def verificar_localizacao(anuncio):
    mapa = anuncio.get("map", {})
    if isinstance(mapa, dict):
        lat = mapa.get("lat")
        lon = mapa.get("lon")
        if lat and lon:
            try:
                dist = haversine(CENTRO_LAT, CENTRO_LON, float(lat), float(lon))
                return dist <= RAIO_KM, round(dist, 1), None
            except Exception:
                pass
    loc = anuncio.get("location", {})
    local_raw = ""
    if isinstance(loc, dict):
        cidade = loc.get("city", {})
        if isinstance(cidade, dict):
            local_raw = cidade.get("name", "")
        if not local_raw:
            local_raw = loc.get("name", "")
    if local_raw:
        aceite = any(l in local_raw.lower() for l in LOCAIS_ACEITES)
        return aceite, None, local_raw
    return True, None, None   # Sem info → aceita


# ----------------------------------------------------------------------
# CLASSIFICACAO DE PRECO
# ----------------------------------------------------------------------

def obter_refs(modelo, storage):
    """Devolve dict {is, buy, sel} para o modelo+storage, ou None."""
    tabela = PRECOS.get(modelo)
    if not tabela:
        return None
    if storage and storage in tabela:
        return tabela[storage]
    # Sem storage: calcula médias dos storages com buy definido
    validos = [v for v in tabela.values() if v.get("buy")]
    if not validos:
        return None
    return {
        "is":  round(sum(v["is"]  for v in validos) / len(validos)),
        "buy": round(sum(v["buy"] for v in validos) / len(validos)),
        "sel": round(sum(v["sel"] for v in validos) / len(validos)),
    }


def classificar(preco, refs):
    """
    Classifica com base no preço de compra alvo (buy).
    Também verifica se está abaixo do iServices.
    """
    if not refs or not refs.get("buy"):
        return "\U0001f4f1", "SEM REFERENCIA", None

    buy = refs["buy"]
    is_p = refs.get("is", buy)

    if preco <= is_p:
        diff = round(((buy - preco) / buy) * 100, 1)
        return "\U0001f525\U0001f525\U0001f525", "ABAIXO DO iSERVICES — COMPRA JA", diff
    elif preco <= buy:
        diff = round(((buy - preco) / buy) * 100, 1)
        if diff >= 10:
            return "\U0001f525\U0001f525", "EXCELENTE NEGOCIO", diff
        return "\U0001f525", "BOM NEGOCIO — compra ja", diff
    elif preco <= buy * 1.05:
        diff = round(((buy - preco) / buy) * 100, 1)
        return "\U0001f7e1", "NO LIMITE — negocia o preco", diff
    else:
        diff = round(((preco - buy) / buy) * 100, 1)
        return "\U0001f534", "ACIMA DO IDEAL", -diff


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


def montar_mensagem(modelo_real, titulo, preco, link,
                    storage, icone, label, diff_pct, refs,
                    bateria_pct, condicao_info, dist_km, local_nome):

    storage_txt = str(storage) + "GB" if storage else "? GB"

    # Lucro potencial
    lucro = (refs["sel"] - preco) if refs and refs.get("sel") else None

    # Cabeçalho
    msg = icone + " <b>" + label + "</b>\n\n"
    msg += "\U0001f4f1 <b>" + modelo_real + "</b> | " + storage_txt + "\n"
    msg += "\U0001f4cc <b>" + titulo + "</b>\n\n"

    # Preços
    msg += "\U0001f4b6 <b>Preco pedido:</b> " + str(preco) + "\u20ac\n"
    if refs:
        is_txt  = str(refs.get("is",  "N/D")) + "\u20ac"
        buy_txt = str(refs.get("buy", "N/D")) + "\u20ac"
        sel_txt = str(refs.get("sel", "N/D")) + "\u20ac"
        msg += ("\U0001f3ea iServices: <b>" + is_txt + "</b>  "
                "\U0001f3af Comprar: <b>" + buy_txt + "</b>  "
                "\U0001f4c8 Vender: <b>" + sel_txt + "</b>\n")
    if lucro is not None:
        emoji_lucro = "\U0001f911" if lucro > 100 else "\U0001f4b0"
        msg += emoji_lucro + " <b>Lucro potencial:</b> +" + str(lucro) + "\u20ac\n"
    if diff_pct is not None:
        sinal = "-" if diff_pct >= 0 else "+"
        msg += "\U0001f4c9 <b>Vs comprar:</b> " + sinal + str(abs(diff_pct)) + "%\n"

    # Bateria
    msg += "\n"
    if bateria_pct is not None:
        bat_e = "\U0001f50b" if bateria_pct >= 84 else "\u26a0\ufe0f"
        msg += bat_e + " <b>Bateria:</b> " + str(bateria_pct) + "%\n"
    else:
        msg += "\U0001f50b <b>Bateria:</b> Nao mencionada\n"

    # Condição
    if condicao_info:
        msg += "\U0001f50d <b>Estado:</b> " + condicao_info + "\n"

    # Localização
    if dist_km is not None:
        msg += "\U0001f4cd <b>Local:</b> " + str(dist_km) + "km de Alges\n"
    elif local_nome:
        msg += "\U0001f4cd <b>Local:</b> " + local_nome + "\n"

    msg += "\n\U0001f517 <a href=\"" + link + "\">Ver no OLX</a>"
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
        data    = r.json()
        ofertas = data.get("data", [])
        log("  API: " + str(len(ofertas)) + " ofertas")
        anuncios = []
        for o in ofertas:
            try:
                titulo     = o.get("title", "")
                link       = o.get("url", "")
                aid        = str(o.get("id", ""))
                created_at = (o.get("created_at") or o.get("last_refresh_time")
                              or o.get("pushup_time") or "")
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
                        "id": aid, "titulo": titulo, "preco": preco,
                        "link": link, "created_at": created_at,
                        "map": o.get("map", {}), "location": o.get("location", {}),
                    })
            except Exception:
                pass
        return anuncios
    except Exception as e:
        log("  API erro: " + str(e))
        return None


def buscar_nextdata(query):
    slug = query.replace(" ", "-")
    url  = "https://www.olx.pt/ads/q-" + slug + "/"
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
            return None
        data = json.loads(match.group(1))
        ads  = []
        try:
            pp  = data["props"]["pageProps"]
            ads = (pp.get("ads") or pp.get("listing", {}).get("ads") or
                   pp.get("initialState", {}).get("listing", {}).get("listing", {}).get("ads") or [])
        except Exception:
            pass
        log("  HTML: " + str(len(ads)) + " anuncios")
        anuncios = []
        for ad in ads:
            try:
                titulo     = ad.get("title", "")
                link       = ad.get("url", "")
                aid        = str(ad.get("id", ""))
                created_at = ad.get("created_at") or ad.get("last_refresh_time") or ""
                preco      = None
                p_raw      = ad.get("price", {})
                if isinstance(p_raw, dict):
                    preco = extrair_preco(p_raw.get("value") or p_raw.get("regularPrice", {}).get("value"))
                else:
                    preco = extrair_preco(p_raw)
                if titulo and link and aid:
                    anuncios.append({
                        "id": aid, "titulo": titulo, "preco": preco,
                        "link": link, "created_at": created_at,
                        "map": ad.get("map", {}), "location": ad.get("location", {}),
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

def processar_modelo(query_modelo, query, historico):
    log("--- " + query_modelo + " ---")

    anuncios = buscar_api(query)
    if anuncios is None:
        log("  API falhou, a tentar HTML...")
        anuncios = buscar_nextdata(query)

    if not anuncios:
        log("  Sem anuncios.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s)")
    enviados = 0

    for anuncio in anuncios:
        aid    = str(anuncio["id"])
        titulo = anuncio["titulo"]

        # Já visto?
        if aid in historico:
            continue
        historico.append(aid)

        # ── 1. PALAVRAS PROIBIDAS NO TÍTULO ──────────────────────────
        proibida, palavra = titulo_tem_palavra_proibida(titulo)
        if proibida:
            log("  [LIXO] '" + str(palavra) + "': " + titulo[:45])
            continue

        # ── 2. MODELO REAL ────────────────────────────────────────────
        modelo_real = detectar_modelo_real(titulo)
        if not modelo_real:
            log("  [SKIP] Modelo nao reconhecido: " + titulo[:45])
            continue

        # ── 3. FILTRO DE TEMPO ────────────────────────────────────────
        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        # ── 4. PRECO ──────────────────────────────────────────────────
        preco = anuncio.get("preco")
        if not preco:
            continue

        # ── 5. FILTRO ANTI-SPAM POR PRECO ─────────────────────────────
        tabela = PRECOS.get(modelo_real, {})
        is_vals = [v["is"] for v in tabela.values() if v.get("is")]
        is_media = round(sum(is_vals) / len(is_vals)) if is_vals else None
        if is_media and preco < is_media * (1 - FILTRO_ACESSORIO_PCT / 100):
            log("  [SPAM] " + str(preco) + "eur vs iS medio " + str(is_media) + "eur: " + titulo[:35])
            continue

        # ── 6. LOCALIZACAO ────────────────────────────────────────────
        aceite, dist_km, local_nome = verificar_localizacao(anuncio)
        if not aceite:
            info = str(dist_km) + "km" if dist_km else str(local_nome)
            log("  [GEO] Fora do raio (" + info + "): " + titulo[:35])
            continue

        # ── 7. LEITURA DA DESCRICAO ───────────────────────────────────
        log("  [DESC] A ler descricao de " + aid + "...")
        descricao = buscar_descricao(aid)
        deve_filtrar, motivo, bateria_pct, condicao_info = analisar_descricao(descricao)

        if deve_filtrar:
            log("  [DESC-FILTRO] " + str(motivo) + ": " + titulo[:40])
            continue

        # ── 8. CLASSIFICACAO E ENVIO ──────────────────────────────────
        storage   = extrair_storage(titulo)
        refs      = obter_refs(modelo_real, storage)
        icone, label, diff_pct = classificar(preco, refs)

        log("  [OK] " + modelo_real + " " + str(storage or "?") + "GB | "
            + str(preco) + "eur | " + label
            + (" | bat:" + str(bateria_pct) + "%" if bateria_pct else ""))

        msg = montar_mensagem(
            modelo_real, titulo, preco, anuncio["link"],
            storage, icone, label, diff_pct, refs,
            bateria_pct, condicao_info, dist_km, local_nome
        )

        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] OK")
        else:
            log("  [FAIL] Telegram falhou")

        time.sleep(1)

    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 60)
    log("OLX TRACKER v3 — " + str(RAIO_KM) + "km de Alges | bat>=" + str(BATERIA_MINIMA) + "%")
    log(str(len(MODELOS)) + " modelos | janela: " + str(MINUTOS_MAXIMO) + "min")
    log("=" * 60)

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

    log("=" * 60)
    log("CONCLUIDO — " + str(total) + " notificacoes enviadas.")
    log("=" * 60)


if __name__ == "__main__":
    main()# ======================================================================
#  TABELA DE PRECOS — 3 colunas por storage
#  "is"  = iServices (preço de referência rápida)
#  "buy" = Comprar/negociar (preço alvo de compra)
#  "sel" = Vender (preço de venda esperado)
#  Condições: como novo, bateria 84-95%, desbloqueado
# ======================================================================

PRECOS = {
    "iPhone 12 Pro Max": {
        128:  {"is": 220, "buy": 240, "sel": 295},
        256:  {"is": 260, "buy": 270, "sel": 310},
        512:  {"is": 340, "buy": 320, "sel": 350},
    },
    "iPhone 13 Mini": {
        128:  {"is": 155, "buy": 210, "sel": 250},
        256:  {"is": 180, "buy": 220, "sel": 260},
    },
    "iPhone 13": {
        128:  {"is": 190, "buy": 230, "sel": 290},
        256:  {"is": 210, "buy": 240, "sel": 300},
        512:  {"is": 230, "buy": 250, "sel": 300},
    },
    "iPhone 13 Pro": {
        128:  {"is": 250, "buy": 270, "sel": 310},
        256:  {"is": 260, "buy": 280, "sel": 340},
        512:  {"is": 320, "buy": 390, "sel": 450},
    },
    "iPhone 13 Pro Max": {
        128:  {"is": 300, "buy": 350, "sel": 400},
        256:  {"is": 320, "buy": 360, "sel": 400},
        512:  {"is": 350, "buy": 440, "sel": 500},
    },
    "iPhone 14": {
        128:  {"is": 200, "buy": 250, "sel": 330},
        256:  {"is": 240, "buy": 300, "sel": 360},
        512:  {"is": 360, "buy": 380, "sel": 430},
    },
    "iPhone 14 Plus": {
        128:  {"is": 220, "buy": 280, "sel": 330},
        256:  {"is": 280, "buy": 300, "sel": 360},
    },
    "iPhone 14 Pro": {
        128:  {"is": 280, "buy": 310, "sel": 380},
        256:  {"is": 300, "buy": 360, "sel": 430},
        512:  {"is": 350, "buy": 420, "sel": 470},
    },
    "iPhone 14 Pro Max": {
        128:  {"is": 330, "buy": 390, "sel": 430},
        256:  {"is": 370, "buy": 400, "sel": 440},
        512:  {"is": 380, "buy": 460, "sel": 570},
        1024: {"is": 630, "buy": 480, "sel": 650},
    },
    "iPhone 15": {
        128:  {"is": 300, "buy": 430, "sel": 470},
        256:  {"is": 340, "buy": 450, "sel": 530},
        512:  {"is": 280, "buy": 360, "sel": 420},
    },
    "iPhone 15 Plus": {
        128:  {"is": 290, "buy": 430, "sel": 510},
        256:  {"is": 330, "buy": 490, "sel": 590},
        512:  {"is": 420, "buy": None, "sel": None},
    },
    "iPhone 15 Pro": {
        128:  {"is": 370, "buy": 470, "sel": 520},
        256:  {"is": 430, "buy": 520, "sel": 600},
        512:  {"is": 530, "buy": 600, "sel": 700},
        1024: {"is": 690, "buy": 720, "sel": 800},
    },
    "iPhone 15 Pro Max": {
        256:  {"is": 460, "buy": 500, "sel": 580},
        512:  {"is": 650, "buy": 700, "sel": 790},
        1024: {"is": 690, "buy": 750, "sel": 850},
    },
    "iPhone 16e": {
        128:  {"is": 280, "buy": 320, "sel": 380},
        256:  {"is": 310, "buy": 400, "sel": 440},
        512:  {"is": 320, "buy": None, "sel": None},
    },
    "iPhone 16": {
        128:  {"is": 400, "buy": 470, "sel": 540},
        256:  {"is": 440, "buy": 650, "sel": 760},
        512:  {"is": 490, "buy": 570, "sel": 600},
    },
    "iPhone 16 Plus": {
        128:  {"is": 440, "buy": 550, "sel": 650},
        256:  {"is": 520, "buy": 600, "sel": 750},
    },
    "iPhone 16 Pro": {
        128:  {"is": 460, "buy": 620, "sel": 700},
        256:  {"is": 520, "buy": 650, "sel": 760},
        512:  {"is": 530, "buy": 750, "sel": 830},
    },
    "iPhone 16 Pro Max": {
        256:  {"is": 560, "buy": 680, "sel": 750},
        512:  {"is": 610, "buy": 750, "sel": 850},
        1024: {"is": 870, "buy": 900, "sel": 960},
    },
}

# Ordem de prioridade — do mais específico para o menos específico
MODELOS_PRIORIDADE = [
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16 Plus", "iPhone 16e", "iPhone 16",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus", "iPhone 15",
    "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14 Plus", "iPhone 14",
    "iPhone 13 Pro Max", "iPhone 13 Pro", "iPhone 13 Mini", "iPhone 13",
    "iPhone 12 Pro Max",
]

MODELOS = {
    "iPhone 12 Pro Max": "iphone 12 pro max",
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


def minutos_desde(created_at_str):
    if not created_at_str:
        return None
    try:
        ts = str(created_at_str).replace("Z", "+00:00")
        criado_em = datetime.fromisoformat(ts)
        return (datetime.now(timezone.utc) - criado_em).total_seconds() / 60
    except Exception:
        return None


def detectar_modelo_real(titulo):
    titulo_lower = titulo.lower()
    if "iphone" not in titulo_lower:
        return None
    for modelo in MODELOS_PRIORIDADE:
        padrao = modelo.lower().replace(" ", r"[\s\-]+")
        if re.search(padrao, titulo_lower):
            return modelo
    return None


def titulo_tem_palavra_proibida(titulo):
    titulo_lower = titulo.lower()
    for palavra in PALAVRAS_EXCLUIDAS:
        if re.search(r"\b" + re.escape(palavra) + r"\b", titulo_lower):
            return True, palavra
    return False, None


# ----------------------------------------------------------------------
# ANALISE DE DESCRICAO
# ----------------------------------------------------------------------

def buscar_descricao(aid):
    """Busca a descrição completa do anúncio via API individual."""
    url = "https://www.olx.pt/api/v1/offers/" + str(aid) + "/"
    try:
        r = requests.get(url, headers=HEADERS_API, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("description", "")
    except Exception as e:
        log("  Erro descricao: " + str(e))
    return ""


def analisar_descricao(descricao):
    """
    Analisa a descrição do anúncio.

    Devolve:
      deve_filtrar (bool)  — True = rejeitar este anúncio
      motivo (str)         — razão do filtro (se aplicável)
      bateria_pct (int)    — percentagem da bateria ou None
      condicao_info (str)  — resumo legível do estado do aparelho
    """
    if not descricao:
        return False, None, None, "⚪ Sem descrição"

    d = descricao.lower()

    # ── FILTROS DUROS ────────────────────────────────────────────────

    # Para peças
    if re.search(r"\bpara\s+pe[çc]as?\b", d):
        return True, "Para peças", None, None

    # Apenas eSIM (phone only accepts eSIM — limitation)
    if re.search(r"\b(apenas\s+esim|s[oó]\s+esim|esim\s+only|n[aã]o\s+aceita?\s+sim\s+f[ií]sico)\b", d):
        return True, "Apenas eSIM", None, None

    # Bloqueado (sem "desbloqueado" na descrição)
    if re.search(r"\bbloqueado\b", d) and not re.search(r"\bdesbloqueado\b", d):
        return True, "Bloqueado/operadora", None, None

    # Peças trocadas / componentes substituídos
    if re.search(
        r"\b(pe[çc]as?\s+trocadas?|ecr[aã]\s+trocado|display\s+trocado"
        r"|bateria\s+trocada|touch\s+trocado|face\s+id\s+trocado"
        r"|componente\s+trocado|original\s+trocado)\b", d
    ):
        return True, "Peças trocadas", None, None

    # ── BATERIA ──────────────────────────────────────────────────────

    bateria_pct = None
    bat_match = (
        re.search(r"bateria[:\s\-]+(\d{2,3})\s*%", d) or
        re.search(r"(\d{2,3})\s*%\s*(?:de\s+)?bateria", d) or
        re.search(r"sa[uú]de[:\s]+(\d{2,3})\s*%", d) or
        re.search(r"capacidade[:\s]+(\d{2,3})\s*%", d) or
        re.search(r"(\d{2,3})\s*%\s*(?:de\s+)?capacidade", d)
    )
    if bat_match:
        pct = int(bat_match.group(1))
        if 50 <= pct <= 100:
            bateria_pct = pct
            if bateria_pct < BATERIA_MINIMA:
                return True, "Bateria " + str(bateria_pct) + "% (min. " + str(BATERIA_MINIMA) + "%)", bateria_pct, None

    # ── CONDICAO ─────────────────────────────────────────────────────

    partes = []

    # Positivos
    if re.search(r"\b(impec[áa]vel|perfeito\s+estado|como\s+novo|sem\s+danos?"
                 r"|sem\s+riscos?|sem\s+arranha[õo]es?|estado\s+impec)\b", d):
        partes.append("✅ Impecável")

    # Negativos — danos / riscos
    dano_match = re.search(
        r"\b(dano|danos|risco(?!metro)|riscos|arranha[õo]|arranhado"
        r"|parti[do]+|rachado|vidro\s+parti|ecr[aã]\s+parti|pequeno\s+risco)\b", d
    )
    if dano_match:
        partes.append("⚠️ Danos/riscos mencionados")

    condicao_info = " | ".join(partes) if partes else "⚪ Estado não mencionado"

    return False, None, bateria_pct, condicao_info


# ----------------------------------------------------------------------
# LOCALIZACAO
# ----------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def verificar_localizacao(anuncio):
    mapa = anuncio.get("map", {})
    if isinstance(mapa, dict):
        lat = mapa.get("lat")
        lon = mapa.get("lon")
        if lat and lon:
            try:
                dist = haversine(CENTRO_LAT, CENTRO_LON, float(lat), float(lon))
                return dist <= RAIO_KM, round(dist, 1), None
            except Exception:
                pass
    loc = anuncio.get("location", {})
    local_raw = ""
    if isinstance(loc, dict):
        cidade = loc.get("city", {})
        if isinstance(cidade, dict):
            local_raw = cidade.get("name", "")
        if not local_raw:
            local_raw = loc.get("name", "")
    if local_raw:
        aceite = any(l in local_raw.lower() for l in LOCAIS_ACEITES)
        return aceite, None, local_raw
    return True, None, None   # Sem info → aceita


# ----------------------------------------------------------------------
# CLASSIFICACAO DE PRECO
# ----------------------------------------------------------------------

def obter_refs(modelo, storage):
    """Devolve dict {is, buy, sel} para o modelo+storage, ou None."""
    tabela = PRECOS.get(modelo)
    if not tabela:
        return None
    if storage and storage in tabela:
        return tabela[storage]
    # Sem storage: calcula médias dos storages com buy definido
    validos = [v for v in tabela.values() if v.get("buy")]
    if not validos:
        return None
    return {
        "is":  round(sum(v["is"]  for v in validos) / len(validos)),
        "buy": round(sum(v["buy"] for v in validos) / len(validos)),
        "sel": round(sum(v["sel"] for v in validos) / len(validos)),
    }


def classificar(preco, refs):
    """
    Classifica com base no preço de compra alvo (buy).
    Também verifica se está abaixo do iServices.
    """
    if not refs or not refs.get("buy"):
        return "\U0001f4f1", "SEM REFERENCIA", None

    buy = refs["buy"]
    is_p = refs.get("is", buy)

    if preco <= is_p:
        diff = round(((buy - preco) / buy) * 100, 1)
        return "\U0001f525\U0001f525\U0001f525", "ABAIXO DO iSERVICES — COMPRA JA", diff
    elif preco <= buy:
        diff = round(((buy - preco) / buy) * 100, 1)
        if diff >= 10:
            return "\U0001f525\U0001f525", "EXCELENTE NEGOCIO", diff
        return "\U0001f525", "BOM NEGOCIO — compra ja", diff
    elif preco <= buy * 1.05:
        diff = round(((buy - preco) / buy) * 100, 1)
        return "\U0001f7e1", "NO LIMITE — negocia o preco", diff
    else:
        diff = round(((preco - buy) / buy) * 100, 1)
        return "\U0001f534", "ACIMA DO IDEAL", -diff


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


def montar_mensagem(modelo_real, titulo, preco, link,
                    storage, icone, label, diff_pct, refs,
                    bateria_pct, condicao_info, dist_km, local_nome):

    storage_txt = str(storage) + "GB" if storage else "? GB"

    # Lucro potencial
    lucro = (refs["sel"] - preco) if refs and refs.get("sel") else None

    # Cabeçalho
    msg = icone + " <b>" + label + "</b>\n\n"
    msg += "\U0001f4f1 <b>" + modelo_real + "</b> | " + storage_txt + "\n"
    msg += "\U0001f4cc <b>" + titulo + "</b>\n\n"

    # Preços
    msg += "\U0001f4b6 <b>Preco pedido:</b> " + str(preco) + "\u20ac\n"
    if refs:
        is_txt  = str(refs.get("is",  "N/D")) + "\u20ac"
        buy_txt = str(refs.get("buy", "N/D")) + "\u20ac"
        sel_txt = str(refs.get("sel", "N/D")) + "\u20ac"
        msg += ("\U0001f3ea iServices: <b>" + is_txt + "</b>  "
                "\U0001f3af Comprar: <b>" + buy_txt + "</b>  "
                "\U0001f4c8 Vender: <b>" + sel_txt + "</b>\n")
    if lucro is not None:
        emoji_lucro = "\U0001f911" if lucro > 100 else "\U0001f4b0"
        msg += emoji_lucro + " <b>Lucro potencial:</b> +" + str(lucro) + "\u20ac\n"
    if diff_pct is not None:
        sinal = "-" if diff_pct >= 0 else "+"
        msg += "\U0001f4c9 <b>Vs comprar:</b> " + sinal + str(abs(diff_pct)) + "%\n"

    # Bateria
    msg += "\n"
    if bateria_pct is not None:
        bat_e = "\U0001f50b" if bateria_pct >= 84 else "\u26a0\ufe0f"
        msg += bat_e + " <b>Bateria:</b> " + str(bateria_pct) + "%\n"
    else:
        msg += "\U0001f50b <b>Bateria:</b> Nao mencionada\n"

    # Condição
    if condicao_info:
        msg += "\U0001f50d <b>Estado:</b> " + condicao_info + "\n"

    # Localização
    if dist_km is not None:
        msg += "\U0001f4cd <b>Local:</b> " + str(dist_km) + "km de Alges\n"
    elif local_nome:
        msg += "\U0001f4cd <b>Local:</b> " + local_nome + "\n"

    msg += "\n\U0001f517 <a href=\"" + link + "\">Ver no OLX</a>"
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
        data    = r.json()
        ofertas = data.get("data", [])
        log("  API: " + str(len(ofertas)) + " ofertas")
        anuncios = []
        for o in ofertas:
            try:
                titulo     = o.get("title", "")
                link       = o.get("url", "")
                aid        = str(o.get("id", ""))
                created_at = (o.get("created_at") or o.get("last_refresh_time")
                              or o.get("pushup_time") or "")
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
                        "id": aid, "titulo": titulo, "preco": preco,
                        "link": link, "created_at": created_at,
                        "map": o.get("map", {}), "location": o.get("location", {}),
                    })
            except Exception:
                pass
        return anuncios
    except Exception as e:
        log("  API erro: " + str(e))
        return None


def buscar_nextdata(query):
    slug = query.replace(" ", "-")
    url  = "https://www.olx.pt/ads/q-" + slug + "/"
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
            return None
        data = json.loads(match.group(1))
        ads  = []
        try:
            pp  = data["props"]["pageProps"]
            ads = (pp.get("ads") or pp.get("listing", {}).get("ads") or
                   pp.get("initialState", {}).get("listing", {}).get("listing", {}).get("ads") or [])
        except Exception:
            pass
        log("  HTML: " + str(len(ads)) + " anuncios")
        anuncios = []
        for ad in ads:
            try:
                titulo     = ad.get("title", "")
                link       = ad.get("url", "")
                aid        = str(ad.get("id", ""))
                created_at = ad.get("created_at") or ad.get("last_refresh_time") or ""
                preco      = None
                p_raw      = ad.get("price", {})
                if isinstance(p_raw, dict):
                    preco = extrair_preco(p_raw.get("value") or p_raw.get("regularPrice", {}).get("value"))
                else:
                    preco = extrair_preco(p_raw)
                if titulo and link and aid:
                    anuncios.append({
                        "id": aid, "titulo": titulo, "preco": preco,
                        "link": link, "created_at": created_at,
                        "map": ad.get("map", {}), "location": ad.get("location", {}),
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

def processar_modelo(query_modelo, query, historico):
    log("--- " + query_modelo + " ---")

    anuncios = buscar_api(query)
    if anuncios is None:
        log("  API falhou, a tentar HTML...")
        anuncios = buscar_nextdata(query)

    if not anuncios:
        log("  Sem anuncios.")
        return 0

    log("  " + str(len(anuncios)) + " anuncio(s)")
    enviados = 0

    for anuncio in anuncios:
        aid    = str(anuncio["id"])
        titulo = anuncio["titulo"]

        # Já visto?
        if aid in historico:
            continue
        historico.append(aid)

        # ── 1. PALAVRAS PROIBIDAS NO TÍTULO ──────────────────────────
        proibida, palavra = titulo_tem_palavra_proibida(titulo)
        if proibida:
            log("  [LIXO] '" + str(palavra) + "': " + titulo[:45])
            continue

        # ── 2. MODELO REAL ────────────────────────────────────────────
        modelo_real = detectar_modelo_real(titulo)
        if not modelo_real:
            log("  [SKIP] Modelo nao reconhecido: " + titulo[:45])
            continue

        # ── 3. FILTRO DE TEMPO ────────────────────────────────────────
        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        # ── 4. PRECO ──────────────────────────────────────────────────
        preco = anuncio.get("preco")
        if not preco:
            continue

        # ── 5. FILTRO ANTI-SPAM POR PRECO ─────────────────────────────
        tabela = PRECOS.get(modelo_real, {})
        is_vals = [v["is"] for v in tabela.values() if v.get("is")]
        is_media = round(sum(is_vals) / len(is_vals)) if is_vals else None
        if is_media and preco < is_media * (1 - FILTRO_ACESSORIO_PCT / 100):
            log("  [SPAM] " + str(preco) + "eur vs iS medio " + str(is_media) + "eur: " + titulo[:35])
            continue

        # ── 6. LOCALIZACAO ────────────────────────────────────────────
        aceite, dist_km, local_nome = verificar_localizacao(anuncio)
        if not aceite:
            info = str(dist_km) + "km" if dist_km else str(local_nome)
            log("  [GEO] Fora do raio (" + info + "): " + titulo[:35])
            continue

        # ── 7. LEITURA DA DESCRICAO ───────────────────────────────────
        log("  [DESC] A ler descricao de " + aid + "...")
        descricao = buscar_descricao(aid)
        deve_filtrar, motivo, bateria_pct, condicao_info = analisar_descricao(descricao)

        if deve_filtrar:
            log("  [DESC-FILTRO] " + str(motivo) + ": " + titulo[:40])
            continue

        # ── 8. CLASSIFICACAO E ENVIO ──────────────────────────────────
        storage   = extrair_storage(titulo)
        refs      = obter_refs(modelo_real, storage)
        icone, label, diff_pct = classificar(preco, refs)

        log("  [OK] " + modelo_real + " " + str(storage or "?") + "GB | "
            + str(preco) + "eur | " + label
            + (" | bat:" + str(bateria_pct) + "%" if bateria_pct else ""))

        msg = montar_mensagem(
            modelo_real, titulo, preco, anuncio["link"],
            storage, icone, label, diff_pct, refs,
            bateria_pct, condicao_info, dist_km, local_nome
        )

        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] OK")
        else:
            log("  [FAIL] Telegram falhou")

        time.sleep(1)

    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 60)
    log("OLX TRACKER v3 — " + str(RAIO_KM) + "km de Alges | bat>=" + str(BATERIA_MINIMA) + "%")
    log(str(len(MODELOS)) + " modelos | janela: " + str(MINUTOS_MAXIMO) + "min")
    log("=" * 60)

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

    log("=" * 60)
    log("CONCLUIDO — " + str(total) + " notificacoes enviadas.")
    log("=" * 60)


if __name__ == "__main__":
    main()
