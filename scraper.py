import requests
from bs4 import BeautifulSoup
import json

URL = "https://ondebola.com/"
OUTPUT_FILE = "jogos.json"

def get_games():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(URL, headers=headers)
    
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    games = []
    rows = soup.select('tr')
    
    for idx, row in enumerate(rows):
        cols = row.find_all('td')
        if len(cols) >= 3:
            try:
                # 1. Extrair Data, Hora e verificar se é Hoje
                date_strings = list(cols[0].stripped_strings)
                is_today = any(s.lower() == 'hoje' for s in date_strings)
                date_strings = [s for s in date_strings if s.lower() != 'hoje']
                
                date_val = date_strings[0] if len(date_strings) > 0 else ""
                time_val = date_strings[1] if len(date_strings) > 1 else ""

                # 2. Extrair Equipas e Competição
                team_strings = list(cols[1].stripped_strings)
                match_teams = team_strings[0] if len(team_strings) > 0 else "N/D"
                competition = team_strings[1] if len(team_strings) > 1 else ""

                # 3. Extrair Canal
                channel = " ".join(cols[2].stripped_strings)
                if not channel:
                    channel = "N/D"
                
                games.append({
                    "id": idx,
                    "date": date_val,
                    "time": time_val,
                    "is_today": is_today,
                    "match": match_teams,
                    "competition": competition,
                    "channel": channel
                })
            except Exception:
                continue

    return games

if __name__ == "__main__":
    games_data = get_games()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games_data, f, ensure_ascii=False, indent=2)