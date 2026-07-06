"""
OLX TRACKER v8 — Monitor de iPhones (versao GitHub otimizada)
Otimizacoes desta versao:
- Janela alargada para 120 minutos (compensa atraso do GitHub Actions)
- API pede 100 resultados em vez de 40 (apanha anuncios que ficavam de fora)
- Logs detalhados dos [SKIP] para debug de titulos mal detectados
- Bateria minima: 81% (rejeita se confirmada abaixo)
- SEM penalizacao 80-84% (bateria 81+ = precos normais)
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

FICHEIRO_HISTORICO = "historico.json"
MINUTOS_MAXIMO     = 120     # Janela alargada — compensa fila do GitHub
BATERIA_MINIMA     = 81      # Rejeita se confirmada abaixo
LIMITE_API         = 100     # Anuncios por pesquisa (era 40)

CENTRO_LAT = 38.6907         # Nova SBE / Carcavelos
CENTRO_LON = -9.3128
RAIO_KM    = 30

LOCAIS_ACEITES = [
    "lisboa", "lisbon", "alges", "algés", "oeiras", "cascais",
    "amadora", "odivelas", "loures", "sintra", "almada", "seixal",
    "barreiro", "estoril", "belem", "belém", "ajuda", "benfica",
    "carnaxide", "queijas", "linda-a-velha", "porto salvo",
    "paco de arcos", "paço de arcos", "caxias", "barcarena",
    "carcavelos", "parede", "monte estoril", "alcabideche",
    "queluz", "massamá", "massama", "damaia", "pontinha",
    "sacavém", "sacavem", "moscavide", "olivais", "oriente",
    "parque das nacoes", "parque das nações",
    "mafra", "sesimbra", "palmela", "setúbal", "setubal",
    "almargem", "ericeira", "malveira", "venda do pinheiro",
    "montijo", "alcochete", "moita", "pinhal novo",
    "cacem", "cacém", "agualva", "rio de mouro",
    "alfragide", "buraca", "reboleira",
]

PALAVRAS_TITULO = [
    "troco", "troca",
    "para iphone", "para iph", "compativel com iphone",
    "gaiola", "smallrig", "cage",
    "suporte", "mount", "tripé", "tripe", "gimbal",
    "lente", "lentes", "ring light",
    "acessorio", "acessórios", "acessorios",
    "proteção", "protecao", "protetor", "protectora",
    "bolsa", "mala", "carteira",
    "dock", "base", "stand",
    "powerbank", "power bank",
    "airpods", "apple watch", "ipad",
]

FILTROS_DESCRICAO = [
    r"para\s+pe[çc]as?",
    r"para\s+repara[çc][aã]o",
    r"para\s+arranjo",
    r"n[aã]o\s+funciona",
    r"n[aã]o\s+liga",
    r"n[aã]o\s+carrega",
    r"deixou\s+de\s+funcionar",
    r"apenas\s+esim",
    r"s[oó]\s+esim",
    r"esim\s+only",
    r"n[aã]o\s+aceita?\s+sim\s+f[ií]sico",
    r"sem\s+slot\s+sim",
    r"n[aã]o\s+tem\s+slot",
    r"bloqueado\s+(?:a|à|na)\s+\w+",
    r"bloqueado\s+icloud",
    r"icloud\s+bloqueado",
    r"icloud\s+lock",
    r"conta\s+icloud",
    r"ativa[çc][aã]o\s+bloqueada",
    r"pe[çc]as?\s+trocadas?",
    r"ecr[aã]\s+trocado",
    r"display\s+trocado",
    r"lcd\s+trocado",
    r"bateria\s+trocada",
    r"touch\s+trocado",
    r"face\s+id\s+trocado",
    r"touch\s+id\s+trocado",
    r"componente\s+trocado",
    r"n[aã]o\s+[eé]\s+original",
    r"ecr[aã]\s+n[aã]o\s+original",
    r"display\s+n[aã]o\s+original",
    r"aftermarket",
    r"refurbished",
    r"ecr[aã]\s+parti",
    r"vidro\s+parti",
    r"vidro\s+rachado",
    r"vidro\s+traseiro\s+parti",
    r"costas\s+partid",
    r"rachado",
    r"rachadur",
    r"[aá]gua",
    r"molhado",
    r"molhou",
    r"oxidado",
    r"oxida[çc][aã]o",
    r"humidade",
    r"roubado",
    r"perdido",
    r"imei\s+bloqueado",
    r"avariado",
    r"avariada",
    r"estragado",
    r"estragada",
    r"com\s+defeito",
    r"defeituo[sz]",
    r"nao\s+funcional",
    r"lote\s+de\s+\d+",
    r"vendo\s+lote",
    r"engano",
]


# ======================================================================
#  TABELA DE PRECOS
# ======================================================================

PRECOS = {
    "iPhone 12 Pro Max": {
        128:  {"is": 220, "buy": 260, "sel": 295},
        256:  {"is": 260, "buy": 300, "sel": 330},
    },
    "iPhone 13 Mini": {
        128:  {"is": 155, "buy": 210, "sel": 240},
        256:  {"is": 180, "buy": 220, "sel": 250},
    },
    "iPhone 13": {
        128:  {"is": 190, "buy": 220, "sel": 250},
        256:  {"is": 210, "buy": 260, "sel": 290},
    },
    "iPhone 13 Pro": {
        128:  {"is": 250, "buy": 310, "sel": 340},
        256:  {"is": 260, "buy": 320, "sel": 350},
    },
    "iPhone 13 Pro Max": {
        128:  {"is": 300, "buy": 300, "sel": 350},
        256:  {"is": 320, "buy": 360, "sel": 400},
    },
    "iPhone 14": {
        128:  {"is": 200, "buy": 260, "sel": 300},
        256:  {"is": 240, "buy": 330, "sel": 370},
    },
    "iPhone 14 Plus": {
        128:  {"is": 220, "buy": 295, "sel": 340},
        256:  {"is": 280, "buy": 300, "sel": 360},
    },
    "iPhone 14 Pro": {
        128:  {"is": 280, "buy": 360, "sel": 400},
        256:  {"is": 300, "buy": 380, "sel": 420},
    },
    "iPhone 14 Pro Max": {
        128:  {"is": 330, "buy": 390, "sel": 430},
        256:  {"is": 370, "buy": 400, "sel": 440},
    },
    "iPhone 15": {
        128:  {"is": 300, "buy": 360, "sel": 390},
        256:  {"is": 340, "buy": 400, "sel": 445},
    },
    "iPhone 15 Plus": {
        128:  {"is": 290, "buy": 410, "sel": 450},
        256:  {"is": 330, "buy": 450, "sel": 490},
    },
    "iPhone 15 Pro": {
        128:  {"is": 370, "buy": 470, "sel": 510},
        256:  {"is": 430, "buy": 520, "sel": 600},
    },
    "iPhone 15 Pro Max": {
        256:  {"is": 460, "buy": 500, "sel": 580},
        512:  {"is": 650, "buy": 700, "sel": 790},
    },
    "iPhone 16": {
        128:  {"is": 400, "buy": 490, "sel": 550},
        256:  {"is": 440, "buy": 650, "sel": 760},
    },
    "iPhone 16 Plus": {
        128:  {"is": 440, "buy": 550, "sel": 650},
        256:  {"is": 520, "buy": 600, "sel": 750},
    },
    "iPhone 16 Pro": {
        128:  {"is": 460, "buy": 620, "sel": 700},
        256:  {"is": 520, "buy": 650, "sel": 760},
    },
    "iPhone 16 Pro Max": {
        256:  {"is": 560, "buy": 680, "sel": 750},
        512:  {"is": 610, "buy": 750, "sel": 850},
    },
}

MODELOS_PRIORIDADE = [
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16 Plus", "iPhone 16",
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
    "iPhone 16 Plus":    "iphone 16 plus",
    "iPhone 16 Pro":     "iphone 16 pro",
    "iPhone 16 Pro Max": "iphone 16 pro max",
}

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


def extrair_storage_de_texto(texto):
    if not texto:
        return None
    t = str(texto).lower()
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


def detectar_modelo_de_texto(texto):
    if not texto:
        return None
    texto_lower = str(texto).lower()
    if "iphone" not in texto_lower:
        return None
    for modelo in MODELOS_PRIORIDADE:
        padrao = modelo.lower().replace(" ", r"[\s\-]+")
        if re.search(padrao, texto_lower):
            return modelo
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


def titulo_tem_palavra_proibida(titulo):
    titulo_lower = titulo.lower()
    for palavra in PALAVRAS_TITULO:
        if re.search(r"\b" + re.escape(palavra) + r"\b", titulo_lower):
            return True, palavra
    return False, None


def extrair_params_olx(params_list):
    resultado = {"modelo": None, "storage": None, "operador": None, "estado": None}
    if not params_list or not isinstance(params_list, list):
        return resultado
    for p in params_list:
        try:
            key = str(p.get("key", "")).lower()
            value = p.get("value", {})
            if isinstance(value, dict):
                texto = str(value.get("label") or value.get("key") or "")
            else:
                texto = str(value)
            if not texto:
                continue
            if "model" in key or "modelo" in key:
                modelo = detectar_modelo_de_texto(texto)
                if modelo:
                    resultado["modelo"] = modelo
            elif "memory" in key or "capacid" in key or "storage" in key or "armazen" in key:
                storage = extrair_storage_de_texto(texto)
                if storage:
                    resultado["storage"] = storage
            elif "operator" in key or "operador" in key:
                resultado["operador"] = texto.lower()
            elif "state" in key or "estado" in key or "condition" in key:
                resultado["estado"] = texto.lower()
        except Exception:
            pass
    return resultado


# ----------------------------------------------------------------------
# DESCRICAO
# ----------------------------------------------------------------------

def buscar_detalhes_anuncio(aid):
    url = "https://www.olx.pt/api/v1/offers/" + str(aid) + "/"
    try:
        r = requests.get(url, headers=HEADERS_API, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {})
            return data.get("description", ""), data.get("params", [])
    except Exception as e:
        log("  Erro detalhes: " + str(e))
    return "", []


def analisar_descricao(descricao):
    if not descricao:
        return False, None, None, "\u26aa Sem descricao"

    d = descricao.lower()

    for padrao in FILTROS_DESCRICAO:
        match = re.search(padrao, d)
        if match:
            return True, match.group(0), None, None

    if re.search(r"\bbloqueado\b", d) and not re.search(r"\bdesbloqueado\b", d):
        return True, "Bloqueado", None, None

    bateria_pct = None
    bat_match = (
        re.search(r"bateria[^0-9]{0,15}(\d{2,3})\s*%", d) or
        re.search(r"(\d{2,3})\s*%\s*(?:de\s+)?bateria", d) or
        re.search(r"sa[uú]de[^0-9]{0,10}(\d{2,3})\s*%", d) or
        re.search(r"capacidade[^0-9]{0,10}(\d{2,3})\s*%", d) or
        re.search(r"battery[^0-9]{0,10}(\d{2,3})\s*%", d)
    )
    if bat_match:
        pct = int(bat_match.group(1))
        if 50 <= pct <= 100:
            bateria_pct = pct
            if bateria_pct < BATERIA_MINIMA:
                return True, "Bateria " + str(bateria_pct) + "%", bateria_pct, None

    partes = []
    if re.search(r"\b(sem\s+danos?|sem\s+riscos?|sem\s+arranha[õo]es?)\b", d):
        partes.append("\u2705 Sem danos")
    if re.search(r"\b(impec[áa]vel|perfeito\s+estado|como\s+novo|estado\s+impec)\b", d):
        if "\u2705 Sem danos" not in partes:
            partes.append("\u2705 Impec\u00e1vel")
    if not any("\u2705" in p for p in partes):
        if re.search(
            r"\b(dano|danos|risco(?!metro)|riscos|arranha[õo]|arranhado"
            r"|amolgad|mossa|marca|marcas\s+de\s+uso)\b", d
        ):
            partes.append("\u26a0\ufe0f Danos/riscos mencionados")

    condicao = " | ".join(partes) if partes else "\u26aa Estado nao mencionado"
    return False, None, bateria_pct, condicao


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
    return True, None, None


# ----------------------------------------------------------------------
# CLASSIFICACAO
# ----------------------------------------------------------------------

def obter_refs(modelo, storage):
    tabela = PRECOS.get(modelo)
    if not tabela:
        return None, None
    if storage and storage in tabela:
        return tabela[storage], storage
    validos = [(k, v) for k, v in tabela.items() if v.get("sel") and v.get("buy")]
    if not validos:
        return None, None
    validos.sort(key=lambda x: x[1]["sel"])
    storage_usado, refs = validos[0]
    return refs, storage_usado


def classificar(preco, refs):
    if not refs or not refs.get("buy"):
        return "\U0001f4f1", "SEM REFERENCIA", None
    buy = refs["buy"]
    is_p = refs.get("is", buy)
    if preco <= is_p:
        diff = round(((buy - preco) / buy) * 100, 1)
        return "\U0001f525\U0001f525\U0001f525", "ABAIXO DO iSERVICES", diff
    elif preco <= buy:
        diff = round(((buy - preco) / buy) * 100, 1)
        if diff >= 10:
            return "\U0001f525\U0001f525", "EXCELENTE NEGOCIO", diff
        return "\U0001f525", "BOM NEGOCIO", diff
    elif preco <= buy * 1.05:
        diff = round(((buy - preco) / buy) * 100, 1)
        return "\u2705", "NO LIMITE — negocia", diff
    else:
        diff = round(((preco - buy) / buy) * 100, 1)
        return "\U0001f7e1", "ACIMA DO IDEAL", -diff


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
                    storage, storage_estimado, icone, label, diff_pct, refs,
                    bateria_pct, condicao_info, dist_km, local_nome):
    if storage:
        storage_txt = str(storage) + "GB"
    elif storage_estimado:
        storage_txt = "\u2753 NAO INDICADO (comparei com " + str(storage_estimado) + "GB) — perguntar ao vendedor"
    else:
        storage_txt = "\u2753 NAO INDICADO — perguntar ao vendedor"

    lucro = (refs["sel"] - preco) if refs and refs.get("sel") else None

    msg = icone + " <b>" + label + "</b>\n\n"
    msg += "\U0001f4f1 <b>" + modelo_real + "</b> | " + storage_txt + "\n"
    msg += "\U0001f4cc <b>" + titulo + "</b>\n\n"
    msg += "\U0001f4b6 <b>Preco pedido:</b> " + str(preco) + "\u20ac\n"

    if refs:
        is_t  = str(refs.get("is",  "?")) + "\u20ac"
        buy_t = str(refs.get("buy", "?")) + "\u20ac"
        sel_t = str(refs.get("sel", "?")) + "\u20ac"
        msg += ("\U0001f3ea iServices: <b>" + is_t + "</b>  "
                "\U0001f3af Comprar: <b>" + buy_t + "</b>  "
                "\U0001f4c8 Vender: <b>" + sel_t + "</b>\n")
    if lucro is not None and lucro > 0:
        emoji_l = "\U0001f911" if lucro > 100 else "\U0001f4b0"
        msg += emoji_l + " <b>Lucro potencial:</b> +" + str(lucro) + "\u20ac\n"
    if diff_pct is not None:
        sinal = "-" if diff_pct >= 0 else "+"
        msg += "\U0001f4c9 <b>Vs comprar:</b> " + sinal + str(abs(diff_pct)) + "%\n"

    msg += "\n"
    if bateria_pct is not None:
        bat_e = "\U0001f50b" if bateria_pct >= BATERIA_MINIMA else "\u26a0\ufe0f"
        msg += bat_e + " <b>Bateria:</b> " + str(bateria_pct) + "%\n"
    else:
        msg += "\u2753 <b>Bateria:</b> NAO INDICADA — perguntar ao vendedor\n"

    if condicao_info:
        msg += "\U0001f50d <b>Estado:</b> " + condicao_info + "\n"

    if dist_km is not None:
        msg += "\U0001f4cd <b>Local:</b> " + str(dist_km) + "km de Oeiras\n"
    elif local_nome:
        msg += "\U0001f4cd <b>Local:</b> " + local_nome + "\n"

    msg += "\n\U0001f517 <a href=\"" + link + "\">Ver no OLX</a>"
    return msg


# ----------------------------------------------------------------------
# SCRAPING
# ----------------------------------------------------------------------

def buscar_api(query):
    url = ("https://www.olx.pt/api/v1/offers/"
           "?offset=0&limit=" + str(LIMITE_API) +
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
                params_lista = o.get("params", [])
                preco = None
                for p in params_lista:
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
                        "params_lista": params_lista,
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
                        "params_lista": ad.get("params", []),
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
    enviados     = 0
    skip_modelo  = 0

    for anuncio in anuncios:
        aid    = str(anuncio["id"])
        titulo = anuncio["titulo"]

        if aid in historico:
            continue
        historico.append(aid)

        # 1. Palavras proibidas no titulo
        proibida, palavra = titulo_tem_palavra_proibida(titulo)
        if proibida:
            log("  [LIXO] '" + str(palavra) + "': " + titulo[:45])
            continue

        # 2. Filtro de tempo
        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        # 3. Preco
        preco = anuncio.get("preco")
        if not preco or preco < 80:
            continue

        # 4. Parametros estruturados
        params_olx = extrair_params_olx(anuncio.get("params_lista", []))

        # 5. MODELO: parametros > titulo
        modelo_real = params_olx["modelo"] or detectar_modelo_de_texto(titulo)
        if not modelo_real:
            skip_modelo += 1
            # Log detalhado: mostra o titulo INTEIRO para debug
            log("  [SKIP-MODELO] Titulo: '" + titulo + "'")
            continue

        # 6. STORAGE
        storage = params_olx["storage"] or extrair_storage_de_texto(titulo)

        # 7. Localizacao
        aceite, dist_km, local_nome = verificar_localizacao(anuncio)
        if not aceite:
            info = str(dist_km) + "km" if dist_km else str(local_nome)
            log("  [GEO] Fora raio (" + info + "): " + titulo[:35])
            continue

        # 8. Descricao + params individuais
        log("  [DESC] A ler " + aid + " (" + titulo[:35] + ")")
        descricao, params_completos = buscar_detalhes_anuncio(aid)
        params_extra = extrair_params_olx(params_completos)

        if not storage and params_extra["storage"]:
            storage = params_extra["storage"]
            log("  [STORAGE] Params: " + str(storage) + "GB")
        if not modelo_real and params_extra["modelo"]:
            modelo_real = params_extra["modelo"]

        operador = params_olx["operador"] or params_extra["operador"]
        if operador and "bloqueado" in operador and "desbloqueado" not in operador:
            log("  [OPERADOR] Bloqueado: " + titulo[:40])
            continue

        if not storage:
            storage = extrair_storage_de_texto(descricao)
            if storage:
                log("  [STORAGE] Descricao: " + str(storage) + "GB")

        # 9. Filtros descricao + bateria
        deve_filtrar, motivo, bateria_pct, condicao_info = analisar_descricao(descricao)
        if deve_filtrar:
            log("  [DESC-FILTRO] " + str(motivo) + ": " + titulo[:40])
            continue

        # 10. Refs
        refs, storage_usado = obter_refs(modelo_real, storage)
        storage_estimado = None
        if not storage and storage_usado:
            storage_estimado = storage_usado
            log("  [STORAGE] Sem info, comparei com " + str(storage_usado) + "GB")

        # 11. Preco demasiado alto
        if refs and refs.get("sel") and preco > (refs["sel"] - 10):
            log("  [CARO] " + str(preco) + " > venda " + str(refs["sel"]) + ": " + titulo[:35])
            continue

        # 12. Classificacao e envio
        icone, label, diff_pct = classificar(preco, refs)

        lucro_log = (refs["sel"] - preco) if refs and refs.get("sel") else "?"
        log("  [OK] " + modelo_real + " " + str(storage or storage_estimado or "?") + "GB | "
            + str(preco) + "eur | lucro:+" + str(lucro_log) + "eur | " + str(label))

        msg = montar_mensagem(
            modelo_real, titulo, preco, anuncio["link"],
            storage, storage_estimado, icone, label, diff_pct, refs,
            bateria_pct, condicao_info, dist_km, local_nome
        )
        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] OK")
        else:
            log("  [FAIL] Telegram falhou")
        time.sleep(1)

    if skip_modelo > 0:
        log("  RESUMO: " + str(skip_modelo) + " anuncios com titulo nao reconhecido")

    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 60)
    log("OLX TRACKER v8 | " + str(RAIO_KM) + "km Oeiras | bat>=" + str(BATERIA_MINIMA) + "%")
    log("Janela: " + str(MINUTOS_MAXIMO) + "min | Limit API: " + str(LIMITE_API))
    log(str(len(MODELOS)) + " modelos | " + str(len(FILTROS_DESCRICAO)) + " filtros descricao")
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
        time.sleep(2)

    log("=" * 60)
    log("CONCLUIDO — " + str(total) + " notificacoes enviadas.")
    log("=" * 60)


if __name__ == "__main__":
    main()
