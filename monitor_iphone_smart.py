"""
OLX TRACKER — Monitor de iPhones
Versão com:
  1. Detecção rigorosa do modelo real pelo título
  2. Filtro anti-lixo com palavras proibidas
  3. Janela de tempo alargada (60 min) para atrasos do GitHub
  4. Mensagem Telegram limpa e rápida de ler
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
MINUTOS_MAXIMO       = 60    # Rede de segurança para atrasos do GitHub Actions
FILTRO_ACESSORIO_PCT = 85    # Ignora se preço > 85% abaixo da referência média
MARGEM_ACIMA         = 5     # % acima da referência → "tenta negociar"
MARGEM_ABAIXO        = 10    # % abaixo da referência → "excelente negócio"

# ----------------------------------------------------------------------
# FILTRO ANTI-LIXO — títulos com estas palavras são ignorados
# ----------------------------------------------------------------------
PALAVRAS_EXCLUIDAS = [
    "capa", "capas", "capinha", "capinhas",
    "pelicula", "peliculas", "película", "películas",
    "ecra", "ecras", "ecrã", "ecrãs", "display",
    "bateria", "baterias",
    "pecas", "peças",
    "caixa", "vazia", "vazio",
    "avariado", "avariada", "avaria",
    "partido", "partida", "partidos", "partidas",
    "bloqueado", "bloqueada",
    "icloud",
]

# ----------------------------------------------------------------------
# FILTRO DE LOCALIZACAO — Centro: Algés | Raio: 20 km
# ----------------------------------------------------------------------
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


# ======================================================================
#  TABELA DE PRECOS DE REFERENCIA (mercado usado PT)
# ======================================================================

PRECOS = {
    "iPhone 13 Mini":    {128: 154,  256: 227,  512: 353},
    "iPhone 13":         {128: 195,  256: 236,  512: 300},
    "iPhone 13 Pro":     {128: 302,  256: 332,  512: 368,  1024: 434},
    "iPhone 13 Pro Max": {128: 309,  256: 349,  512: 389,  1024: 464},
    "iPhone 14":         {128: 247,  256: 304,  512: 391},
    "iPhone 14 Plus":    {128: 298,  256: 347,  512: 417},
    "iPhone 14 Pro":     {128: 390,  256: 428,  512: 502,  1024: 533},
    "iPhone 14 Pro Max": {128: 436,  256: 474,  512: 547,  1024: 611},
    "iPhone 15":         {128: 370,  256: 440,  512: 515},
    "iPhone 15 Plus":    {128: 381,  256: 467,  512: 580},
    "iPhone 15 Pro":     {128: 470,  256: 520,  512: 569,  1024: 670},
    "iPhone 15 Pro Max": {256: 551,  512: 605,  1024: 630},
    "iPhone 16":         {256: 511,  512: 604,  1024: 670},
    "iPhone 16e":        {128: 355,  256: 429,  512: 535},
    "iPhone 16 Plus":    {128: 545,  256: 640,  512: 725},
    "iPhone 16 Pro":     {128: 667,  256: 702,  512: 820,  1024: 930},
    "iPhone 16 Pro Max": {256: 746,  512: 831,  1024: 960},
}

# Ordem de prioridade para detecção do modelo real no título
# (do mais específico para o menos específico)
MODELOS_PRIORIDADE = [
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16 Plus", "iPhone 16e", "iPhone 16",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus", "iPhone 15",
    "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14 Plus", "iPhone 14",
    "iPhone 13 Pro Max", "iPhone 13 Pro", "iPhone 13 Mini", "iPhone 13",
]

# ======================================================================
#  MODELOS E QUERIES DE PESQUISA
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
# DETECCAO RIGOROSA DO MODELO REAL
# ----------------------------------------------------------------------

def detectar_modelo_real(titulo):
    """
    Analisa o título e devolve o modelo iPhone mais específico encontrado.
    Itera por MODELOS_PRIORIDADE do mais específico para o menos específico,
    evitando classificar um 'Pro Max' como modelo base.
    Devolve None se não encontrar nenhum modelo reconhecido.
    """
    titulo_lower = titulo.lower()

    if "iphone" not in titulo_lower:
        return None

    for modelo in MODELOS_PRIORIDADE:
        # Constrói padrão de busca flexível (ex: "iphone 15 pro max")
        padrao = modelo.lower().replace(" ", r"[\s\-]+")
        if re.search(padrao, titulo_lower):
            return modelo

    return None


# ----------------------------------------------------------------------
# FILTRO ANTI-LIXO
# ----------------------------------------------------------------------

def titulo_tem_palavra_proibida(titulo):
    """
    Devolve True se o título contiver alguma palavra da lista PALAVRAS_EXCLUIDAS.
    Usa \b para corresponder apenas palavras completas.
    """
    titulo_lower = titulo.lower()
    for palavra in PALAVRAS_EXCLUIDAS:
        padrao = r"\b" + re.escape(palavra) + r"\b"
        if re.search(padrao, titulo_lower):
            return True, palavra
    return False, None


# ----------------------------------------------------------------------
# LOCALIZACAO
# ----------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def verificar_localizacao(anuncio):
    """
    Devolve (aceite, distancia_km, nome_local).
    GPS tem prioridade. Se não houver, usa whitelist de nomes.
    Se sem info, aceita por defeito.
    """
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

    return True, None, None  # Sem info → aceita


# ----------------------------------------------------------------------
# CLASSIFICACAO
# ----------------------------------------------------------------------

def classificar(preco, preco_ref):
    if preco_ref is None:
        return "\U0001f4f1", "SEM REFERENCIA", None

    diff_pct = ((preco_ref - preco) / preco_ref) * 100

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


def montar_mensagem(modelo_real, titulo, preco, link, storage, icone, label, diff_pct, preco_ref, dist_km, local_nome):
    preco_txt   = str(preco) + "\u20ac"
    ref_txt     = str(preco_ref) + "\u20ac" if preco_ref else "N/D"
    storage_txt = str(storage) + "GB" if storage else "?"

    if dist_km is not None:
        local_txt = str(dist_km) + "km de Alges"
    elif local_nome:
        local_txt = local_nome
    else:
        local_txt = "N/D"

    if diff_pct is not None:
        sinal    = "-" if diff_pct >= 0 else "+"
        diff_txt = sinal + str(round(abs(diff_pct), 1)) + "% vs ref"
    else:
        diff_txt = ""

    msg = (
        icone + " <b>" + label + "</b>\n\n"
        "\U0001f4f1 <b>" + modelo_real + "</b> | " + storage_txt + "\n"
        "\U0001f4cc <b>" + titulo + "</b>\n\n"
        "\U0001f4b6 <b>Preco:</b> " + preco_txt + "\n"
        "\U0001f3af <b>Ref:</b> " + ref_txt
    )
    if diff_txt:
        msg += "  (" + diff_txt + ")"
    msg += (
        "\n\U0001f4cd <b>Local:</b> " + local_txt + "\n\n"
        "\U0001f517 <a href=\"" + link + "\">Ver no OLX</a>"
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
                titulo = ad.get("title", "")
                link   = ad.get("url", "")
                aid    = str(ad.get("id", ""))
                created_at = ad.get("created_at") or ad.get("last_refresh_time") or ""
                preco = None
                p_raw = ad.get("price", {})
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
        aid = str(anuncio["id"])

        # Já visto → salta (sem adicionar de novo ao histórico)
        if aid in historico:
            continue

        # Marca como visto imediatamente (evita duplicados mesmo que filtre)
        historico.append(aid)

        titulo = anuncio["titulo"]

        # ── 1. FILTRO ANTI-LIXO ──────────────────────────────────────
        proibida, palavra = titulo_tem_palavra_proibida(titulo)
        if proibida:
            log("  [LIXO] '" + palavra + "' em: " + titulo[:50])
            continue

        # ── 2. DETECCAO DO MODELO REAL ────────────────────────────────
        modelo_real = detectar_modelo_real(titulo)
        if modelo_real is None:
            log("  [SKIP] Modelo nao reconhecido: " + titulo[:50])
            continue

        # ── 3. FILTRO DE TEMPO ────────────────────────────────────────
        mins = minutos_desde(anuncio.get("created_at", ""))
        if mins is not None and mins > MINUTOS_MAXIMO:
            continue

        # ── 4. PRECO ──────────────────────────────────────────────────
        preco = anuncio.get("preco")
        if not preco:
            continue

        # ── 5. FILTRO DE ACESSORIOS (preco absurdo) ───────────────────
        tabela_real = PRECOS.get(modelo_real, {})
        ref_media   = round(sum(tabela_real.values()) / len(tabela_real)) if tabela_real else None
        if ref_media and ((ref_media - preco) / ref_media) * 100 >= FILTRO_ACESSORIO_PCT:
            log("  [SPAM] " + str(preco) + "eur demasiado baixo: " + titulo[:40])
            continue

        # ── 6. FILTRO DE LOCALIZACAO ──────────────────────────────────
        aceite, dist_km, local_nome = verificar_localizacao(anuncio)
        if not aceite:
            info = str(dist_km) + "km" if dist_km else str(local_nome)
            log("  [GEO] Fora do raio (" + info + "): " + titulo[:40])
            continue

        # ── 7. CLASSIFICACAO E ENVIO ──────────────────────────────────
        storage   = extrair_storage(titulo)
        preco_ref = obter_preco_ref(modelo_real, storage)
        icone, label, diff_pct = classificar(preco, preco_ref)

        log("  [OK] " + modelo_real + " | " + titulo[:35] +
            " | " + str(preco) + "eur | ref: " + str(preco_ref) + "eur | " + label)

        msg = montar_mensagem(
            modelo_real, titulo, preco, anuncio["link"],
            storage, icone, label, diff_pct, preco_ref,
            dist_km, local_nome
        )

        if enviar_telegram(msg):
            enviados += 1
            log("  [SEND] Telegram OK")
        else:
            log("  [FAIL] Telegram falhou")

        time.sleep(1)

    return enviados


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 60)
    log("OLX TRACKER — " + str(RAIO_KM) + "km de Alges | janela: " + str(MINUTOS_MAXIMO) + "min")
    log(str(len(MODELOS)) + " modelos | " + str(len(PALAVRAS_EXCLUIDAS)) + " palavras proibidas")
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
