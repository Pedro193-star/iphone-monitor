"""
OLX TRACKER — APPLE WATCH v1
Monitoriza Apple Watch (SE, Series 7-10, Ultra 1/2) no OLX Portugal.

RESTRICOES DE QUALIDADE (rejeita):
- Acessorios soltos: braceletes, correias, capas, carregadores
- Bloqueado iCloud / conta Apple (Watch bloqueado e inutil!)
- Ecra partido/rachado, danos por agua, avariado, para pecas
- Replicas e imitacoes

PRECOS: tabela vazia — preencher manualmente. Enquanto vazia,
notifica TODOS os anuncios que passem os filtros de qualidade.
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

FICHEIRO_HISTORICO = "historico_watch.json"
MINUTOS_MAXIMO     = 120
LIMITE_API         = 100
PRECO_MINIMO       = 40      # Abaixo disto e acessorio/replica

CENTRO_LAT = 38.6907
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
    "montijo", "alcochete", "moita", "pinhal novo",
    "cacem", "cacém", "agualva", "rio de mouro",
    "alfragide", "buraca", "reboleira", "ericeira", "malveira",
]

# Palavras proibidas no TITULO (acessorios e outros produtos)
PALAVRAS_TITULO = [
    "bracelete", "braceletes", "correia", "correias", "band", "bands",
    "strap", "straps", "pulseira", "pulseiras", "loop",
    "carregador", "carregadores", "cabo", "cabos", "dock",
    "capa", "capas", "case", "protetor", "protecao", "proteção",
    "pelicula", "película", "vidro temperado", "vidro",
    "suporte", "stand", "adaptador",
    "iphone", "ipad", "airpods", "macbook", "imac",
    "replica", "réplica", "imitacao", "imitação", "copia", "cópia",
    "smartwatch generico", "tipo apple", "estilo apple",
]

# Filtros na DESCRICAO (rejeita)
FILTROS_DESCRICAO = [
    # Bloqueios (critico em Watches!)
    r"bloqueado\s+icloud",
    r"icloud\s+bloqueado",
    r"icloud\s+lock",
    r"conta\s+icloud",
    r"conta\s+apple",
    r"ativa[çc][aã]o\s+bloqueada",
    r"\bbloqueado\b(?![\s\S]{0,30}desbloqueado)",
    # Para pecas / nao funciona
    r"para\s+pe[çc]as?",
    r"para\s+repara[çc][aã]o",
    r"n[aã]o\s+funciona",
    r"n[aã]o\s+liga",
    r"n[aã]o\s+carrega",
    r"deixou\s+de\s+funcionar",
    # Danos
    r"ecr[aã]\s+parti",
    r"vidro\s+parti",
    r"vidro\s+rachado",
    r"rachado",
    r"rachadur",
    r"ecr[aã]\s+trocado",
    r"display\s+trocado",
    # Agua
    r"[aá]gua",
    r"molhado",
    r"molhou",
    r"oxidado",
    r"oxida[çc][aã]o",
    r"humidade",
    # Estado geral
    r"avariado",
    r"avariada",
    r"estragado",
    r"estragada",
    r"com\s+defeito",
    r"defeituo[sz]",
    r"roubado",
    r"perdido",
    # Replicas
    r"r[eé]plica",
    r"imita[çc][aã]o",
    r"c[oó]pia",
    r"n[aã]o\s+[eé]\s+original",
    r"gen[eé]rico",
    r"1[\s:]*1",
    # Lote
    r"lote\s+de\s+\d+",
    r"vendo\s+lote",
]

# ======================================================================
#  MODELOS (prioridade: mais especifico primeiro)
# ======================================================================

MODELOS_PRIORIDADE = [
    "Apple Watch Ultra 2",
    "Apple Watch Ultra",
    "Apple Watch Series 10",
    "Apple Watch Series 9",
    "Apple Watch Series 8",
    "Apple Watch Series 7",
    "Apple Watch SE 2",
    "Apple Watch SE",
]

PADROES = {
    "Apple Watch Ultra 2":   r"ultra\s*2",
    "Apple Watch Ultra":     r"\bultra\b",
    "Apple Watch Series 10": r"(series|serie|s[eé]rie)\s*10|\bs10\b",
    "Apple Watch Series 9":  r"(series|serie|s[eé]rie)\s*9|\bs9\b",
    "Apple Watch Series 8":  r"(series|serie|s[eé]rie)\s*8|\bs8\b",
    "Apple Watch Series 7":  r"(series|serie|s[eé]rie)\s*7|\bs7\b",
    "Apple Watch SE 2":      r"se\s*2|se\s*\(?2[\u00aa\s]*gera",
    "Apple Watch SE":        r"\bse\b",
}

QUERIES = {
    "Apple Watch Ultra":  "apple watch ultra",
    "Apple Watch 10":     "apple watch series 10",
    "Apple Watch 9":      "apple watch series 9",
    "Apple Watch 8":      "apple watch series 8",
    "Apple Watch 7":      "apple watch series 7",
    "Apple Watch SE":     "apple watch se",
}

# ======================================================================
#  PRECOS — PREENCHER MANUALMENTE (por agora vazio)
#  Exemplo de como preencher:
#  PRECOS = {
#      "Apple Watch Series 9": {"buy": 140, "sel": 200},
#      "Apple Watch Ultra 2":  {"buy": 380, "sel": 490},
#  }
#  Enquanto vazio: notifica todos os anuncios que passem os filtros.
# ======================================================================

PRECOS = {}

# ======================================================================

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://www.olx.pt/",
}


def carregar_historico():
    if not os.path.exists(FICHEIRO_HISTORICO):
        return []
    try:
        with open(FICHEIRO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
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
    if not created_at_str:
        return None
    try:
        ts = str(created_at_str).replace("Z", "+00:00")
        return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 60
    except Exception:
        return None


def detectar_modelo(titulo):
    t = titulo.lower()
    if "watch" not in t and "applewatch" not in t.replace(" ", ""):
        return None
    for modelo in MODELOS_PRIORIDADE:
        if re.search(PADROES[modelo], t):
            return modelo
    return None


def detectar_tamanho(texto):
    """Extrai o tamanho da caixa (40/41/42/44/45/46/49mm)."""
    m = re.search(r"\b(40|41|42|44|45|46|49)\s*mm\b", str(texto).lower())
    return m.group(1) + "mm" if m else None


def detectar_cellular(texto):
    t = str(texto).lower()
    if re.search(r"cellular|celular|lte|4g|esim", t):
        return "GPS + Cellular"
    if "gps" in t:
        return "GPS"
    return None


def titulo_proibido(titulo):
    t = titulo.lower()
    for p in PALAVRAS_TITULO:
        if re.search(r"\b" + re.escape(p) + r"\b", t):
            return True, p
    return False, None


def analisar_descricao(descricao):
    if not descricao:
        return False, None, None, "\u26aa Sem descricao"
    d = descricao.lower()
    for padrao in FILTROS_DESCRICAO:
        m = re.search(padrao, d)
        if m:
            return True, m.group(0), None, None
    bateria = None
    bm = re.search(r"bateria[^0-9]{0,15}(\d{2,3})\s*%", d) or re.search(r"(\d{2,3})\s*%\s*(?:de\s+)?bateria", d)
    if bm:
        pct = int(bm.group(1))
        if 50 <= pct <= 100:
            bateria = pct
    partes = []
    if re.search(r"\b(sem\s+danos?|sem\s+riscos?|sem\s+arranha[õo]es?)\b", d):
        partes.append("\u2705 Sem danos")
    if re.search(r"\b(impec[áa]vel|perfeito\s+estado|como\s+novo)\b", d):
        if not partes:
            partes.append("\u2705 Impec\u00e1vel")
    if not partes and re.search(r"\b(dano|danos|riscos?|arranha[õo]|amolgad|marcas\s+de\s+uso)\b", d):
        partes.append("\u26a0\ufe0f Danos/riscos mencionados")
    condicao = " | ".join(partes) if partes else "\u26aa Estado nao mencionado"
    return False, None, bateria, condicao


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def verificar_localizacao(anuncio):
    mapa = anuncio.get("map", {})
    if isinstance(mapa, dict) and mapa.get("lat") and mapa.get("lon"):
        try:
            dist = haversine(CENTRO_LAT, CENTRO_LON, float(mapa["lat"]), float(mapa["lon"]))
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
        return any(l in local_raw.lower() for l in LOCAIS_ACEITES), None, local_raw
    return True, None, None


def enviar_telegram(texto):
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": texto,
            "parse_mode": "HTML", "disable_web_page_preview": False,
        }, timeout=10)
        return r.ok
    except Exception as e:
        log("Telegram erro: " + str(e))
        return False


def montar_mensagem(modelo, titulo, preco, link, tamanho, cellular,
                    icone, label, refs, bateria, condicao, dist_km, local_nome):
    msg = icone + " <b>" + label + "</b>  [Apple Watch]\n\n"
    msg += "\u231a <b>" + modelo + "</b>"
    if tamanho:
        msg += " | " + tamanho
    if cellular:
        msg += " | " + cellular
    msg += "\n\U0001f4cc <b>" + titulo + "</b>\n\n"
    msg += "\U0001f4b6 <b>Preco pedido:</b> " + str(preco) + "\u20ac\n"
    if refs:
        msg += ("\U0001f3af Comprar: <b>" + str(refs["buy"]) + "\u20ac</b>  "
                "\U0001f4c8 Vender: <b>" + str(refs["sel"]) + "\u20ac</b>\n")
        lucro = refs["sel"] - preco
        if lucro > 0:
            msg += "\U0001f4b0 <b>Lucro potencial:</b> +" + str(lucro) + "\u20ac\n"
    msg += "\n"
    if bateria is not None:
        msg += "\U0001f50b <b>Bateria:</b> " + str(bateria) + "%\n"
    msg += "\U0001f50d <b>Estado:</b> " + condicao + "\n"
    if dist_km is not None:
        msg += "\U0001f4cd <b>Local:</b> " + str(dist_km) + "km de Oeiras\n"
    elif local_nome:
        msg += "\U0001f4cd <b>Local:</b> " + local_nome + "\n"
    msg += "\n\u26a0\ufe0f <i>Verificar: tamanho, GPS vs Cellular, iCloud removido, estado do ecra</i>\n"
    msg += "\n\U0001f517 <a href=\"" + link + "\">Ver no OLX</a>"
    return msg


def buscar_api(query):
    url = ("https://www.olx.pt/api/v1/offers/?offset=0&limit=" + str(LIMITE_API) +
           "&query=" + quote(query) + "&currency=EUR&sort_by=created_at%3Adesc")
    try:
        r = requests.get(url, headers=HEADERS_API, timeout=15)
        log("  API: HTTP " + str(r.status_code))
        if r.status_code != 200:
            return None
        ofertas = r.json().get("data", [])
        log("  API: " + str(len(ofertas)) + " ofertas")
        anuncios = []
        for o in ofertas:
            try:
                titulo = o.get("title", "")
                link   = o.get("url", "")
                aid    = str(o.get("id", ""))
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
                        "id": aid, "titulo": titulo, "preco": preco, "link": link,
                        "created_at": created_at,
                        "map": o.get("map", {}), "location": o.get("location", {}),
                    })
            except Exception:
                pass
        return anuncios
    except Exception as e:
        log("  API erro: " + str(e))
        return None


def buscar_descricao(aid):
    try:
        r = requests.get("https://www.olx.pt/api/v1/offers/" + str(aid) + "/",
                         headers=HEADERS_API, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("description", "")
    except Exception:
        pass
    return ""


def processar_query(nome, query, historico):
    log("--- " + nome + " ---")
    anuncios = buscar_api(query)
    if not anuncios:
        log("  Sem anuncios.")
        return 0
    enviados = 0
    for anuncio in anuncios:
        aid    = str(anuncio["id"])
        titulo = anuncio["titulo"]
        if aid in historico:
            continue
        historico.append(aid)

        proibida, palavra = titulo_proibido(titulo)
        if proibida:
            log("  [LIXO] '" + str(palavra) + "': " + titulo[:45])
            continue

        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        preco = anuncio.get("preco")
        if not preco or preco < PRECO_MINIMO:
            continue

        modelo = detectar_modelo(titulo)
        if not modelo:
            log("  [SKIP-MODELO] '" + titulo + "'")
            continue

        aceite, dist_km, local_nome = verificar_localizacao(anuncio)
        if not aceite:
            continue

        log("  [DESC] " + aid + " (" + titulo[:35] + ")")
        descricao = buscar_descricao(aid)
        deve_filtrar, motivo, bateria, condicao = analisar_descricao(descricao)
        if deve_filtrar:
            log("  [DESC-FILTRO] " + str(motivo) + ": " + titulo[:40])
            continue

        tamanho  = detectar_tamanho(titulo) or detectar_tamanho(descricao)
        cellular = detectar_cellular(titulo) or detectar_cellular(descricao)

        refs = PRECOS.get(modelo)
        if refs:
            if preco > (refs["sel"] - 10):
                log("  [CARO] " + str(preco) + " > " + str(refs["sel"]))
                continue
            if preco <= refs["buy"]:
                icone, label = "\U0001f525\U0001f525", "EXCELENTE NEGOCIO"
            else:
                icone, label = "\u2705", "NO LIMITE — negocia"
        else:
            icone, label = "\U0001f195", "NOVO ANUNCIO"

        log("  [OK] " + modelo + " | " + str(preco) + "eur")
        msg = montar_mensagem(modelo, titulo, preco, anuncio["link"], tamanho, cellular,
                              icone, label, refs, bateria, condicao, dist_km, local_nome)
        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] OK")
        time.sleep(1)
    return enviados


def main():
    log("=" * 60)
    log("OLX TRACKER — APPLE WATCH | " + str(RAIO_KM) + "km Oeiras")
    log("Precos definidos: " + (str(len(PRECOS)) + " modelos" if PRECOS else "NENHUM (modo descoberta)"))
    log("=" * 60)
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("ERRO: Credenciais Telegram nao definidas!")
        return
    historico = carregar_historico()
    log("Historico: " + str(len(historico)))
    total = 0
    for nome, query in QUERIES.items():
        try:
            total += processar_query(nome, query, historico)
        except Exception as e:
            log("Erro em " + nome + ": " + str(e))
        guardar_historico(historico)
        time.sleep(2)
    log("CONCLUIDO — " + str(total) + " notificacoes.")


if __name__ == "__main__":
    main()
