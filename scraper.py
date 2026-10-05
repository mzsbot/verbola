import requests
from bs4 import BeautifulSoup
import json

URL = "https://ondebola.com/"
OUTPUT_FILE = "jogos.json"

def get_games():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(URL, headers=headers, timeout=10)
    except Exception:
        return []
        
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    games = []
    
    rows = soup.select('tr')
    
    for idx, row in enumerate(rows):
        cols = row.find_all('td')
        
        # Ignora linhas de publicidade
        if len(cols) >= 3 and 'pub' not in row.get('class', []):
            try:
                # 1. DATA E HORA
                date_strings = [s for s in cols[0].stripped_strings]
                is_today = False
                clean_dates = []
                
                for s in date_strings:
                    if 'hoje' in s.lower():
                        is_today = True
                    else:
                        clean_dates.append(s)
                        
                date_val = clean_dates[0] if len(clean_dates) > 0 else ""
                time_val = clean_dates[1] if len(clean_dates) > 1 else ""

                # 2. EQUIPAS, COMPETIÇÃO E BANDEIRAS
                flags = []
                for img in cols[1].find_all('img'):
                    src = img.get('src')
                    if src:
                        if src.startswith('/'):
                            src = f"https://ondebola.com{src}"
                        elif not src.startswith('http'):
                            src = f"https://ondebola.com/{src}"
                        flags.append(src)
                        
                team_strings = [s for s in cols[1].stripped_strings]
                if len(team_strings) >= 2:
                    # O último texto é a competição; o resto são as equipas
                    competition = team_strings[-1]
                    match_teams = " ".join(team_strings[:-1])
                elif len(team_strings) == 1:
                    match_teams = team_strings[0]
                    competition = ""
                else:
                    match_teams = "N/D"
                    competition = ""

                # Força o espaçamento correto no hífen
                match_teams = match_teams.replace(" - ", "-").replace("-", " - ")
                match_teams = " ".join(match_teams.split())

                # 3. CANAIS
                channels = []
                for c in cols[2].stripped_strings:
                    c_clean = c.strip()
                    # Filtra lixo invisível do HTML original
                    if c_clean and 'livemodetv' not in c_clean.lower() and c_clean != '🔴':
                        channels.append(c_clean)
                        
                if not channels:
                    channels = ["N/D"]

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
                print(f"Erro na linha {idx}: {e}")
                continue

    return games

if __name__ == "__main__":
    games_data = get_games()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games_data, f, ensure_ascii=False, indent=2)