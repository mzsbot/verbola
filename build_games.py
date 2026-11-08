import re
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from common import (
    COMPETITIONS_FILE, EPG_FILE, FIXTURES_FILE, OUTPUT_FILE, DAYS_AHEAD,
    now_lisbon, read_json, write_json, fold, load_competitions, load_allowed_leagues
)

# Os jogos vêm do EPG. Quando uma emissão corresponde a um jogo das APIs (fixtures.json),
# usa-se a hora real do jogo; senão estima-se pela hora da emissão.

# Canais que não distinguem direto de repetição: só contam emissões confirmadas pelas APIs
VALIDATED_CHANNELS = ("DAZN",)

# Uma emissão é de um jogo das APIs se estiver no ar no pontapé de saída (com folga para EPGs atrasados)
KICKOFF_TOLERANCE = timedelta(minutes=15)

# Resumos e "melhores momentos" duram 10-30 min; um jogo em direto ~2 horas
MIN_DURATION = timedelta(minutes=80)

# A emissão começa uns minutos antes do pontapé de saída (20:18 -> jogo às 20:30)
KICKOFF_STEP = 15

# Emissões do mesmo jogo com o pontapé de saída estimado a menos disto são o mesmo direto
# em canais diferentes; mais tarde é uma repetição
SAME_AIRING = timedelta(minutes=20)

MIN_SIMILARITY = 0.6

WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS   = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Palavras que não ajudam a distinguir equipas ("SL Benfica" -> "benfica")
TEAM_STOPWORDS = {"fc", "cf", "sc", "ac", "afc", "sl", "cd", "ud", "sad", "cp", "club", "de", "da", "do", "w", "u19", "u20", "u21", "u23", "ii"}

def team_tokens(name):
    tokens = re.sub(r'[^a-z0-9 ]', ' ', fold(name)).split()
    return [t for t in tokens if t not in TEAM_STOPWORDS] or tokens

def team_similarity(a, b):
    ta, tb = team_tokens(a), team_tokens(b)
    if not ta or not tb:
        return 0.0

    # "man city" vs "manchester city": cada palavra da mais curta é início de uma da outra
    # (palavras de 1-2 letras como "b" não contam, senão "ceara b" casava com "besiktas")
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    prefix = sum(1 for s in short if any(min(len(s), len(l)) >= 3 and (l.startswith(s) or s.startswith(l)) for l in long_)) / len(short)

    # "napoles" vs "napoli": semelhança de caracteres
    ratio = SequenceMatcher(None, ' '.join(ta), ' '.join(tb)).ratio()
    return max(prefix, ratio)

def match_score(a, b):
    return (team_similarity(a["home"], b["home"]) + team_similarity(a["away"], b["away"])) / 2

def same_match(a, b):
    return match_score(a, b) >= MIN_SIMILARITY

def find_fixture(programme, fixtures):
    # O jogo das APIs com equipas parecidas cujo pontapé de saída calha durante a emissão
    start = datetime.fromisoformat(programme["start"])
    stop  = datetime.fromisoformat(programme["stop"])
    best, best_score = None, MIN_SIMILARITY

    for fixture in fixtures:
        kickoff = datetime.fromisoformat(fixture["kickoff"])
        if not (start - KICKOFF_TOLERANCE <= kickoff < stop):
            continue
        score = match_score(programme, fixture)
        if score > best_score:
            best, best_score = fixture, score
    return best

def estimate_kickoff(start):
    # Arredonda para o quarto de hora seguinte (13:54 -> 14:00, 20:18 -> 20:30, 20:00 -> 20:00)
    start = start.replace(second=0, microsecond=0)
    return start + timedelta(minutes=-start.minute % KICKOFF_STEP)

def pretty_team(name):
    # "BULGÁRIA" -> "Bulgária" (o canal SPORT TV 7 escreve tudo em maiúsculas)
    return name.title() if name.isupper() and len(name) > 3 else name

def competition_finder():
    # Procura no texto o alias mais comprido do competitions.json ("Liga Portugal 2" ganha a
    # "Liga Portugal", "2. Bundesliga" ganha a "Bundesliga")
    lookup  = load_competitions()
    aliases = sorted(lookup, key=len, reverse=True)
    pattern = re.compile(r'(?<![a-z0-9])(' + '|'.join(re.escape(a) for a in aliases) + r')(?![a-z0-9])')

    def find(*texts):
        for text in texts:
            match = pattern.search(fold(text))
            if match:
                return lookup[match.group(1)]
        return (None, None, None)
    return find

def league_ids_by_key():
    return {key: set(info.get("api_football_ids", [])) for key, info in (read_json(COMPETITIONS_FILE, {}) or {}).items()}

def competitions_by_league():
    # {id da liga: (chave, nome, ícone)}, para os jogos que vêm das APIs
    lookup = load_competitions()
    icons  = {key: icon for key, _, icon in lookup.values()}
    result = {}
    for key, info in (read_json(COMPETITIONS_FILE, {}) or {}).items():
        for league_id in info.get("api_football_ids", []):
            result[league_id] = (key, info.get("name"), icons.get(key))
    return result

