"""
OLX TRACKER — Relatório Diário das 22h
Apanhado de todos os iPhones publicados nas últimas 24h
"""

import requests
import json
import os
import re
import time
import statistics
from datetime import datetime, timezone, timedelta
from urllib.parse import quote


# ======================================================================
#  CONFIGURACOES
# ======================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

HORAS_LOOKBACK = 24   # Apanha anúncios das últimas 24h

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

MODELOS_PRIORIDADE = [
    "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16 Plus", "iPhone 16e", "iPhone 16",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus", "iPhone 15",
    "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14 Plus", "iPhone 14",
    "iPhone 13 Pro Max", "iPhone 13 Pro", "iPhone 13 Mini", "iPhone 13",
]

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

PALAVRAS_EXCLUIDAS = [
    "capa", "capas", "capinha", "capinhas",
    "pelicula", "peliculas", "película", "películas",
    "ecra", "ecras", "ecrã", "ecrãs", "display",
    "bateria", "baterias", "pecas", "peças",
    "caixa", "vazia", "vazio",
    "avariado", "avariada", "avaria",
    "partido", "partida", "partidos", "partidas",
    "bloqueado", "bloqueada", "icloud",
]

HEADERS_API = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://www.olx.pt/",
}


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
            return True
    return False


def minutos_desde(created_at_str):
    if not created_at_str:
        return None
    try:
        ts = str(created_at_str).replace("Z", "+00:00")
        criado_em = datetime.fromisoformat(ts)
        return (datetime.now(timezone.utc) - criado_em).total_seconds() / 60
    except Exception:
        return None


def obter_preco_ref(modelo, storage):
    tabela = PRECOS.get(modelo)
    if not tabela:
        return None
    if storage and storage in tabela:
        return tabela[storage]
    return round(sum(tabela.values()) / len(tabela))


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
            "disable_web_page_preview": True,
        }, timeout=10)
        return r.ok
    except Exception as e:
        log("Telegram erro: " + str(e))
        return False


# ----------------------------------------------------------------------
# SCRAPING COM PAGINACAO
# ----------------------------------------------------------------------

def buscar_todos_anuncios(query):
    """Pagina a API do OLX para apanhar todos os anúncios relevantes."""
    todos = []
    limite_horas = HORAS_LOOKBACK * 60  # em minutos
    offset = 0

    while True:
        url = ("https://www.olx.pt/api/v1/offers/"
               "?offset=" + str(offset) +
               "&limit=40"
               "&query=" + quote(query) +
               "&currency=EUR"
               "&sort_by=created_at%3Adesc")
        try:
            r = requests.get(url, headers=HEADERS_API, timeout=15)
            if r.status_code != 200:
                break
            data   = r.json()
            pagina = data.get("data", [])
            if not pagina:
                break

            parou = False
            for o in pagina:
                try:
                    titulo     = o.get("title", "")
                    link       = o.get("url", "")
                    aid        = str(o.get("id", ""))
                    created_at = (o.get("created_at") or o.get("last_refresh_time")
                                  or o.get("pushup_time") or "")
                    mins = minutos_desde(created_at)

                    # Se este anúncio já é mais antigo que o lookback, para a paginação
                    if mins is not None and mins > limite_horas:
                        parou = True
                        break

                    preco = None
                    for p in o.get("params", []):
                        if "price" in str(p.get("key", "")).lower():
                            preco = extrair_preco(p.get("value", {}).get("value", ""))
                            break
                    if preco is None:
                        p_raw = o.get("price", {})
                        preco = extrair_preco(p_raw.get("value") if isinstance(p_raw, dict) else p_raw)

                    if titulo and link and aid:
                        todos.append({
                            "id": aid, "titulo": titulo, "preco": preco,
                            "link": link, "created_at": created_at, "mins": mins,
                        })
                except Exception:
                    pass

            if parou or len(pagina) < 40:
                break

            offset += 40
            time.sleep(1)

        except Exception as e:
            log("  Erro paginacao: " + str(e))
            break

    return todos


# ----------------------------------------------------------------------
# CONSTRUCAO DO RELATORIO
# ----------------------------------------------------------------------

def construir_relatorio():
    """
    Para cada modelo, recolhe todos os anúncios das últimas 24h,
    limpa o lixo, detecta o modelo real, e calcula estatísticas.
    Devolve dict: modelo -> lista de anúncios processados.
    """
    # Usa um set para evitar duplicados entre queries
    ids_vistos = set()
    relatorio  = {m: [] for m in MODELOS_PRIORIDADE}

    for modelo_query, query in MODELOS.items():
        log("A recolher: " + modelo_query)
        anuncios = buscar_todos_anuncios(query)
        log("  " + str(len(anuncios)) + " anuncios encontrados")

        for anuncio in anuncios:
            aid = anuncio["id"]
            if aid in ids_vistos:
                continue
            ids_vistos.add(aid)

            titulo = anuncio["titulo"]

            # Filtra lixo
            if titulo_tem_palavra_proibida(titulo):
                continue

            # Detecta modelo real
            modelo_real = detectar_modelo_real(titulo)
            if not modelo_real:
                continue

            preco = anuncio.get("preco")
            if not preco:
                continue

            storage   = extrair_storage(titulo)
            preco_ref = obter_preco_ref(modelo_real, storage)

            diff_pct = None
            if preco_ref:
                diff_pct = round(((preco_ref - preco) / preco_ref) * 100, 1)

            relatorio[modelo_real].append({
                "titulo":    titulo,
                "preco":     preco,
                "preco_ref": preco_ref,
                "storage":   storage,
                "diff_pct":  diff_pct,
                "link":      anuncio["link"],
                "mins":      anuncio.get("mins"),
            })

        time.sleep(3)

    return relatorio


