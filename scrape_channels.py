import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from common import LISBON, CHANNELS_FILE, now_lisbon, read_json, write_json

URL = "https://ondebola.com/"

# Os canais mudam pouco; evita pedir a página ao ondebola em todas as execuções de 15 em 15 min
MAX_AGE = timedelta(hours=3)

MONTHS = {
    "Jan": 1,
    "Fev": 2,
    "Mar": 3,
    "Abr": 4,
    "Mai": 5,
    "Jun": 6,
    "Jul": 7,
    "Ago": 8,
    "Set": 9,
    "Out": 10,
    "Nov": 11,
    "Dez": 12
}

def parse_pt_date(date_str, time_str):
    # "Qua 28 Out" + "16:00" -> datetime em Lisboa (o ano não vem na página)
    parts = date_str.split()
    day   = int(parts[1])
    month = MONTHS[parts[2]]

    h, m = 0, 0
    if time_str and ':' in time_str:
        h, m = map(int, time_str.split(':'))

    now  = now_lisbon()
    year = now.year
    if month < now.month - 1:
        year += 1

    return datetime(year, month, day, h, m, tzinfo=LISBON)

def parse_row(row):
    date_col    = row.select_one('td.col-date')
    desc_col    = row.select_one('td.col-desc')
    channel_col = row.select_one('td.col-channel')
    if not (date_col and desc_col and channel_col):
        return None

    date_strings = [s for s in date_col.stripped_strings if 'hoje' not in s.lower()]
    date_val = date_strings[0] if len(date_strings) > 0 else ""
    time_val = date_strings[1] if len(date_strings) > 1 else ""

    # Equipas e competição pelas classes; a competição pode vir vazia
    teams = [t.get_text(strip=True) for t in desc_col.select('.team')]
    extra = desc_col.select_one('.extra')
    competition = extra.get_text(strip=True) if extra else ""

    channels = []
    for c in channel_col.stripped_strings:
        c_clean = c.strip()
        if c_clean and 'livemodetv' not in c_clean.lower() and c_clean != '🔴':
            channels.append(c_clean)

    return {
        "source_id": row.get('data-game-id'),
        "kickoff": parse_pt_date(date_val, time_val).isoformat(),
        "date": date_val,
        "time": time_val,
        "home": teams[0] if len(teams) > 0 else "",
        "away": teams[1] if len(teams) > 1 else "",
        "competition": competition,
        "channels": channels or ["N/D"]
    }

def scrape():
    headers  = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(URL, headers=headers, timeout=10)
    response.raise_for_status()

    soup  = BeautifulSoup(response.text, 'html.parser')
    games = []
    for row in soup.select('tr'):
        if 'pub' in row.get('class', []):
            continue
        try:
            game = parse_row(row)
        except Exception as e:
            print(f"Linha ignorada: {e}")
            continue
        if game:
            games.append(game)

    games.sort(key=lambda g: g["kickoff"])
    return games

if __name__ == "__main__":
    force    = "--force" in sys.argv
    previous = read_json(CHANNELS_FILE)

    if previous and not force:
        age = now_lisbon() - datetime.fromisoformat(previous["scraped_at"])
        if age < MAX_AGE:
            print(f"Canais atualizados há {int(age.total_seconds() // 60)} min; scraping saltado (usa --force para forçar)")
            sys.exit(0)

    games = scrape()
    if not games:
        # Não substitui dados bons por uma lista vazia (ex.: o site mudou o HTML)
        print("Nenhum jogo encontrado no ondebola; dados anteriores mantidos")
        sys.exit(1)

    write_json(CHANNELS_FILE, {"scraped_at": now_lisbon().isoformat(), "games": games})
    print(f"{len(games)} jogos com canais guardados em {CHANNELS_FILE}")
