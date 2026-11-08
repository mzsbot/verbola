import os
import sys
import requests
from datetime import datetime, timedelta

from build_games import find_fixture
from common import (
    COMPETITIONS_FILE, EPG_FILE, FIXTURES_FILE, LISBON, DAYS_AHEAD,
    load_env, now_lisbon, read_json, write_json, load_allowed_leagues, is_allowed
)

# Jogos reais para validar as emissões do EPG (sobretudo da DAZN, que não distingue direto
# de repetição) e para acertar a hora do pontapé de saída.
# Fonte principal: football-data.org (plano gratuito com ~12 competições, até 10 dias por pedido).
# Complemento: API-Football para as competições que o football-data.org não tem (o plano
# gratuito só dá ontem, hoje e amanhã)
API_FOOTBALL_URL  = "https://v3.football.api-sports.io/fixtures"
FOOTBALL_DATA_URL = "https://api.football-data.org/v4/matches"

# API-Football: 100 pedidos/dia; cada atualização gasta 3 (ontem, hoje e amanhã), ~24 por dia.
# football-data.org: 10 pedidos/minuto; cada atualização gasta 1.
REFRESH_EVERY = timedelta(hours=3)

# Jogos adiados ou cancelados: guardam-se à parte para retirar as emissões que o EPG ainda tem
SKIP_API_FOOTBALL  = {"PST", "CANC", "ABD"}
SKIP_FOOTBALL_DATA = {"POSTPONED", "CANCELLED", "SUSPENDED"}

