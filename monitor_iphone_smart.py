"""
╔══════════════════════════════════════════════════════════════════════╗
║        MONITOR INTELIGENTE DE iPHONES — OLX Portugal               ║
║        Deteta negócios abaixo do preço de mercado                   ║
║        Notificações via Telegram Bot                                ║
╚══════════════════════════════════════════════════════════════════════╝

Lógica principal:
  1. Para cada modelo, recolhe os preços dos primeiros 20 anúncios
     → calcula a média de mercado dinâmica
  2. Verifica se há anúncios novos (não vistos ainda)
  3. Se o preço do anúncio novo for ≥ 15% abaixo da média → notifica
  4. Guarda tudo num ficheiro JSON local para não repetir alertas
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import statistics
from datetime import datetime
from typing import Optional


# ======================================================================
#  ⚙️  CONFIGURAÇÕES — EDITA APENAS ESTA SECÇÃO
# ======================================================================

TELEGRAM_BOT_TOKEN = "COLE_AQUI_O_TOKEN_DO_BOT"    # Ex: "7123456789:AAFxxxxxxx"
TELEGRAM_CHAT_ID   = "COLE_AQUI_O_CHAT_ID"          # Ex: "123456789"

# Desconto mínimo para receber alerta (0.15 = 15% abaixo da média)
DESCONTO_MINIMO = 0.15

# Número de anúncios usados para calcular a média de mercado
AMOSTRAS_PARA_MEDIA = 20

# Ficheiro de persistência (IDs vistos + médias guardadas)
FICHEIRO_DADOS = "dados_mercado.json"

# Quantas horas até recalcular a média (evita pedidos desnecessários)
HORAS_VALIDADE_MEDIA = 6

# -----------------------------------------------------------------------
# Modelos a monitorizar + URLs de pesquisa no OLX
# Para adicionar/remover modelos, basta editar este dicionário.
# Chave  = nome do modelo (aparece na notificação)
# Valor  = URL de pesquisa no OLX Portugal
# -----------------------------------------------------------------------
MODELOS = {
    "iPhone 14": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14/",
    "iPhone 14 Pro": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14-pro/",
    "iPhone 14 Pro Max": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-14-pro-max/",
    "iPhone 15": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15/",
    "iPhone 15 Pro": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15-pro/",
    "iPhone 15 Pro Max": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-15-pro-max/",
    "iPhone 16": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16/",
    "iPhone 16 Pro": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16-pro/",
    "iPhone 16 Pro Max": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-16-pro-max/",
    "iPhone 17": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17/",
    "iPhone 17 Pro": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17-pro/",
    "iPhone 17 Pro Max": "https://www.olx.pt/informatica-e-tecnologia/telemoveis-e-smartphones/q-iphone-17-pro-max/",
}

# ======================================================================
#  FIM DAS CONFIGURAÇÕES
# ======================================================================


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ──────────────────────────────────────────────────────────────────────
# PERSISTÊNCIA
# ──────────────────────────────────────────────────────────────────────

def carregar_dados() -> dict:
    """Carrega o ficheiro JSON com IDs vistos e médias guardadas."""
    if os.path.exists(FICHEIRO_DADOS):
        try:
            with open(FICHEIRO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"vistos": [], "medias": {}}


def guardar_dados(dados: dict):
    """Guarda os dados. Limita a lista de vistos a 5000 entradas."""
    dados["vistos"] = dados["vistos"][-5000:]
    with open(FICHEIRO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ──────────────────────────────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────────────────────────────

def enviar_telegram(texto: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except requests.RequestException as e:
        log(f"[Telegram] Erro: {e}")
        return False


def montar_alerta(modelo: str, anuncio: dict, media: float, desconto_pct: float) -> str:
    """Formata a mensagem de alerta enviada para o Telegram."""
    estrelas = "🔥" if desconto_pct >= 25 else ("💸" if desconto_pct >= 20 else "✅")
    return (
        f"{estrelas} <b>NEGÓCIO DETETADO!</b>\n\n"
        f"📱 <b>Modelo:</b> {modelo}\n"
        f"📌 <b>{anuncio['titulo']}</b>\n\n"
        f"💶 <b>Preço:</b> {anuncio['preco_texto']} €\n"
        f"📊 <b>Média do mercado:</b> {media:.0f} €\n"
        f"📉 <b>Desconto:</b> -{desconto_pct:.1f}% abaixo da média\n\n"
        f"🔗 <a href=\"{anuncio['link']}\">Ver anúncio no OLX</a>"
    )


# ──────────────────────────────────────────────────────────────────────
# SCRAPING
# ──────────────────────────────────────────────────────────────────────

def extrair_preco(texto: str) -> Optional[int]:
    """
    Converte texto de preço para inteiro.
    Exemplos: '750 €' → 750 | '1.200 €' → 1200 | 'Grátis' → None
    """
    if not texto:
        return None
    # Remove tudo exceto dígitos e vírgulas/pontos
    limpo = texto.strip().lower()
    if "grátis" in limpo or "troca" in limpo or "ver desc" in limpo:
        return None
    # Remove separadores de milhar e parte decimal
    sem_milhar = re.sub(r"\.(?=\d{3})", "", limpo)  # Remove ponto de milhar
    sem_decimal = re.sub(r",\d{1,2}$", "", sem_milhar)  # Remove decimais
    numeros = re.findall(r"\d+", sem_decimal)
    if numeros:
        valor = int("".join(numeros[:2]))  # Junta até 2 grupos (ex: 1 + 200 → 1200)
        # Sanidade: iPhones entre 50€ e 5000€
        if 50 <= valor <= 5000:
            return valor
    return None


def extrair_id(link: str) -> str:
    """Extrai o ID único do link do OLX."""
    match = re.search(r"ID(\w+)", link)
    if match:
        return match.group(1)
    # Fallback: usa hash do URL
    return str(abs(hash(link)) % (10 ** 10))


def scrape_olx_pagina(url: str) -> list[dict]:
    """
    Raspa uma página do OLX e devolve lista de anúncios com:
    id, titulo, preco_num, preco_texto, link
    """
    anuncios = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"  [OLX] Erro HTTP: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # OLX usa data-cy="l-card" para cada anúncio
    cards = soup.find_all("div", {"data-cy": "l-card"})

    # Fallback para estrutura alternativa
    if not cards:
        cards = soup.find_all("li", class_=re.compile(r"css-\w+"))

    if not cards:
        log("  [OLX] Nenhum card encontrado — o OLX pode ter mudado o HTML.")
        return []

    for card in cards:
        try:
            # Título
            titulo_el = (
                card.find("h6")
                or card.find("h4")
                or card.find("h3")
                or card.find("p", class_=re.compile(r"title|titulo", re.I))
            )
            if not titulo_el:
                continue
            titulo = titulo_el.get_text(strip=True)

            # Link
            link_el = card.find("a", href=True)
            if not link_el:
                continue
            link = link_el["href"]
            if not link.startswith("http"):
                link = "https://www.olx.pt" + link
            # Remove parâmetros de tracking
            link = link.split("?")[0]

            # ID
            anuncio_id = extrair_id(link)

            # Preço — tenta vários seletores
            preco_el = (
                card.find("p", {"data-testid": "ad-price"})
                or card.find("p", class_=re.compile(r"price|Price|preco", re.I))
                or card.find("span", class_=re.compile(r"price|Price", re.I))
                or card.find("strong")
            )
            preco_texto = preco_el.get_text(strip=True) if preco_el else ""
            preco_num = extrair_preco(preco_texto)

            if preco_num is None:
                continue  # Sem preço válido, salta

            anuncios.append({
                "id": anuncio_id,
                "titulo": titulo,
                "preco_num": preco_num,
                "preco_texto": preco_texto,
                "link": link,
            })

        except Exception as e:
            log(f"  [OLX] Erro ao processar card: {e}")
            continue

    return anuncios


# ──────────────────────────────────────────────────────────────────────
# LÓGICA DE MÉDIA
# ──────────────────────────────────────────────────────────────────────

def calcular_media(anuncios: list[dict], n: int = AMOSTRAS_PARA_MEDIA) -> Optional[float]:
    """
    Calcula a média de mercado usando os primeiros N anúncios com preço válido.
    Usa mediana em vez de média para resistir a outliers (ex: anúncios com preço
    absurdo de 1€ ou 9999€).
    """
    precos = [a["preco_num"] for a in anuncios if a.get("preco_num")][:n]
    if len(precos) < 3:
        log(f"  Amostras insuficientes para calcular média ({len(precos)} encontradas).")
        return None
    # Remove outliers extremos (fora de 2 desvios padrão)
    media_bruta = statistics.mean(precos)
    desvio = statistics.stdev(precos) if len(precos) > 1 else 0
    precos_filtrados = [p for p in precos if abs(p - media_bruta) <= 2 * desvio]
    if not precos_filtrados:
        precos_filtrados = precos
    return statistics.median(precos_filtrados)


def media_valida(dados: dict, modelo: str) -> Optional[float]:
    """Verifica se a média guardada ainda é válida (dentro do prazo)."""
    medias = dados.get("medias", {})
    if modelo not in medias:
        return None
    entrada = medias[modelo]
    timestamp = entrada.get("timestamp", "")
    if not timestamp:
        return None
    try:
        guardada = datetime.fromisoformat(timestamp)
        horas_passadas = (datetime.now() - guardada).total_seconds() / 3600
        if horas_passadas < HORAS_VALIDADE_MEDIA:
            return entrada.get("valor")
    except ValueError:
        pass
    return None


def guardar_media(dados: dict, modelo: str, valor: float):
    """Guarda a média calculada com timestamp."""
    if "medias" not in dados:
        dados["medias"] = {}
    dados["medias"][modelo] = {
        "valor": round(valor, 2),
        "timestamp": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────
# PROCESSAMENTO PRINCIPAL
# ──────────────────────────────────────────────────────────────────────

def processar_modelo(modelo: str, url: str, dados: dict) -> int:
    """
    Processa um modelo:
      1. Obtém anúncios da página
      2. Calcula/usa média em cache
      3. Para cada anúncio novo, verifica desconto e notifica
    Devolve o número de alertas enviados.
    """
    log(f"\n🔍 A verificar: {modelo}")
    alertas_enviados = 0

    anuncios = scrape_olx_pagina(url)
    if not anuncios:
        log(f"  Sem anúncios encontrados para {modelo}.")
        return 0

    log(f"  {len(anuncios)} anúncio(s) recolhido(s).")

    # --- Média de mercado ---
    media = media_valida(dados, modelo)
    if media is None:
        log(f"  A calcular média de mercado com {AMOSTRAS_PARA_MEDIA} amostras...")
        media = calcular_media(anuncios)
        if media is None:
            log(f"  ⚠️ Não foi possível calcular a média para {modelo}. A saltar.")
            return 0
        guardar_media(dados, modelo, media)
        log(f"  📊 Média calculada: {media:.0f} €")
    else:
        log(f"  📊 Média em cache: {media:.0f} € (válida por mais {HORAS_VALIDADE_MEDIA}h)")

    limiar = media * (1 - DESCONTO_MINIMO)

    # --- Verificar novos anúncios ---
    vistos = dados.get("vistos", [])
    novos_nesta_execucao = 0

    for anuncio in anuncios:
        aid = anuncio["id"]

        if aid in vistos:
            continue

        # Marca como visto independentemente do preço
        vistos.append(aid)
        novos_nesta_execucao += 1

        preco = anuncio["preco_num"]

        if preco > limiar:
            continue  # Preço acima do limiar — não notifica

        desconto_pct = ((media - preco) / media) * 100
        log(
            f"  🔥 NEGÓCIO! {anuncio['titulo']} — "
            f"{preco}€ (média: {media:.0f}€, -{desconto_pct:.1f}%)"
        )

        mensagem = montar_alerta(modelo, anuncio, media, desconto_pct)
        if enviar_telegram(mensagem):
            alertas_enviados += 1
            log(f"  ✅ Alerta enviado via Telegram.")
        else:
            log(f"  ❌ Falha ao enviar Telegram.")

        time.sleep(1)  # Pausa para não fazer flood

    dados["vistos"] = vistos
    log(f"  {novos_nesta_execucao} novo(s) anúncio(s) analisado(s).")
    return alertas_enviados


# ──────────────────────────────────────────────────────────────────────
# ENTRADA PRINCIPAL
# ──────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("▶️  MONITOR DE iPHONES INICIADO")
    log(f"   Modelos: {len(MODELOS)} | Desconto mínimo: {DESCONTO_MINIMO*100:.0f}%")
    log("=" * 60)

    dados = carregar_dados()
    total_alertas = 0

    for modelo, url in MODELOS.items():
        alertas = processar_modelo(modelo, url, dados)
        total_alertas += alertas
        guardar_dados(dados)         # Guarda após cada modelo (safe)
        time.sleep(3)                # Pausa entre modelos (evita ban do OLX)

    log("\n" + "=" * 60)
    log(f"✔️  CONCLUÍDO — {total_alertas} alerta(s) enviado(s).")
    log("=" * 60 + "\n")


if __name__ == "__main__":
    main()
