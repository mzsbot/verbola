import re
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from common import (
    COMPETITIONS_FILE, EPG_FILE, FIXTURES_FILE, OUTPUT_FILE, DAYS_AHEAD,
    now_lisbon, read_json, write_json, fold, load_competitions, match_competition,
    load_allowed_leagues, is_allowed
)

# Uma emissão é do jogo se estiver no ar no pontapé de saída (com folga para EPGs atrasados).
# As repetições (ex.: DAZN) passam noutra hora e ficam de fora sozinhas.
KICKOFF_TOLERANCE = timedelta(minutes=15)
MIN_SIMILARITY    = 0.6

WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS   = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Palavras que não ajudam a distinguir equipas ("SL Benfica W" -> "benfica")
TEAM_STOPWORDS = {"fc", "cf", "sc", "ac", "afc", "sl", "cd", "ud", "sad", "cp", "club", "de", "da", "do", "w", "u19", "u20", "u21", "u23", "ii"}

# Nomes do EPG que não se parecem nada com os da API
TEAM_ALIASES = {
    "slb": "benfica",
    "scp": "sporting",
    "fcp": "porto",
    "psg": "paris saint germain",
    "napoles": "napoli",
    "inter milao": "inter",
    "milao": "ac milan",
    "bayern munique": "bayern munchen",
}

def team_tokens(name):
    text = re.sub(r'[^a-z0-9 ]', ' ', fold(name))
    text = ' '.join(text.split())
    text = TEAM_ALIASES.get(text, text)
    tokens = text.split()
    return [t for t in tokens if t not in TEAM_STOPWORDS] or tokens

def team_similarity(a, b):
    ta, tb = team_tokens(a), team_tokens(b)
    if not ta or not tb:
        return 0.0

    # "man city" vs "manchester city": cada palavra da mais curta é início de uma da outra
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    # (palavras de 1-2 letras como "b" ou "ii" não contam, senão "ceara b" casava com "besiktas")
    prefix = sum(1 for s in short if any(min(len(s), len(l)) >= 3 and (l.startswith(s) or s.startswith(l)) for l in long_)) / len(short)

    # "bolonha" vs "bologna": semelhança de caracteres
    ratio = SequenceMatcher(None, ' '.join(ta), ' '.join(tb)).ratio()
    return max(prefix, ratio)

def find_fixture(programme, fixtures):
    start = datetime.fromisoformat(programme["start"])
    stop  = datetime.fromisoformat(programme["stop"])
    best, best_score = None, MIN_SIMILARITY

    for fixture in fixtures:
        kickoff = datetime.fromisoformat(fixture["kickoff"])
        if not (start - KICKOFF_TOLERANCE <= kickoff < stop):
            continue
        score = (team_similarity(programme["home"], fixture["home"]) +
                 team_similarity(programme["away"], fixture["away"])) / 2
        if score > best_score:
            best, best_score = fixture, score
    return best

def channel_sort_key(name):
    # "SPORT TV 10" depois de "SPORT TV 2"
    return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', name)]

def competitions_by_api_league(lookup):
    # {id da liga na API: (chave, nome, ícone)} a partir do campo "api_football_ids"
    result = {}
    icons  = {key: icon for key, _, icon in lookup.values()}
    for key, info in (read_json(COMPETITIONS_FILE, {}) or {}).items():
        for league_id in info.get("api_football_ids", []):
            result[league_id] = (key, info.get("name"), icons.get(key))
    return result

def build_games(programmes, fixtures, by_league, lookup, now):
    channels  = {}
    unmatched = []
    for programme in programmes:
        fixture = find_fixture(programme, fixtures)
        if fixture:
            channels.setdefault(fixture["id"], set()).add(programme["channel"])
        else:
            unmatched.append(programme)

    output = []
    for fixture in fixtures:
        if fixture["id"] not in channels:
            continue

        # Primeiro pelo id da liga; senão pelo nome da API nos aliases do competitions.json
        competition_key, name, icon = by_league.get(fixture["league_id"]) or match_competition(fixture["league"], lookup)
        kickoff = datetime.fromisoformat(fixture["kickoff"])

        output.append({
            "sport": "futebol",
            "kickoff": kickoff.isoformat(),
            "date": f"{WEEKDAYS[kickoff.weekday()]} {kickoff.day} {MONTHS[kickoff.month - 1]}",
            "time": kickoff.strftime("%H:%M"),
            "is_today": kickoff.date() == now.date(),
            "match": f"{fixture['home']} - {fixture['away']}",
            "competition": name or fixture["league"],
            "competition_key": competition_key,
            "competition_icon": icon,
            "league_id": fixture["league_id"],
            "channels": sorted(channels[fixture["id"]], key=channel_sort_key),
            "fixture_id": fixture["id"]
        })

    output.sort(key=lambda g: (g["kickoff"], g["match"]))
    for idx, game in enumerate(output):
        game["id"] = idx
    return output, unmatched

if __name__ == "__main__":
    now      = now_lisbon()
    epg      = read_json(EPG_FILE)
    fixtures = read_json(FIXTURES_FILE)
    if not epg or not fixtures:
        print(f"Faltam dados em {EPG_FILE} ou {FIXTURES_FILE}; corre primeiro o scrape_channels.py e o fetch_games.py")
        sys.exit(1)

    # De ontem em diante (ignora jogos mais antigos que ficaram na cache) e só as
    # competições permitidas, para retirar uma bastar editar o ficheiro, sem pedir à API
    window  = {now.date() + timedelta(days=d) for d in range(-1, DAYS_AHEAD + 1)}
    allowed = load_allowed_leagues()
    lookup  = load_competitions()
    result, unmatched = build_games(
        epg["programmes"],
        [f for f in fixtures["fixtures"]
         if datetime.fromisoformat(f["kickoff"]).date() in window and is_allowed(f, allowed)],
        competitions_by_api_league(lookup), lookup, now
    )

    # Ontem, hoje e o próximo dia com jogos (não necessariamente amanhã)
    today  = now.date()
    future = sorted({datetime.fromisoformat(g["kickoff"]).date() for g in result} - {today - timedelta(days=1), today})
    days   = [today - timedelta(days=1), today] + [d for d in future if d > today][:1]
    result = [g for g in result if datetime.fromisoformat(g["kickoff"]).date() in days]
    for idx, game in enumerate(result):
        game["id"] = idx

    write_json(OUTPUT_FILE, result)
    print(f"{len(result)} jogos guardados em {OUTPUT_FILE} ({', '.join(d.strftime('%d/%m') for d in days)})")

    # A DAZN não distingue direto de repetição, por isso as emissões dela sem jogo são esperadas
    for p in unmatched:
        start = datetime.fromisoformat(p["start"])
        if start.date() in days and not p["channel"].startswith("DAZN"):
            print(f"Emissão sem jogo (competição não permitida ou nomes diferentes): {start:%d/%m %H:%M} {p['channel']}: {p['home']} x {p['away']}")

    for name in sorted({g["competition"] for g in result if not g["competition_key"]}):
        print(f"Competição sem correspondência: {name}")
