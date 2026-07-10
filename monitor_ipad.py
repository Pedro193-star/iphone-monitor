"""
OLX TRACKER — IPAD v2
Modelos: iPad 9/10, Air 4/5/M2/M3, Mini 6/7, Pro M1/M2/M4/M5 (11 e 12.9/13)
Precos: P2P venda rapida (~1 semana), bom estado, config base — CALIBRAR!
"""

import requests
import json
import os
import re
import time
import math
from datetime import datetime, timezone
from urllib.parse import quote

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

FICHEIRO_HISTORICO = "historico_ipad.json"
MINUTOS_MAXIMO     = 120
LIMITE_API         = 50
PRECO_MINIMO       = 80

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

PALAVRAS_TITULO = [
    "capa", "capas", "case", "smart cover", "folio",
    "pelicula", "película", "protetor", "vidro temperado",
    "pencil apenas", "apenas pencil", "so pencil", "só pencil",
    "teclado apenas", "apenas teclado", "so teclado", "só teclado",
    "magic keyboard apenas",
    "suporte", "stand", "dock", "adaptador", "cabo", "carregador",
    "iphone", "watch", "airpods", "macbook", "imac",
    "replica", "réplica", "imitacao", "imitação",
    "tablet android", "samsung tab", "lenovo", "huawei", "xiaomi pad",
]

FILTROS_DESCRICAO = [
    r"bloqueado\s+icloud", r"icloud\s+bloqueado", r"icloud\s+lock",
    r"conta\s+icloud", r"conta\s+apple", r"ativa[çc][aã]o\s+bloqueada",
    r"\bmdm\b", r"gest[aã]o\s+remota", r"remote\s+management",
    r"supervisionado", r"supervised", r"perfil\s+de\s+empresa",
    r"bloqueio\s+de\s+empresa",
    r"\bbloqueado\b(?![\s\S]{0,30}desbloqueado)",
    r"para\s+pe[çc]as?", r"para\s+repara[çc][aã]o",
    r"n[aã]o\s+funciona", r"n[aã]o\s+liga", r"n[aã]o\s+carrega",
    r"deixou\s+de\s+funcionar",
    r"ecr[aã]\s+parti", r"vidro\s+parti", r"vidro\s+rachado",
    r"rachado", r"rachadur", r"ecr[aã]\s+trocado", r"display\s+trocado",
    r"linhas\s+no\s+ecr[aã]", r"mancha\s+no\s+ecr[aã]",
    r"pixel\s+morto", r"dead\s+pixel",
    r"[aá]gua", r"molhado", r"molhou", r"oxidado", r"oxida[çc][aã]o", r"humidade",
    r"avariado", r"avariada", r"estragado", r"estragada",
    r"com\s+defeito", r"defeituo[sz]", r"roubado", r"perdido",
    r"n[aã]o\s+[eé]\s+original",
    r"lote\s+de\s+\d+", r"vendo\s+lote",
]

MODELOS_PRIORIDADE = [
    "iPad Pro 13 M5", "iPad Pro 11 M5",
    "iPad Pro 13 M4", "iPad Pro 11 M4",
    "iPad Pro 12.9 M2", "iPad Pro 11 M2",
    "iPad Pro 12.9 M1", "iPad Pro 11 M1",
    "iPad Pro 12.9", "iPad Pro 11",
    "iPad Air 13 M3", "iPad Air 11 M3",
    "iPad Air 13 M2", "iPad Air 11 M2",
    "iPad Air 5", "iPad Air 4",
    "iPad Mini 7", "iPad Mini 6",
    "iPad 10", "iPad 9",
]

