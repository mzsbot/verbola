import io
import re
import sys
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from common import LISBON, EPG_FILE, SEARCH_CHANNELS_FILE, DAYS_AHEAD, now_lisbon, read_json, write_json, fold

URL = "https://iptv-epg.org/files/epg-pt.xml"

# O EPG muda pouco; evita descarregar os ~30 MB em todas as execuções do cron
MAX_AGE = timedelta(hours=3)

# Programas que não são o jogo em si: antevisões, resumos, repetições, magazines
NOT_LIVE = re.compile(
    r'antevisao|aquecimento|rescaldo|resumo|summary|recorded|magazine|highlights|melhores momentos'
)
NOT_LIVE_DESC = re.compile(r'^(recorde|reveja|resumo|rescaldo|antevisao)')

# Outras modalidades que a categoria "Futebol" também apanha
OTHER_SPORTS = re.compile(r'futsal|futebol de praia|beach soccer|futebol americano|e-?sports|efootball')

# "S1 — Sporting CP x Moreirense FC" ou "Sporting CP x Moreirense FC - Liga Portugal"
TEAMS = re.compile(r'^(?:S\d+\s*[—–-]\s*)?(.+?)\s+(?:x|vs\.?)\s+(.+?)(?:\s+-\s+.*)?$', re.IGNORECASE)

def parse_time(value):
    # "20261108162000 +0000" -> datetime em Lisboa
    return datetime.strptime(value, "%Y%m%d%H%M%S %z").astimezone(LISBON)

def parse_teams(title, desc):
    # A primeira linha da descrição é a fonte mais fiável (na Sport TV o título nem sempre tem equipas)
    for text in (desc.split('\n')[0], re.sub(r'\s*\([^)]*\)$', '', title)):
        match = TEAMS.match(text.strip())
        if match:
            return match.group(1).strip(" .,;"), match.group(2).strip(" .,;")
    return None, None

def is_live_football(title, desc, categories):
    text = fold(f"{title} {desc}")
    if OTHER_SPORTS.search(text):
        return False
    if not ("futebol" in categories or "futebol" in text):
        return False
    if NOT_LIVE.search(fold(title)) or NOT_LIVE_DESC.search(fold(desc.split('\n')[-1])):
        return False
    return True

def download(attempts=3):
    # Descarrega o XML inteiro antes de o ler: uma ligação cortada a meio do ficheiro
    # (~30 MB) falha aqui e volta a tentar, em vez de rebentar a meio do parse
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(URL, headers={'User-Agent': 'verbola'}, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            print(f"Erro ao descarregar o EPG (tentativa {attempt}/{attempts}): {e}")
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)

def scrape(channels, window_start, window_end):
    programmes = []
    for _, elem in ET.iterparse(io.BytesIO(download()), events=("end",)):
        if elem.tag == "programme":
            channel_id = elem.get("channel", "")
            if channel_id in channels:
                start = parse_time(elem.get("start"))
                stop  = parse_time(elem.get("stop"))
                title = elem.findtext("title", "").strip()
                desc  = elem.findtext("desc", "").strip()
                categories = {fold(c.text or "") for c in elem.findall("category")}

                if start < window_end and stop > window_start and \
                        is_live_football(title, desc, categories):
                    home, away = parse_teams(title, desc)
                    if home and away:
                        programmes.append({
                            "channel": channels[channel_id],
                            "start": start.isoformat(),
                            "stop": stop.isoformat(),
                            "title": title,
                            # Ex.: "Assiste ao jogo da UEFA Champions League entre ..." (para a competição)
                            "info": desc.splitlines()[-1][:200] if desc else "",
                            "home": home,
                            "away": away
                        })
        if elem.tag in ("programme", "channel"):
            elem.clear()

    programmes.sort(key=lambda p: (p["start"], p["channel"]))
    return programmes

if __name__ == "__main__":
    force    = "--force" in sys.argv
    now      = now_lisbon()
    previous = read_json(EPG_FILE)

    if previous and not force:
        age = now - datetime.fromisoformat(previous["scraped_at"])
        same_day = datetime.fromisoformat(previous["scraped_at"]).date() == now.date()
        if age < MAX_AGE and same_day:
            print(f"EPG atualizado há {int(age.total_seconds() // 60)} min; download saltado (usa --force para forçar)")
            sys.exit(0)

    # De ontem até DAYS_AHEAD dias depois de hoje, em Lisboa
    today        = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today - timedelta(days=1)
    window_end   = today + timedelta(days=DAYS_AHEAD + 1)

    # Canais a pesquisar no EPG: {id do XMLTV: nome mostrado no site}
    channels = {c["id"]: c["name"] for c in read_json(SEARCH_CHANNELS_FILE, [])}
    if not channels:
        print(f"Sem canais definidos em {SEARCH_CHANNELS_FILE}")
        sys.exit(1)

    programmes = scrape(channels, window_start, window_end)
    if not programmes:
        # Não substitui dados bons por uma lista vazia (ex.: o EPG mudou de formato)
        print("Nenhum jogo de futebol encontrado no EPG; dados anteriores mantidos")
        sys.exit(1)

    # O EPG vai largando os programas que já passaram; as emissões de ontem que já
    # não vêm no ficheiro mantêm-se da extração anterior
    seen = {(p["channel"], p["start"]) for p in programmes}
    for p in (previous or {}).get("programmes", []):
        if (p["channel"], p["start"]) not in seen and datetime.fromisoformat(p["start"]) >= window_start:
            programmes.append(p)
    programmes.sort(key=lambda p: (p["start"], p["channel"]))

    write_json(EPG_FILE, {"scraped_at": now.isoformat(), "programmes": programmes})
    print(f"{len(programmes)} emissões de futebol guardadas em {EPG_FILE}")
