import os
import re
import sys
import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from common import (
    CHANNELS_FILE, COMPETITIONS_FILE, FIXTURES_FILE, OUTPUT_FILE,
    load_env, now_lisbon, read_json, write_json, fold, load_competitions, match_competition
)

API_URL = "https://v3.football.api-sports.io/fixtures"

# Plano gratuito: 100 pedidos/dia. Com o cron de 15 em 15 min só se pede à API
# quando há jogos a decorrer ou quando os dados guardados ficaram antigos.
REFRESH_EVERY = timedelta(hours=3)
LIVE_REFRESH  = timedelta(minutes=10)
LIVE_BEFORE   = timedelta(minutes=15)
LIVE_AFTER    = timedelta(minutes=150)
MIN_REMAINING = 5

# Diferença máxima entre a hora do ondebola e a da API para considerar o mesmo jogo
MAX_KICKOFF_DIFF = timedelta(minutes=20)
MIN_SIMILARITY   = 0.6

# Palavras que não ajudam a distinguir equipas ("SL Benfica W" -> "benfica")
TEAM_STOPWORDS = {"fc", "cf", "sc", "ac", "afc", "sl", "cd", "ud", "sad", "club", "de", "da", "do", "w", "u19", "u20", "u21", "u23", "ii"}

def team_tokens(name):
    tokens = re.sub(r'[^a-z0-9 ]', ' ', fold(name)).split()
    return [t for t in tokens if t not in TEAM_STOPWORDS] or tokens

def team_similarity(a, b):
    ta, tb = team_tokens(a), team_tokens(b)
    if not ta or not tb:
        return 0.0

    # "man city" vs "manchester city": cada palavra da mais curta é início de uma da outra
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    prefix = sum(1 for s in short if any(l.startswith(s) or s.startswith(l) for l in long_)) / len(short)

    # "bolonha" vs "bologna": semelhança de caracteres
    ratio = SequenceMatcher(None, ' '.join(ta), ' '.join(tb)).ratio()
    return max(prefix, ratio)

def fixture_from_api(item):
    return {
        "id": item["fixture"]["id"],
        "kickoff": item["fixture"]["date"],
        "status": item["fixture"]["status"]["short"],
        "elapsed": item["fixture"]["status"]["elapsed"],
        "league_id": item["league"]["id"],
        "league": item["league"]["name"],
        "home": item["teams"]["home"]["name"],
        "away": item["teams"]["away"]["name"],
        "goals": item["goals"]
    }

def is_live_window(games, now):
    for game in games:
        kickoff = datetime.fromisoformat(game["kickoff"])
        if kickoff - LIVE_BEFORE <= now <= kickoff + LIVE_AFTER:
            return True
    return False

def needs_refresh(cache, games, now, force):
    if force or not cache:
        return True
    if cache["date"] != now.date().isoformat():
        return True
    age = now - datetime.fromisoformat(cache["fetched_at"])
    if age >= REFRESH_EVERY:
        return True
    return age >= LIVE_REFRESH and is_live_window(games, now)