def fetch_api_football(api_key, day):
    response = requests.get(
        API_FOOTBALL_URL,
        headers={"x-apisports-key": api_key},
        params={"date": day.isoformat(), "timezone": "Europe/Lisbon"},
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    # A API devolve 200 mesmo com erros (chave inválida, limite atingido, data fora do plano)
    if data.get("errors"):
        raise RuntimeError(f"API-Football: {data['errors']}")

    remaining = response.headers.get("x-ratelimit-requests-remaining")
    print(f"API-Football: {data.get('results')} jogos em {day}; pedidos restantes hoje: {remaining}")
    return [
        {
            "id": item["fixture"]["id"],
            "source": "api-football",
            "kickoff": item["fixture"]["date"],
            "league_id": item["league"]["id"],
            "league": item["league"]["name"],
            "home": item["teams"]["home"]["name"],
            "away": item["teams"]["away"]["name"],
            "postponed": item["fixture"]["status"]["short"] in SKIP_API_FOOTBALL
        }
        for item in data.get("response", [])
    ]

def football_data_leagues():
    # {código do football-data.org: id da liga na API-Football}, a partir do competitions.json,
    # para os jogos das duas fontes usarem os mesmos ids (allowed_competitions, ícones)
    result = {}
    for info in (read_json(COMPETITIONS_FILE, {}) or {}).values():
        if info.get("football_data_code") and info.get("api_football_ids"):
            result[info["football_data_code"]] = info["api_football_ids"][0]
    return result

def fetch_football_data(token, date_from, date_to):
    response = requests.get(
        FOOTBALL_DATA_URL,
        headers={"X-Auth-Token": token},
        params={"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()},
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    leagues = football_data_leagues()
    matches = data.get("matches", [])
    print(f"football-data.org: {len(matches)} jogos de {date_from} a {date_to}")

    fixtures, unknown = [], set()
    for item in matches:
        code = item["competition"]["code"]
        if code not in leagues:
            unknown.add(f'{code} ({item["competition"]["name"]})')
            continue
        kickoff = datetime.fromisoformat(item["utcDate"].replace("Z", "+00:00")).astimezone(LISBON)
        fixtures.append({
            "id": f"fd-{item['id']}",
            "source": "football-data",
            "kickoff": kickoff.isoformat(),
            "league_id": leagues[code],
            "league": item["competition"]["name"],
            "home": item["homeTeam"]["shortName"] or item["homeTeam"]["name"],
            "away": item["awayTeam"]["shortName"] or item["awayTeam"]["name"],
            "postponed": item["status"] in SKIP_FOOTBALL_DATA
        })

    if unknown:
        print(f"football-data.org: ignoradas por não terem football_data_code no competitions.json: {', '.join(sorted(unknown))}")
    return fixtures

def with_channel(fixtures, programmes):
    # Das centenas de jogos por dia só interessam os que têm emissão no EPG; guardar
    # só esses evita que o ficheiro commitado faça crescer o repositório
    ids = {f["id"] for f in (find_fixture(p, fixtures) for p in programmes) if f}
    return [f for f in fixtures if f["id"] in ids]

def needs_refresh(cache, now, force):
    if force or not cache:
        return True
    if cache["date"] != now.date().isoformat():
        return True
    return now - datetime.fromisoformat(cache["fetched_at"]) >= REFRESH_EVERY

def fetch_source(name, fetch, previous):
    # Se uma das fontes falhar, mantém os jogos dela da última atualização
    try:
        return fetch(), True
    except Exception as e:
        print(f"Erro em {name}: {e}; a usar os jogos guardados")
        return [f for f in previous if f.get("source") == name], False

if __name__ == "__main__":
    load_env()
    force     = "--force" in sys.argv
    now       = now_lisbon()
    today     = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow  = today + timedelta(days=1)

    api_key = os.environ.get("API_FOOTBALL_KEY")
    fd_key  = os.environ.get("FOOTBALL_DATA_KEY")
    if not api_key or not fd_key:
        print("API_FOOTBALL_KEY e FOOTBALL_DATA_KEY têm de estar definidas (secrets do GitHub ou .env local)")
        sys.exit(1)

    cache = read_json(FIXTURES_FILE)
    if not needs_refresh(cache, now, force):
        print("Dados das APIs recentes; pedidos saltados (usa --force para forçar)")
        sys.exit(0)

    epg = read_json(EPG_FILE)
    if not epg:
        print(f"Sem dados do EPG em {EPG_FILE}; corre primeiro o scrape_channels.py")
        sys.exit(1)

    previous = cache["fixtures"] if cache else []
    fd_fixtures, fd_ok = fetch_source(
        "football-data",
        # De ontem até DAYS_AHEAD dias depois de hoje; o dateTo não inclui esse dia, daí o +1
        lambda: fetch_football_data(fd_key, yesterday, today + timedelta(days=DAYS_AHEAD + 1)),
        previous
    )
    api_fixtures, api_ok = fetch_source(
        "api-football",
        lambda: [f for day in (yesterday, today, tomorrow) for f in fetch_api_football(api_key, day)],
        previous
    )
    if not api_ok and not fd_ok:
        print("As duas fontes falharam; dados anteriores mantidos")
        sys.exit(1)

    # O football-data.org é a fonte principal; da API-Football só entram as competições que
    # ele não cobre (Liga Europa, Liga das Nações, taças...), para não haver jogos repetidos
    fd_leagues   = set(football_data_leagues().values())
    api_fixtures = [f for f in api_fixtures if f["league_id"] not in fd_leagues]

    # Só as competições do allowed_competitions.json
    allowed  = load_allowed_leagues()
    fixtures  = [f for f in api_fixtures + fd_fixtures if is_allowed(f, allowed)]
    postponed = [f for f in fixtures if f["postponed"]]
    fixtures  = with_channel([f for f in fixtures if not f["postponed"]], epg["programmes"])
    fixtures.sort(key=lambda f: f["kickoff"])

    write_json(FIXTURES_FILE, {
        "fetched_at": now.isoformat(), "date": today.isoformat(),
        "fixtures": fixtures, "postponed": postponed
    })
    print(f"{len(fixtures)} jogos e {len(postponed)} adiados/cancelados guardados em {FIXTURES_FILE}")