PADROES = {
    "iPad Pro 13 M5":  r"pro[\s\S]{0,15}13[\s\S]{0,15}m5|m5[\s\S]{0,15}pro[\s\S]{0,10}13",
    "iPad Pro 11 M5":  r"pro[\s\S]{0,15}11[\s\S]{0,15}m5|m5[\s\S]{0,15}pro[\s\S]{0,10}11|pro[\s\S]{0,10}m5",
    "iPad Pro 13 M4":  r"pro[\s\S]{0,15}13[\s\S]{0,15}m4|m4[\s\S]{0,15}pro[\s\S]{0,10}13",
    "iPad Pro 11 M4":  r"pro[\s\S]{0,15}11[\s\S]{0,15}m4|m4[\s\S]{0,15}pro[\s\S]{0,10}11|pro[\s\S]{0,10}m4",
    "iPad Pro 12.9 M2": r"pro[\s\S]{0,10}12[\.,]?9[\s\S]{0,15}m2|m2[\s\S]{0,15}12[\.,]?9",
    "iPad Pro 11 M2":  r"pro[\s\S]{0,10}11[\s\S]{0,15}m2|m2[\s\S]{0,15}pro[\s\S]{0,10}11",
    "iPad Pro 12.9 M1": r"pro[\s\S]{0,10}12[\.,]?9[\s\S]{0,15}m1|m1[\s\S]{0,15}12[\.,]?9|pro[\s\S]{0,10}12[\.,]?9[\s\S]{0,15}2021",
    "iPad Pro 11 M1":  r"pro[\s\S]{0,10}11[\s\S]{0,15}m1|m1[\s\S]{0,15}pro[\s\S]{0,10}11|pro[\s\S]{0,10}11[\s\S]{0,15}2021",
    "iPad Pro 12.9":   r"pro\s*12[\.,]?9",
    "iPad Pro 11":     r"pro\s*11",
    "iPad Air 13 M3":  r"air[\s\S]{0,10}13[\s\S]{0,15}m3|air[\s\S]{0,10}m3[\s\S]{0,10}13",
    "iPad Air 11 M3":  r"air[\s\S]{0,15}m3",
    "iPad Air 13 M2":  r"air[\s\S]{0,10}13[\s\S]{0,15}m2|air[\s\S]{0,10}m2[\s\S]{0,10}13|air\s*13",
    "iPad Air 11 M2":  r"air[\s\S]{0,15}m2",
    "iPad Air 5":      r"air\s*5|air[\s\S]{0,15}m1",
    "iPad Air 4":      r"air\s*4",
    "iPad Mini 7":     r"mini\s*7",
    "iPad Mini 6":     r"mini\s*6",
    "iPad 10":         r"ipad\s*10\b|10[\u00aa\s]*gera[çc][aã]o",
    "iPad 9":          r"ipad\s*9\b|9[\u00aa\s]*gera[çc][aã]o",
}

QUERIES = {
    "iPad Pro":  "ipad pro",
    "iPad Air":  "ipad air",
    "iPad Mini": "ipad mini",
    "iPad":      "ipad",
}

# Precos P2P venda rapida (bom estado, storage base, WiFi) — CALIBRAR!
PRECOS = {
    "iPad Pro 13 M5":   {"buy": 1070, "sel": 1150},
    "iPad Pro 11 M5":   {"buy": 880,  "sel": 950},
    "iPad Pro 13 M4":   {"buy": 890,  "sel": 960},
    "iPad Pro 11 M4":   {"buy": 730,  "sel": 800},
    "iPad Pro 12.9 M2": {"buy": 580,  "sel": 640},
    "iPad Pro 11 M2":   {"buy": 480,  "sel": 530},
    "iPad Pro 12.9 M1": {"buy": 470,  "sel": 520},
    "iPad Pro 11 M1":   {"buy": 390,  "sel": 430},
    "iPad Pro 12.9":    {"buy": 470,  "sel": 520},
    "iPad Pro 11":      {"buy": 390,  "sel": 430},
    "iPad Air 13 M3":   {"buy": 590,  "sel": 650},
    "iPad Air 11 M3":   {"buy": 490,  "sel": 540},
    "iPad Air 13 M2":   {"buy": 510,  "sel": 560},
    "iPad Air 11 M2":   {"buy": 420,  "sel": 460},
    "iPad Air 5":       {"buy": 300,  "sel": 340},
    "iPad Air 4":       {"buy": 250,  "sel": 280},
    "iPad Mini 7":      {"buy": 390,  "sel": 430},
    "iPad Mini 6":      {"buy": 285,  "sel": 320},
    "iPad 10":          {"buy": 200,  "sel": 230},
    "iPad 9":           {"buy": 135,  "sel": 160},
}

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


def extrair_storage(texto):
    if not texto:
        return None
    t = str(texto).lower()
    if "2tb" in t or "2 tb" in t:
        return "2TB"
    if "1tb" in t or "1 tb" in t or "1024" in t:
        return "1TB"
    if "512" in t:
        return "512GB"
    if "256" in t:
        return "256GB"
    if "128" in t:
        return "128GB"
    if "64" in t:
        return "64GB"
    return None


