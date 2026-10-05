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
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    games = []
    
    # O OndeBola usa <tr> para as linhas e <td> para as colunas
    rows = soup.select('tr')
    
    for idx, row in enumerate(rows):
        cols = row.find_all('td')
        
        # Ignorar linhas de publicidade (geralmente não têm 3 ou 4 colunas com dados de jogo)
        if len(cols) >= 3 and not row.get('class') == ['pub']:
            try:
                # --- COLUNA 1: Data e Hora ---
                col1_html = str(cols[0])
                # Substituir <br> por | para separar facilmente
                col1_clean = re.sub(r'<br\s*/?>', '|', col1_html)
                col1_soup = BeautifulSoup(col1_clean, 'html.parser')
                col1_text = col1_soup.get_text(strip=True)
                
                date_parts = [p.strip() for p in col1_text.split('|') if p.strip()]
                
                date_val = date_parts[0] if len(date_parts) > 0 else ""
                
                # A segunda parte costuma ter a hora e a palavra "hoje"
                time_str_raw = date_parts[1] if len(date_parts) > 1 else ""
                is_today = "hoje" in time_str_raw.lower()
                time_val = time_str_raw.lower().replace("hoje", "").strip()

                # --- COLUNA 2: Equipas, Competição e Bandeiras ---
                # Extrair as bandeiras (imagens) primeiro
                images = cols[1].find_all('img')
                flags = []
                for img in images:
                    src = img.get('src')
                    if src:
                        # Se o URL da imagem for relativo, converte para absoluto
                        if src.startswith('/'):
                            src = f"https://ondebola.com{src}"
                        elif not src.startswith('http'):
                            src = f"https://ondebola.com/{src}"
                        flags.append(src)

                # Extrair Equipas e Competição
                col2_html = str(cols[1])
                # Remover as imagens para não sujar o texto
                col2_clean_img = re.sub(r'<img[^>]*>', '', col2_html)
                # Substituir <br> e <span> por |
                col2_clean = re.sub(r'<br\s*/?>|<span[^>]*>', '|', col2_clean_img)
                col2_soup = BeautifulSoup(col2_clean, 'html.parser')
                col2_text = col2_soup.get_text(separator='|', strip=True)
                
                # Limpar traços múltiplos " - - - "
                col2_text = re.sub(r'(\s*-\s*){2,}', ' - ', col2_text)
                
                team_parts = [p.strip() for p in col2_text.split('|') if p.strip() and p.strip() != '-']
                
                match_teams = team_parts[0] if len(team_parts) > 0 else "N/D"
                competition = team_parts[1] if len(team_parts) > 1 else ""

                # --- COLUNA 3: Canal ---
                # Limpar as bolinhas (ex: Betano 🔴) que estão em <img> ou <span>
                col3_html = str(cols[2])
                col3_clean_img = re.sub(r'<img[^>]*>', '', col3_html)
                col3_clean = re.sub(r'<br\s*/?>|<span[^>]*>|</span>', '|', col3_clean_img)
                col3_soup = BeautifulSoup(col3_clean, 'html.parser')
                
                # Extrair os canais (podem ser múltiplos, ex: Sport.Tv6 e Betano)
                channels_raw = [p.strip() for p in col3_soup.get_text(separator='|').split('|') if p.strip()]
                # Filtrar links vazios e garantir que pegamos os nomes limpos
                channels = [c for c in channels_raw if c and c.lower() != 'livemodetv']

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