def channel_sort_key(name):
    # "SPORT TV 10" depois de "SPORT TV 2"
    return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', name)]

def is_postponed(programme, postponed):
    # O football-data.org põe os adiados às 00:00, por isso compara-se só o dia e as equipas
    day = datetime.fromisoformat(programme["start"]).date()
    return any(datetime.fromisoformat(f["kickoff"]).date() == day and same_match(programme, f) for f in postponed)

def build_events(programmes, fixtures, postponed, find_competition, by_league, allowed_keys):
    events  = []
    skipped = []
    for p in sorted(programmes, key=lambda p: p["start"]):
        start = datetime.fromisoformat(p["start"])
        stop  = datetime.fromisoformat(p["stop"])
        if stop - start < MIN_DURATION or is_postponed(p, postponed):
            continue

        # Com jogo nas APIs: hora e competição reais. Sem jogo: na DAZN é repetição (ou um
        # jogo que as APIs não cobrem); nos outros canais estima-se a partir do EPG
        fixture = find_fixture(p, fixtures)
        if fixture:
            kickoff = datetime.fromisoformat(fixture["kickoff"])
            key, name, icon = by_league.get(fixture["league_id"]) or find_competition(p["title"], p.get("info", ""))
        elif p["channel"].startswith(VALIDATED_CHANNELS):
            continue
        else:
            kickoff = estimate_kickoff(start)
            key, name, icon = find_competition(p["title"], p.get("info", ""))

        if key not in allowed_keys:
            skipped.append((p, name))
            continue

        # Mesmo jogo já visto: à mesma hora é outro canal do direto; mais tarde é repetição
        # Nomes das equipas: os das APIs quando há jogo; senão os do EPG
        source = fixture or p
        home, away = pretty_team(source["home"]), pretty_team(source["away"])

        event = next((e for e in events if e["competition_key"] == key and same_match(e, p)), None)
        if event:
            if abs(kickoff - event["kickoff"]) <= SAME_AIRING:
                event["channels"].add(p["channel"])
                if fixture:
                    event.update(kickoff=kickoff, home=home, away=away)
            continue

        events.append({
            "kickoff": kickoff,
            "home": home,
            "away": away,
            "competition_key": key,
            "competition": name,
            "competition_icon": icon,
            "channels": {p["channel"]}
        })
    return events, skipped

def to_output(events, now):
    output = []
    for e in sorted(events, key=lambda e: (e["kickoff"], e["home"])):
        kickoff = e["kickoff"]
        output.append({
            "id": len(output),
            "sport": "futebol",
            "kickoff": kickoff.isoformat(),
            "date": f"{WEEKDAYS[kickoff.weekday()]} {kickoff.day} {MONTHS[kickoff.month - 1]}",
            "time": kickoff.strftime("%H:%M"),
            "is_today": kickoff.date() == now.date(),
            "match": f"{e['home']} - {e['away']}",
            "competition": e["competition"],
            "competition_key": e["competition_key"],
            "competition_icon": e["competition_icon"],
            "channels": sorted(e["channels"], key=channel_sort_key)
        })
    return output

if __name__ == "__main__":
    now = now_lisbon()
    epg = read_json(EPG_FILE)
    if not epg:
        print(f"Sem dados em {EPG_FILE}; corre primeiro o scrape_channels.py")
        sys.exit(1)

    # Competições permitidas: as do competitions.json com um id do allowed_competitions.json
    allowed      = load_allowed_leagues()
    allowed_keys = {key for key, ids in league_ids_by_key().items() if allowed is None or ids & allowed}

    # Sem jogos das APIs (ex.: fetch_games.py falhou sem cache) a DAZN fica de fora
    apis   = read_json(FIXTURES_FILE) or {}
    events, skipped = build_events(
        epg["programmes"], apis.get("fixtures", []), apis.get("postponed", []),
        competition_finder(), competitions_by_league(), allowed_keys
    )

    # Ontem, hoje e o próximo dia com jogos (não necessariamente amanhã), até DAYS_AHEAD dias
    today  = now.date()
    future = sorted({e["kickoff"].date() for e in events if today < e["kickoff"].date() <= today + timedelta(days=DAYS_AHEAD)})
    days   = [today - timedelta(days=1), today] + future[:1]
    events = [e for e in events if e["kickoff"].date() in days]

    result = to_output(events, now)
    write_json(OUTPUT_FILE, result)
    print(f"{len(result)} jogos guardados em {OUTPUT_FILE} ({', '.join(d.strftime('%d/%m') for d in days)})")

    # Emissões de futebol cuja competição não foi reconhecida (para acrescentar aliases)
    unknown = sorted({p["title"] for p, name in skipped if name is None and datetime.fromisoformat(p["start"]).date() in days})
    for title in unknown:
        print(f"Competição não reconhecida: {title}")
