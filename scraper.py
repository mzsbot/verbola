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
                # 1. Separar Data e Hora (e verificar marcador 'hoje')
                col0_lines = [line.strip() for line in cols[0].get_text(separator="\n").split('\n') if line.strip()]
                is_today = any('hoje' in line.lower() for line in col0_lines)
                col0_lines = [line for line in col0_lines if 'hoje' not in line.lower()]
                
                date_val = col0_lines[0] if len(col0_lines) > 0 else ""
                time_val = col0_lines[1] if len(col0_lines) > 1 else ""

                # 2. Separar Equipas e Competição
                col1_lines = [line.strip() for line in cols[1].get_text(separator="\n").split('\n') if line.strip()]
                match_teams = col1_lines[0] if len(col1_lines) > 0 else "N/D"
                competition = col1_lines[1] if len(col1_lines) > 1 else ""

                # 3. Extrair Canal
                channel = cols[2].get_text(separator=" ", strip=True)
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