import sys
from datetime import datetime

from common import (
    CHANNELS_FILE, OUTPUT_FILE,
    now_lisbon, read_json, write_json, load_competitions, match_competition
)

def build_games(games, lookup, now):
    output = []
    for game in games:
        competition = game["competition"]
        competition_key, name, competition_icon = match_competition(competition, lookup)

        # O nome vem do competitions.json; sem correspondência fica o do ondebola
        if competition_key:
            competition = name

        kickoff = datetime.fromisoformat(game["kickoff"])

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
            "channels": game["channels"]
        })

    output.sort(key=lambda g: g["kickoff"])
    for idx, game in enumerate(output):
        game["id"] = idx
    return output

if __name__ == "__main__":
    now      = now_lisbon()
    channels = read_json(CHANNELS_FILE)
    if not channels:
        print(f"Sem dados de canais em {CHANNELS_FILE}; corre primeiro o scrape_channels.py")
        sys.exit(1)

    result = build_games(channels["games"], load_competitions(), now)
    write_json(OUTPUT_FILE, result)
    print(f"{len(result)} jogos guardados em {OUTPUT_FILE}")

    unmatched = sorted({g["competition"] for g in result if g["competition"] and not g["competition_key"]})
    for name in unmatched:
        print(f"Competição sem correspondência: {name}")
