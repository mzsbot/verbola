import requests
from bs4 import BeautifulSoup
import json
import os

URL = "https://ondebola.com/"
OUTPUT_FILE = "jogos.json"

def get_games():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(URL, headers=headers)
    
    if response.status_code != 200:
        print("Erro ao aceder ao site.")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    games = []
    
    # NOTA: Estes seletores dependem da estrutura HTML atual do ondebola.com.
    # É necessário inspecionar os elementos no navegador caso a lista venha vazia.
    rows = soup.select('tr') # Assume que os jogos estão em tabelas
    
    for idx, row in enumerate(rows):
        cols = row.find_all('td')
        if len(cols) >= 3:
            try:
                date_time = cols[0].get_text(strip=True)
                teams = cols[1].get_text(separator=" - ", strip=True)
                channel = cols[2].get_text(strip=True)
                
                games.append({
                    "id": idx,
                    "date": date_time,
                    "match": teams,
                    "channel": channel
                })
            except Exception:
                continue

    return games

if __name__ == "__main__":
    games_data = get_games()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games_data, f, ensure_ascii=False, indent=2)
    print(f"Extração concluída. {len(games_data)} jogos guardados.")