# ----------------------------------------------------------------------
# FORMATACAO DAS MENSAGENS
# ----------------------------------------------------------------------

def classificar_emoji(diff_pct):
    if diff_pct is None:
        return "\U0001f4f1"
    if diff_pct >= 25:
        return "\U0001f525\U0001f525"
    if diff_pct >= 10:
        return "\U0001f525"
    if diff_pct >= -5:
        return "\u2705"
    return "\U0001f534"


def formatar_bloco_modelo(modelo, anuncios):
    """Formata o bloco de texto para um modelo específico."""
    if not anuncios:
        return None

    precos = [a["preco"] for a in anuncios if a["preco"]]
    if not precos:
        return None

    media      = round(statistics.mean(precos))
    mediana    = round(statistics.median(precos))
    minimo     = min(precos)
    maximo     = max(precos)
    tabela_ref = PRECOS.get(modelo, {})
    ref_media  = round(sum(tabela_ref.values()) / len(tabela_ref)) if tabela_ref else None

    # Melhor deal (maior % abaixo da referência)
    melhor = None
    for a in anuncios:
        if a["diff_pct"] is not None:
            if melhor is None or a["diff_pct"] > melhor["diff_pct"]:
                melhor = a

    linhas = [
        "\U0001f4f1 <b>" + modelo + "</b>  (" + str(len(anuncios)) + " anuncios)",
        "   \U0001f4ca Media: <b>" + str(media) + "\u20ac</b>  |  Mediana: " + str(mediana) + "\u20ac",
        "   \U0001f4c9 Min: " + str(minimo) + "\u20ac  |  Max: " + str(maximo) + "\u20ac",
    ]

    if ref_media:
        diff_media = round(((ref_media - media) / ref_media) * 100, 1)
        sinal      = "-" if diff_media >= 0 else "+"
        linhas.append("   \U0001f3af Ref mercado: " + str(ref_media) +
                      "\u20ac  (" + sinal + str(abs(diff_media)) + "% vs media dia)")

    if melhor:
        emoji_melhor = classificar_emoji(melhor["diff_pct"])
        sinal        = "-" if melhor["diff_pct"] >= 0 else "+"
        linhas.append(
            "   " + emoji_melhor + " Melhor deal: <a href=\"" + melhor["link"] + "\">" +
            melhor["titulo"][:35] + "</a> — " +
            str(melhor["preco"]) + "\u20ac (" + sinal + str(abs(melhor["diff_pct"])) + "%)"
        )

    return "\n".join(linhas)


def enviar_relatorio(relatorio):
    """Envia o relatório completo em mensagens organizadas."""
    agora = datetime.now()
    ontem = agora - timedelta(hours=24)

    # Cabeçalho
    cabecalho = (
        "\U0001f4ca <b>RELATORIO DIARIO — OLX TRACKER</b>\n"
        "\U0001f4c5 " + ontem.strftime("%d/%m") + " 22h \u2192 " +
        agora.strftime("%d/%m") + " 22h\n"
        "\U0001f50d Mercado de iPhones em Portugal\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    enviar_telegram(cabecalho)
    time.sleep(1)

    # Uma mensagem por modelo (só os que têm anúncios)
    modelos_com_dados = 0
    for modelo in MODELOS_PRIORIDADE:
        anuncios = relatorio.get(modelo, [])
        bloco    = formatar_bloco_modelo(modelo, anuncios)
        if bloco:
            enviar_telegram(bloco)
            modelos_com_dados += 1
            time.sleep(1)

    # Rodapé com resumo
    total_anuncios = sum(len(v) for v in relatorio.values())
    rodape = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u2705 <b>Resumo:</b> " + str(total_anuncios) + " anuncios validos em " +
        str(modelos_com_dados) + " modelos\n"
        "\U0001f552 Proximo relatorio amanha as 22h"
    )
    enviar_telegram(rodape)
    log("Relatorio enviado: " + str(total_anuncios) + " anuncios em " + str(modelos_com_dados) + " modelos.")


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 60)
    log("OLX TRACKER — RELATORIO DIARIO DAS 22H")
    log("Janela: ultimas " + str(HORAS_LOOKBACK) + "h")
    log("=" * 60)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("ERRO: Credenciais Telegram nao definidas!")
        return

    relatorio = construir_relatorio()
    enviar_relatorio(relatorio)

    log("=" * 60)
    log("CONCLUIDO.")
    log("=" * 60)


if __name__ == "__main__":
    main()
