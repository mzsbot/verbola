import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

URL = "https://ondebola.com/"
OUTPUT_FILE = "jogos.json"

def parse_pt_date(date_str, time_str):
    try:
        months = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6, 
                  "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12}
        parts = date_str.split()
        day = int(parts[1]) if len(parts) > 1 else 1
        month = months.get(parts[2], 1) if len(parts) > 2 else 1
        
        h, m = 0, 0
        if time_str and ':' in time_str:
            h, m = map(int, time_str.split(':'))
            
        pt_tz = ZoneInfo('Europe/Lisbon')
        now = datetime.now(pt_tz)
        year = now.year
        
        if month < now.month - 1:
            year += 1
            
        return datetime(year, month, day, h, m, tzinfo=pt_tz)
    except Exception:
        return datetime.now(ZoneInfo('Europe/Lisbon'))

def get_futebol_events():
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
        if len(cols) >= 3 and 'pub' not in row.get('class', []):
            try:
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

                flags = []
                for img in cols[1].find_all('img'):
                    src = img.get('src')
                    if src:
                        if src.startswith('/'): src = f"https://ondebola.com{src}"
                        elif not src.startswith('http'): src = f"https://ondebola.com/{src}"
                        flags.append(src)
                        
                team_strings = [s for s in cols[1].stripped_strings]
                if len(team_strings) >= 2:
                    competition = team_strings[-1]
                    match_teams = " ".join(team_strings[:-1])
                elif len(team_strings) == 1:
                    match_teams = team_strings[0]
                    competition = ""
                else:
                    match_teams, competition = "N/D", ""

                match_teams = match_teams.replace(" - ", "-").replace("-", " - ")
                match_teams = " ".join(match_teams.split())

                channels = []
                for c in cols[2].stripped_strings:
                    c_clean = c.strip()
                    if c_clean and 'livemodetv' not in c_clean.lower() and c_clean != '🔴':
                        channels.append(c_clean)
                        
                if not channels: channels = ["N/D"]

                games.append({
                    "sport": "futebol",
                    "sort_date": parse_pt_date(date_val, time_val),
                    "date": date_val,
                    "time": time_val,
                    "is_today": is_today,
                    "match": match_teams,
                    "competition": competition,
                    "flags": flags,
                    "channels": channels
                })
            except Exception:
                continue
    return games

def get_f1_events():
    f1_games = []
    try:
        # Repositório Oficial JSON da F1Calendar (mais rápido e atualizado)
        res = requests.get("https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2026.json", timeout=10)
        if res.status_code != 200:
            return []
            
        data = res.json()
        pt_tz = ZoneInfo('Europe/Lisbon')
        now = datetime.now(pt_tz)
        
        session_names = {
            "fp1": "Treinos Livres 1",
            "fp2": "Treinos Livres 2",
            "fp3": "Treinos Livres 3",
            "qualifying": "Qualificação",
            "sprintQualifying": "Qualificação Sprint",
            "sprint": "Sprint",
            "gp": "Corrida"
        }
        
        weekdays = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
        months_pt = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        for race in data.get("races", []):
            race_name = race.get("name", "Grande Prémio")
            sessions = race.get("sessions", {})
            
            for key, time_str in sessions.items():
                if not time_str: continue
                
                try:
                    # Converte a hora UTC do ficheiro (ex: "2026-10-09T09:30:00Z") para um objeto datetime
                    if time_str.endswith("Z"):
                        utc_dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    else:
                        utc_dt = datetime.fromisoformat(time_str)
                except Exception:
                    continue
                    
                # Converte para a hora em Portugal Continental
                pt_dt = utc_dt.astimezone(pt_tz)
                
                # Regras de limite temporal
                delta_days = (pt_dt.date() - now.date()).days
                
                # 1. Se for negativo, já passou. 2. Se for superior a 10 dias, é no futuro longo.
                if delta_days < 0 or delta_days > 10:
                    continue
                    
                session_title = session_names.get(key, key.title())
                date_val = f"{weekdays[pt_dt.weekday()]} {pt_dt.day} {months_pt[pt_dt.month]}"
                time_val = f"{pt_dt.hour:02d}:{pt_dt.minute:02d}"
                is_today = (pt_dt.date() == now.date())
                
                f1_games.append({
                    "sport": "f1",
                    "sort_date": pt_dt,
                    "date": date_val,
                    "time": time_val,
                    "is_today": is_today,
                    "match": f"{race_name} - {session_title}",
                    "competition": "Fórmula 1",
                    "flags": [],
                    "channels": ["SPORT.TV4"]
                })
    except Exception as e:
        print("Aviso: Falha na extração de F1:", e)
        
    return f1_games

if __name__ == "__main__":
    all_events = get_futebol_events() + get_f1_events()
    
    # Ordena todos os jogos (Futebol e F1) com precisão cronológica
    all_events.sort(key=lambda x: x["sort_date"])
    
    for idx, event in enumerate(all_events):
        event["id"] = idx
        event.pop("sort_date", None)
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
