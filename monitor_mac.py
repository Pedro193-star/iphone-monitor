"""
OLX TRACKER — MAC v2
Modelos: MacBook Air M1-M4 (13/15), MacBook Pro M1-M5, Mac Mini, iMac
So Apple Silicon (Intel ignorado).
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

FICHEIRO_HISTORICO = "historico_mac.json"
MINUTOS_MAXIMO     = 120
LIMITE_API         = 50
PRECO_MINIMO       = 150

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
    "carregador", "carregadores", "magsafe apenas", "cabo",
    "capa", "capas", "sleeve", "bolsa", "mala", "mochila",
    "teclado apenas", "apenas teclado", "magic keyboard",
    "magic mouse", "rato", "mouse", "trackpad",
    "suporte", "stand", "dock", "hub", "adaptador",
    "pelicula", "película", "protetor",
    "iphone", "watch", "airpods", "ipad",
    "hackintosh", "windows", "asus", "lenovo", "dell", "acer",
]

FILTROS_DESCRICAO = [
    r"bloqueado\s+icloud", r"icloud\s+bloqueado", r"icloud\s+lock",
    r"conta\s+icloud", r"conta\s+apple",
    r"find\s+my\s+(?:mac|ativo|ligado)",
    r"ativa[çc][aã]o\s+bloqueada",
    r"\bmdm\b", r"gest[aã]o\s+remota", r"remote\s+management",
    r"perfil\s+de\s+empresa", r"bloqueio\s+de\s+empresa",
    r"firmware\s+lock", r"password\s+de\s+firmware", r"efi\s+lock",
    r"pin\s+bloqueado",
    r"\bbloqueado\b(?![\s\S]{0,30}desbloqueado)",
    r"para\s+pe[çc]as?", r"para\s+repara[çc][aã]o",
    r"n[aã]o\s+funciona", r"n[aã]o\s+liga", r"n[aã]o\s+carrega",
    r"deixou\s+de\s+funcionar",
    r"ecr[aã]\s+parti", r"ecr[aã]\s+rachado",
    r"linhas\s+no\s+ecr[aã]", r"mancha\s+no\s+ecr[aã]", r"manchas\s+no\s+ecr[aã]",
    r"pixel\s+morto", r"pixeis\s+mortos", r"dead\s+pixel",
    r"ecr[aã]\s+trocado", r"display\s+trocado",
    r"backlight", r"retroilumina[çc][aã]o",
    r"[aá]gua", r"molhado", r"molhou", r"derramou", r"derrame",
    r"liquido", r"l[ií]quido", r"oxidado", r"oxida[çc][aã]o", r"humidade",
    r"teclas?\s+(?:que\s+)?n[aã]o\s+funciona", r"teclado\s+avariado",
    r"bateria\s+inchada", r"bateria\s+viciada", r"service\s+battery",
    r"reparar\s+bateria",
    r"avariado", r"avariada", r"estragado", r"estragada",
    r"com\s+defeito", r"defeituo[sz]", r"roubado", r"perdido",
    r"lote\s+de\s+\d+", r"vendo\s+lote",
]

MODELOS_PRIORIDADE = [
    "MacBook Pro M5",
    "MacBook Pro M4",
    "MacBook Pro M3",
    "MacBook Pro M2",
    "MacBook Pro M1",
    "MacBook Air 15 M4",
    "MacBook Air M4",
    "MacBook Air 15 M3",
    "MacBook Air M3",
    "MacBook Air 15 M2",
    "MacBook Air M2",
    "MacBook Air M1",
    "Mac Mini M4",
    "Mac Mini M2",
    "Mac Mini M1",
    "iMac M4",
    "iMac M3",
    "iMac M1",
]

PADROES = {
    "MacBook Pro M5":    r"macbook\s*pro[\s\S]{0,25}\bm5\b|\bm5\b[\s\S]{0,25}macbook\s*pro",
    "MacBook Pro M4":    r"macbook\s*pro[\s\S]{0,25}\bm4\b|\bm4\b[\s\S]{0,25}macbook\s*pro",
    "MacBook Pro M3":    r"macbook\s*pro[\s\S]{0,25}\bm3\b|\bm3\b[\s\S]{0,25}macbook\s*pro",
    "MacBook Pro M2":    r"macbook\s*pro[\s\S]{0,25}\bm2\b|\bm2\b[\s\S]{0,25}macbook\s*pro",
    "MacBook Pro M1":    r"macbook\s*pro[\s\S]{0,25}\bm1\b|\bm1\b[\s\S]{0,25}macbook\s*pro",
    "MacBook Air 15 M4": r"air[\s\S]{0,10}15[\s\S]{0,15}\bm4\b|\bm4\b[\s\S]{0,10}air[\s\S]{0,10}15",
    "MacBook Air M4":    r"macbook\s*air[\s\S]{0,25}\bm4\b|\bm4\b[\s\S]{0,25}macbook\s*air",
    "MacBook Air 15 M3": r"air[\s\S]{0,10}15[\s\S]{0,15}\bm3\b|\bm3\b[\s\S]{0,10}air[\s\S]{0,10}15",
    "MacBook Air M3":    r"macbook\s*air[\s\S]{0,25}\bm3\b|\bm3\b[\s\S]{0,25}macbook\s*air",
    "MacBook Air 15 M2": r"air[\s\S]{0,10}15[\s\S]{0,15}\bm2\b|\bm2\b[\s\S]{0,10}air[\s\S]{0,10}15",
    "MacBook Air M2":    r"macbook\s*air[\s\S]{0,25}\bm2\b|\bm2\b[\s\S]{0,25}macbook\s*air",
    "MacBook Air M1":    r"macbook\s*air[\s\S]{0,25}\bm1\b|\bm1\b[\s\S]{0,25}macbook\s*air",
    "Mac Mini M4":       r"mac\s*mini[\s\S]{0,25}\bm4\b|\bm4\b[\s\S]{0,25}mac\s*mini",
    "Mac Mini M2":       r"mac\s*mini[\s\S]{0,25}\bm2\b|\bm2\b[\s\S]{0,25}mac\s*mini",
    "Mac Mini M1":       r"mac\s*mini[\s\S]{0,25}\bm1\b|\bm1\b[\s\S]{0,25}mac\s*mini",
    "iMac M4":           r"imac[\s\S]{0,25}\bm4\b|\bm4\b[\s\S]{0,25}imac",
    "iMac M3":           r"imac[\s\S]{0,25}\bm3\b|\bm3\b[\s\S]{0,25}imac",
    "iMac M1":           r"imac[\s\S]{0,25}\bm1\b|\bm1\b[\s\S]{0,25}imac",
}

QUERIES = {
    "MacBook Pro": "macbook pro",
    "MacBook Air": "macbook air",
    "Mac Mini":    "mac mini",
    "iMac":        "imac",
}

# Precos P2P venda rapida (bom estado, config base 8-16GB/256) — CALIBRAR!
# Nota: Pro M1/M2/M4/M5 = versoes Pro/Max 14-16". Ecra 16" vale +100-150.
PRECOS = {
    "MacBook Pro M5":    {"buy": 1770, "sel": 1900},
    "MacBook Pro M4":    {"buy": 1340, "sel": 1450},
    "MacBook Pro M3":    {"buy": 830,  "sel": 900},
    "MacBook Pro M2":    {"buy": 810,  "sel": 880},
    "MacBook Pro M1":    {"buy": 620,  "sel": 680},
    "MacBook Air 15 M4": {"buy": 850,  "sel": 920},
    "MacBook Air M4":    {"buy": 760,  "sel": 830},
    "MacBook Air 15 M3": {"buy": 660,  "sel": 720},
    "MacBook Air M3":    {"buy": 600,  "sel": 650},
    "MacBook Air 15 M2": {"buy": 550,  "sel": 600},
    "MacBook Air M2":    {"buy": 480,  "sel": 520},
    "MacBook Air M1":    {"buy": 370,  "sel": 400},
    "Mac Mini M4":       {"buy": 480,  "sel": 520},
    "Mac Mini M2":       {"buy": 340,  "sel": 380},
    "Mac Mini M1":       {"buy": 270,  "sel": 300},
    "iMac M4":           {"buy": 1070, "sel": 1150},
    "iMac M3":           {"buy": 880,  "sel": 950},
    "iMac M1":           {"buy": 590,  "sel": 650},
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


def extrair_ram(texto):
    m = re.search(r"\b(8|16|18|24|32|36|48|64|96|128)\s*gb(?:\s+(?:de\s+)?ram|\s+unified|\s+mem)", str(texto).lower())
    if m:
        return m.group(1) + "GB RAM"
    return None


def extrair_storage(texto):
    t = str(texto).lower()
    if "4tb" in t or "4 tb" in t:
        return "4TB"
    if "2tb" in t or "2 tb" in t:
        return "2TB"
    if "1tb" in t or "1 tb" in t or "1024" in t:
        return "1TB"
    if "512" in t:
        return "512GB"
    if "256" in t:
        return "256GB"
    return None


def extrair_ciclos(texto):
    m = re.search(r"(\d{1,4})\s*ciclos?", str(texto).lower())
    if m:
        return int(m.group(1))
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
    if "macbook" not in t and "mac mini" not in t and "imac" not in t:
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
    ciclos = extrair_ciclos(d)
    partes = []
    if re.search(r"\b(sem\s+danos?|sem\s+riscos?|sem\s+arranha[õo]es?)\b", d):
        partes.append("\u2705 Sem danos")
    if re.search(r"\b(impec[áa]vel|perfeito\s+estado|como\s+novo)\b", d):
        if not partes:
            partes.append("\u2705 Impec\u00e1vel")
    if re.search(r"\b(com\s+fatura|fatura\s+inclu|com\s+caixa)\b", d):
        partes.append("\U0001f9fe Fatura/caixa")
    if re.search(r"\bgarantia\b", d):
        partes.append("\U0001f6e1\ufe0f Menciona garantia")
    if not any("\u2705" in p for p in partes):
        if re.search(r"\b(dano|danos|riscos?|arranha[õo]|amolgad|mossa|marcas\s+de\s+uso)\b", d):
            partes.append("\u26a0\ufe0f Danos/riscos mencionados")
    condicao = " | ".join(partes) if partes else "\u26aa Estado nao mencionado"
    return False, None, ciclos, condicao


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


def montar_mensagem(modelo, titulo, preco, link, ram, storage, ciclos,
                    icone, label, diff_pct, refs, condicao, dist_km, local_nome):
    msg = icone + " <b>" + label + "</b>  [Mac]\n\n"
    msg += "\U0001f4bb <b>" + modelo + "</b>"
    if ram:
        msg += " | " + ram
    if storage:
        msg += " | " + storage
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
    if ciclos is not None:
        c_emoji = "\U0001f50b" if ciclos < 500 else "\u26a0\ufe0f"
        msg += c_emoji + " <b>Ciclos de bateria:</b> " + str(ciclos) + "\n"
    msg += "\U0001f50d <b>Estado:</b> " + condicao + "\n"
    if dist_km is not None:
        msg += "\U0001f4cd <b>Local:</b> " + str(dist_km) + "km de Oeiras\n"
    elif local_nome:
        msg += "\U0001f4cd <b>Local:</b> " + local_nome + "\n"
    msg += "\n\u26a0\ufe0f <i>Precos = config base. Verificar: RAM/storage, ciclos (&lt;500), Find My OFF, sem MDM, teclado PT. Ecra 16\" vale +100-150</i>\n"
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
        deve_filtrar, motivo, ciclos, condicao = analisar_descricao(descricao)
        if deve_filtrar:
            log("  [DESC-FILTRO] " + str(motivo) + ": " + titulo[:40])
            continue

        ram     = extrair_ram(titulo) or extrair_ram(descricao)
        storage = extrair_storage(titulo) or extrair_storage(descricao)

        icone, label, diff_pct = classificar(preco, refs)
        log("  [OK] " + modelo + " | " + str(preco) + "eur | lucro:+" + str(refs["sel"] - preco) + "eur")
        msg = montar_mensagem(modelo, titulo, preco, anuncio["link"], ram, storage, ciclos,
                              icone, label, diff_pct, refs, condicao, dist_km, local_nome)
        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] OK")
        time.sleep(1)
    return enviados


def main():
    log("=" * 60)
    log("OLX TRACKER — MAC v2 | " + str(RAIO_KM) + "km Oeiras | so Apple Silicon")
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
