"""
OLX TRACKER — Relatorio Diario das 20h
Apanhado de todos os iPhones publicados nas ultimas 24h
Com os mesmos filtros do monitor (sem acessorios, sem pecas, etc.)
Mostra: preco pedido, valor de compra, potencial de venda
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

HORAS_LOOKBACK = 24

# Mesmas palavras proibidas do monitor
PALAVRAS_TITULO = [
    "capa", "capas", "capinha", "capinhas",
    "pelicula", "peliculas", "película", "películas",
    "vidro", "temperado",
    "ecra", "ecras", "ecrã", "ecrãs",
    "display", "lcd", "oled",
    "bateria", "baterias",
    "pecas", "peças", "peca", "peça",
    "caixa", "vazia", "vazio",
    "avariado", "avariada", "avaria",
    "partido", "partida", "partidos",
    "bloqueado", "bloqueada",
    "icloud",
    "carregador", "cabo", "auriculares",
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
        128:  {"is": 300, "buy": 370, "sel": 420},
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
    for palavra in PALAVRAS_TITULO:
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


def obter_refs(modelo, storage):
    tabela = PRECOS.get(modelo)
    if not tabela:
        return None
    if storage and storage in tabela:
        return tabela[storage]
    validos = [v for v in tabela.values() if v.get("buy")]
    if not validos:
        return None
    return {
        "is":  round(sum(v["is"]  for v in validos) / len(validos)),
        "buy": round(sum(v["buy"] for v in validos) / len(validos)),
        "sel": round(sum(v["sel"] for v in validos) / len(validos)),
    }


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
    todos = []
    limite_min = HORAS_LOOKBACK * 60
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

                    if mins is not None and mins > limite_min:
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
# RELATORIO
# ----------------------------------------------------------------------

def construir_relatorio():
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

            # Filtro titulo
            if titulo_tem_palavra_proibida(titulo):
                continue

            # Modelo real
            modelo_real = detectar_modelo_real(titulo)
            if not modelo_real:
                continue

            preco = anuncio.get("preco")
            if not preco or preco < 80:
                continue

            storage = extrair_storage(titulo)
            refs    = obter_refs(modelo_real, storage)

            buy_ref   = refs.get("buy") if refs else None
            sell_ref  = refs.get("sel") if refs else None
            lucro     = (sell_ref - preco) if sell_ref and preco else None
            pedir     = buy_ref if buy_ref else None

            # Diferenca vs buy
            diff_pct = None
            if buy_ref and preco:
                diff_pct = round(((buy_ref - preco) / buy_ref) * 100, 1)

            relatorio[modelo_real].append({
                "titulo":   titulo,
                "preco":    preco,
                "storage":  storage,
                "buy_ref":  buy_ref,
                "sell_ref": sell_ref,
                "lucro":    lucro,
                "pedir":    pedir,
                "diff_pct": diff_pct,
                "link":     anuncio["link"],
            })

        time.sleep(3)

    return relatorio


def emoji_deal(diff_pct):
    if diff_pct is None:
        return "\U0001f4f1"
    if diff_pct >= 25:
        return "\U0001f525\U0001f525\U0001f525"
    if diff_pct >= 10:
        return "\U0001f525\U0001f525"
    if diff_pct >= 0:
        return "\U0001f525"
    if diff_pct >= -5:
        return "\u2705"
    return "\U0001f7e1"


def formatar_bloco_modelo(modelo, anuncios):
    if not anuncios:
        return None

    precos = [a["preco"] for a in anuncios if a["preco"]]
    if not precos:
        return None

    media   = round(statistics.mean(precos))
    minimo  = min(precos)
    maximo  = max(precos)

    # Cabecalho do modelo
    linhas = [
        "\U0001f4f1 <b>" + modelo + "</b>  (" + str(len(anuncios)) + " anuncios)",
        "   \U0001f4ca Media: " + str(media) + "\u20ac  |  Min: " + str(minimo) + "\u20ac  |  Max: " + str(maximo) + "\u20ac",
        "",
    ]

    # Cada anuncio individualmente
    for a in sorted(anuncios, key=lambda x: x.get("diff_pct") or -999, reverse=True):
        emoji = emoji_deal(a["diff_pct"])
        storage_txt = str(a["storage"]) + "GB" if a["storage"] else "?"

        linha = "   " + emoji + " <b>" + str(a["preco"]) + "\u20ac</b>"
        linha += " | " + storage_txt

        if a["pedir"]:
            linha += " | Pedir: " + str(a["pedir"]) + "\u20ac"

        if a["lucro"] is not None and a["lucro"] > 0:
            linha += " | Lucro: +" + str(a["lucro"]) + "\u20ac"
        elif a["lucro"] is not None and a["lucro"] <= 0:
            linha += " | Lucro: " + str(a["lucro"]) + "\u20ac"

        if a["diff_pct"] is not None:
            sinal = "-" if a["diff_pct"] >= 0 else "+"
            linha += " (" + sinal + str(abs(a["diff_pct"])) + "%)"

        linhas.append(linha)

        # Titulo com link (mais pequeno)
        linhas.append("      <a href=\"" + a["link"] + "\">" + a["titulo"][:40] + "</a>")

    return "\n".join(linhas)


def enviar_relatorio(relatorio):
    agora = datetime.now()
    ontem = agora - timedelta(hours=24)

    # Cabecalho
    cabecalho = (
        "\U0001f4ca <b>RELATORIO DIARIO — OLX TRACKER</b>\n"
        "\U0001f4c5 " + ontem.strftime("%d/%m") + " 20h \u2192 " +
        agora.strftime("%d/%m") + " 20h\n"
        "\U0001f50d iPhones publicados nas ultimas 24h\n"
        "\U0001f3af Pedir = valor a propor ao vendedor\n"
        "\U0001f4b0 Lucro = potencial se venderes ao preco da tabela\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
    )
    enviar_telegram(cabecalho)
    time.sleep(1)

    # Um bloco por modelo
    modelos_com_dados = 0
    total_anuncios = 0
    total_bons = 0

    for modelo in MODELOS_PRIORIDADE:
        anuncios = relatorio.get(modelo, [])
        if not anuncios:
            continue

        bloco = formatar_bloco_modelo(modelo, anuncios)
        if bloco:
            # Telegram tem limite de 4096 chars
            if len(bloco) > 4000:
                partes = bloco.split("\n")
                metade = len(partes) // 2
                enviar_telegram("\n".join(partes[:metade]))
                time.sleep(1)
                enviar_telegram("\n".join(partes[metade:]))
            else:
                enviar_telegram(bloco)
            modelos_com_dados += 1
            total_anuncios += len(anuncios)
            total_bons += sum(1 for a in anuncios if a.get("diff_pct") and a["diff_pct"] >= 0)
            time.sleep(1)

    # Rodape
    rodape = (
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "\u2705 <b>Resumo:</b> " + str(total_anuncios) + " anuncios | " +
        str(modelos_com_dados) + " modelos | " +
        str(total_bons) + " abaixo do preco de compra\n"
        "\U0001f552 Proximo relatorio amanha as 20h"
    )
    enviar_telegram(rodape)
    log("Relatorio enviado: " + str(total_anuncios) + " anuncios em " + str(modelos_com_dados) + " modelos.")


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    log("=" * 60)
    log("OLX TRACKER — RELATORIO DIARIO DAS 20H")
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
