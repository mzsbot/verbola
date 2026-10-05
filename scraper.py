import requests
from bs4 import BeautifulSoup
import json
import re

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
    
    # Procura as linhas da tabela
    rows = soup.select('tr')
    
    for idx, row in enumerate(rows):
        cols = row.find_all('td')
        if len(cols) >= 3:
            try:
                # 1. Tratar Data e Hora (remover a palavra "hoje" que suja a string)
                date_time_raw = cols[0].get_text(separator=" ", strip=True)
                date_time_clean = date_time_raw.replace("hoje", "").strip()
                
                # 2. Tratar Equipas e Competição
                # O site coloca as equipas e a competição na mesma célula. Vamos separar.
                teams_comp_raw = cols[1].get_text(separator="|", strip=True)
                parts = teams_comp_raw.split('|')
                
                if len(parts) >= 2:
                    match_teams = parts[0].strip()
                    competition = parts[1].strip()
                    # Limpar traços excessivos nas equipas (ex: Chipre - - Letónia)
                    match_teams = re.sub(r'\s*-\s*-\s*', ' - ', match_teams)
                else:
                    match_teams = teams_comp_raw
                    competition = ""
                
                # Juntar as equipas e a competição de forma limpa para o frontend
                match_display = f"{match_teams} <span class='text-xs text-gray-400 block mt-1'>{competition}</span>"

                # 3. Tratar Canal (remover espaços extra se houver mais de um canal)
                channel = cols[2].get_text(separator=" ", strip=True)
                if not channel:
                    channel = "N/D"
                
                games.append({
                    "id": idx,
                    "date": date_time_clean,
                    "match": match_display,
                    "channel": channel
                })
            except Exception as e:
                print(f"Erro ao processar linha {idx}: {e}")
                continue

    return games

if __name__ == "__main__":
    games_data = get_games()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games_data, f, ensure_ascii=False, indent=2)
    print(f"Extração concluída. {len(games_data)} jogos guardados.")