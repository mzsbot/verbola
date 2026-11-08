import os
import sys
import requests
from datetime import datetime, timedelta

from build_games import find_fixture
from common import (
    EPG_FILE, FIXTURES_FILE,
    load_env, now_lisbon, read_json, write_json, load_allowed_leagues, is_allowed
)

API_URL = "https://v3.football.api-sports.io/fixtures"

# Plano gratuito: 100 pedidos/dia e só datas de ontem a amanhã. Cada atualização
# gasta 2 pedidos (hoje e amanhã); de 3 em 3 horas são ~16 pedidos por dia.
REFRESH_EVERY = timedelta(hours=3)

def fixture_from_api(item):
    return {
        "id": item["fixture"]["id"],
        "kickoff": item["fixture"]["date"],
        "status": item["fixture"]["status"]["short"],
        "league_id": item["league"]["id"],
        "league": item["league"]["name"],
        "country": item["league"]["country"],
        "home": item["teams"]["home"]["name"],
        "away": item["teams"]["away"]["name"]
    }

def fetch_fixtures(api_key, day):
    response = requests.get(
        API_URL,
        headers={"x-apisports-key": api_key},
        params={"date": day, "timezone": "Europe/Lisbon"},
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    # A API devolve 200 mesmo com erros (chave inválida, limite atingido, data fora do plano)
    if data.get("errors"):
        raise RuntimeError(f"API-Football: {data['errors']}")

    remaining = response.headers.get("x-ratelimit-requests-remaining")
    print(f"API-Football: {data.get('results')} jogos em {day}; pedidos restantes hoje: {remaining}")
    return [fixture_from_api(item) for item in data.get("response", [])]

def with_channel(fixtures, programmes):
    # Dos ~1200 jogos/dia da API só interessam os que têm emissão no EPG; guardar
    # só esses evita que o ficheiro commitado faça crescer o repositório
    ids = {f["id"] for f in (find_fixture(p, fixtures) for p in programmes) if f}
    return [f for f in fixtures if f["id"] in ids]

def needs_refresh(cache, now, force):
    if force or not cache:
        return True
    if cache["date"] != now.date().isoformat():
        return True
    return now - datetime.fromisoformat(cache["fetched_at"]) >= REFRESH_EVERY

if __name__ == "__main__":
    load_env()
    force   = "--force" in sys.argv
    now     = now_lisbon()
    api_key = os.environ.get("API_FOOTBALL_KEY")

    if not api_key:
        print("API_FOOTBALL_KEY não definida (secret do GitHub ou .env local)")
        sys.exit(1)

    if not needs_refresh(read_json(FIXTURES_FILE), now, force):
        print("Dados da API recentes; pedido saltado (usa --force para forçar)")
        sys.exit(0)

    epg = read_json(EPG_FILE)
    if not epg:
        print(f"Sem dados do EPG em {EPG_FILE}; corre primeiro o scrape_channels.py")
        sys.exit(1)

    days     = [now.date(), now.date() + timedelta(days=1)]
    fixtures = []
    for day in days:
        fixtures += fetch_fixtures(api_key, day.isoformat())

    # Só as competições do allowed_competitions.json
    allowed  = load_allowed_leagues()
    fixtures = [f for f in fixtures if is_allowed(f, allowed)]
    fixtures = with_channel(fixtures, epg["programmes"])
    fixtures.sort(key=lambda f: f["kickoff"])

    write_json(FIXTURES_FILE, {"fetched_at": now.isoformat(), "date": now.date().isoformat(), "fixtures": fixtures})
    print(f"{len(fixtures)} jogos guardados em {FIXTURES_FILE}")
