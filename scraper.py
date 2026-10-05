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
        
        # Ignora blocos de publicidade ou linhas incompletas
        if len(cols) >= 3 and not 'pub' in row.get('class', []):
            try:
                # --- 1. DATA E HORA ---
                date_strings = list(cols[0].stripped_strings)
                is_today = any('hoje' in s.lower() for s in date_strings)
                # Remove a palavra 'hoje' da lista de texto
                date_strings = [s for s in date_strings if 'hoje' not in s.lower()]
                
                date_val = date_strings[0] if len(date_strings) > 0 else ""
                time_val = date_strings[1] if len(date_strings) > 1 else ""

                # --- 2. EQUIPAS, COMPETIÇÃO E BANDEIRAS ---
                flags = []
                for img in cols[1].find_all('img'):
                    src = img.get('src')
                    if src:
                        if src.startswith('/'): 
                            src = f"https://ondebola.com{src}"
                        elif not src.startswith('http'): 
                            src = f"https://ondebola.com/{src}"
                        flags.append(src)
                    # Remove a imagem do HTML para não colar palavras quando extrairmos o texto
                    img.extract() 
                
                # Extrai o texto limpo, separado por '|'
                team_text = cols[1].get_text(separator='|', strip=True)
                team_parts = [p.strip() for p in team_text.split('|') if p.strip() and p.strip() != '-']
                
                if len(team_parts) >= 2:
                    match_teams = team_parts[0]
                    competition = team_parts[-1]
                elif len(team_parts) == 1:
                    match_teams = team_parts[0]
                    competition = ""
                else:
                    match_teams = "N/D"
                    competition = ""

                # --- 3. CANAIS ---
                for img in cols[2].find_all('img'):
                    img.extract() 
                    
                channels_raw = [p.strip() for p in cols[2].get_text(separator='|', strip=True).split('|') if p.strip()]
                # Filtra lixo como o texto invisível "LiveModeTv"
                channels = [c for c in channels_raw if c.lower() != 'livemodetv']

                games.append({
                    "id": idx,
                    "date": date_val,
                    "time": time_val,
                    "is_today": is_today,
                    "match": match_teams,
                    "competition": competition,
                    "flags": flags,
                    "channels": channels
                })
            except Exception as e:
                print(f"Erro a processar linha {idx}: {e}")
                continue

    return games

if __name__ == "__main__":
    games_data = get_games()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games_data, f, ensure_ascii=False, indent=2)