def detectar_conectividade(texto):
    t = str(texto).lower()
    if re.search(r"cellular|celular|lte|5g|4g|\bsim\b", t):
        return "WiFi + Cellular"
    if "wifi" in t or "wi-fi" in t:
        return "WiFi"
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
    if "ipad" not in t:
        return None
    for modelo in MODELOS_PRIORIDADE:
        if re.search(PADROES[modelo], t):
            return modelo
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
    if re.search(r"\b(com\s+pencil|inclui\s+pencil|apple\s+pencil\s+inclu)", d):
        partes.append("\u270f\ufe0f Inclui Pencil")
    if re.search(r"\b(com\s+teclado|inclui\s+teclado|magic\s+keyboard\s+inclu)", d):
        partes.append("\u2328\ufe0f Inclui teclado")
    if not any("\u2705" in p for p in partes):
        if re.search(r"\b(dano|danos|riscos?|arranha[õo]|amolgad|marcas\s+de\s+uso)\b", d):
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


def classificar(preco, refs):
    buy = refs["buy"]
    if preco <= buy:
        diff = round(((buy - preco) / buy) * 100, 1)
        if diff >= 15:
            return "\U0001f525\U0001f525", "EXCELENTE NEGOCIO", diff
        return "\U0001f525", "BOM NEGOCIO", diff
    diff = round(((buy - preco) / buy) * 100, 1)
    return "\u2705", "NO LIMITE — negocia", diff


def montar_mensagem(modelo, titulo, preco, link, storage, conect,
                    icone, label, diff_pct, refs, bateria, condicao, dist_km, local_nome):
    msg = icone + " <b>" + label + "</b>  [iPad]\n\n"
    msg += "\U0001f4f1 <b>" + modelo + "</b>"
    if storage:
        msg += " | " + storage
    if conect:
        msg += " | " + conect
    msg += "\n\U0001f4cc <b>" + titulo + "</b>\n\n"
    msg += "\U0001f4b6 <b>Preco pedido:</b> " + str(preco) + "\u20ac\n"
    msg += ("\U0001f3af Comprar: <b>" + str(refs["buy"]) + "\u20ac</b>  "
            "\U0001f4c8 Vender: <b>" + str(refs["sel"]) + "\u20ac</b>\n")
    lucro = refs["sel"] - preco
    if lucro > 0:
        emoji_l = "\U0001f911" if lucro > 100 else "\U0001f4b0"
        msg += emoji_l + " <b>Lucro potencial:</b> +" + str(lucro) + "\u20ac\n"
    if diff_pct is not None:
        sinal = "-" if diff_pct >= 0 else "+"
        msg += "\U0001f4c9 <b>Vs comprar:</b> " + sinal + str(abs(diff_pct)) + "%\n"
    msg += "\n"
    if bateria is not None:
        msg += "\U0001f50b <b>Bateria:</b> " + str(bateria) + "%\n"
    msg += "\U0001f50d <b>Estado:</b> " + condicao + "\n"
    if dist_km is not None:
        msg += "\U0001f4cd <b>Local:</b> " + str(dist_km) + "km de Oeiras\n"
    elif local_nome:
        msg += "\U0001f4cd <b>Local:</b> " + local_nome + "\n"
    msg += "\n\u26a0\ufe0f <i>Precos = config base. Verificar: storage, WiFi vs Cellular, iCloud E MDM removidos</i>\n"
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

        refs = PRECOS.get(modelo)
        if not refs:
            continue

        if preco > (refs["sel"] - 10):
            log("  [CARO] " + str(preco) + " > " + str(refs["sel"]) + ": " + titulo[:35])
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

        storage = extrair_storage(titulo) or extrair_storage(descricao)
        conect  = detectar_conectividade(titulo) or detectar_conectividade(descricao)

        icone, label, diff_pct = classificar(preco, refs)
        log("  [OK] " + modelo + " | " + str(preco) + "eur | lucro:+" + str(refs["sel"] - preco) + "eur")
        msg = montar_mensagem(modelo, titulo, preco, anuncio["link"], storage, conect,
                              icone, label, diff_pct, refs, bateria, condicao, dist_km, local_nome)
        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] OK")
        time.sleep(1)
    return enviados


def main():
    log("=" * 60)
    log("OLX TRACKER — IPAD v2 | " + str(RAIO_KM) + "km Oeiras")
    log(str(len(PRECOS)) + " modelos com precos")
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