def fetch_fixtures(api_key, day):
    response = requests.get(
        API_URL,
        headers={"x-apisports-key": api_key},
        params={"date": day, "timezone": "Europe/Lisbon"},
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    # A API devolve 200 mesmo com erros (chave inválida, limite atingido)
    if data.get("errors"):
        raise RuntimeError(f"API-Football: {data['errors']}")

    remaining = response.headers.get("x-ratelimit-requests-remaining")
    print(f"API-Football: {data.get('results')} jogos em {day}; pedidos restantes hoje: {remaining}")
    return [fixture_from_api(item) for item in data.get("response", [])]

def find_fixture(game, fixtures):
    kickoff = datetime.fromisoformat(game["kickoff"])
    best, best_score = None, MIN_SIMILARITY

    for fixture in fixtures:
        if abs(datetime.fromisoformat(fixture["kickoff"]) - kickoff) > MAX_KICKOFF_DIFF:
            continue
        score = (team_similarity(game["home"], fixture["home"]) + team_similarity(game["away"], fixture["away"])) / 2
        if score > best_score:
            best, best_score = fixture, score
    return best

def build_games(games, fixtures, competitions_by_league, lookup, now):
    output = []
    for game in games:
        fixture = find_fixture(game, fixtures)

        competition = game["competition"]
        competition_key, competition_icon = match_competition(competition, lookup)

        # Sem correspondência pelo nome do ondebola, tenta pelo id da liga na API
        if fixture and not competition_key and fixture["league_id"] in competitions_by_league:
            competition_key, name, competition_icon = competitions_by_league[fixture["league_id"]]
            competition = competition or name

        kickoff = datetime.fromisoformat(fixture["kickoff"] if fixture else game["kickoff"])

        output.append({
            "sport": "futebol",
            "kickoff": kickoff.isoformat(),
            "date": game["date"],
            "time": kickoff.strftime("%H:%M"),
            "is_today": kickoff.date() == now.date(),
            "match": f"{game['home']} - {game['away']}" if game["away"] else game["home"],
            "competition": competition,
            "competition_key": competition_key,
            "competition_icon": competition_icon,
            "channels": game["channels"],
            "fixture_id": fixture["id"] if fixture else None,
            "status": fixture["status"] if fixture else None,
            "elapsed": fixture["elapsed"] if fixture else None,
            "score": fixture["goals"] if fixture and fixture["goals"]["home"] is not None else None
        })

    output.sort(key=lambda g: g["kickoff"])
    for idx, game in enumerate(output):
        game["id"] = idx
    return output

def competitions_by_api_league(lookup):
    # {id da liga na API: (chave, nome, ícone)} a partir do campo "api_football_ids"
    result = {}
    icons  = {key: icon for key, icon in lookup.values()}
    for key, info in (read_json(COMPETITIONS_FILE, {}) or {}).items():
        for league_id in info.get("api_football_ids", []):
            result[league_id] = (key, info.get("name"), icons.get(key))
    return result

if __name__ == "__main__":
    load_env()
    force = "--force" in sys.argv
    now   = now_lisbon()

    channels = read_json(CHANNELS_FILE)
    if not channels:
        print(f"Sem dados de canais em {CHANNELS_FILE}; corre primeiro o scrape_channels.py")
        sys.exit(1)
    games = channels["games"]

    cache     = read_json(FIXTURES_FILE)
    api_key   = os.environ.get("API_FOOTBALL_KEY")
    refreshed = False

    if not api_key:
        print("API_FOOTBALL_KEY não definida; a usar só os dados do ondebola")
    elif needs_refresh(cache, games, now, force):
        try:
            fixtures  = fetch_fixtures(api_key, now.date().isoformat())
            cache     = {"fetched_at": now.isoformat(), "date": now.date().isoformat(), "fixtures": fixtures}
            refreshed = True
        except Exception as e:
            # Falha da API não impede a atualização: usa a última resposta guardada
            print(f"Erro ao contactar a API-Football: {e}")
    else:
        print("Dados da API recentes; pedido saltado")

    fixtures = cache["fixtures"] if cache else []
    lookup   = load_competitions()
    result   = build_games(games, fixtures, competitions_by_api_league(lookup), lookup, now)
    write_json(OUTPUT_FILE, result)

    if refreshed:
        # Guarda só os jogos associados (~500 por dia -> uma dúzia), para o ficheiro
        # commitado a cada execução não fazer crescer o repositório
        matched_ids = {g["fixture_id"] for g in result if g["fixture_id"]}
        cache["fixtures"] = [f for f in fixtures if f["id"] in matched_ids]
        write_json(FIXTURES_FILE, cache)

    matched = sum(1 for g in result if g["fixture_id"])
    print(f"{len(result)} jogos guardados em {OUTPUT_FILE} ({matched} ligados à API-Football)")

    unmatched = sorted({g["competition"] for g in result if g["competition"] and not g["competition_key"]})
    for name in unmatched:
        print(f"Competição sem correspondência: {name}")
