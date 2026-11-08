import json
import os
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

LISBON               = ZoneInfo('Europe/Lisbon')
COMPETITIONS_FILE    = "./data/competitions.json"
ALLOWED_FILE         = "./data/allowed_competitions.json"
SEARCH_CHANNELS_FILE = "./data/search_channels.json"
EPG_FILE             = "./data/raw/epg.json"
FIXTURES_FILE        = "./data/raw/api_football.json"
OUTPUT_FILE          = "./data/jogos.json"

# O site mostra ontem, hoje e o próximo dia com jogos (que pode não ser amanhã);
# este último procura-se até DAYS_AHEAD dias depois de hoje (EPG e football-data.org)
DAYS_AHEAD = 7

def now_lisbon():
    return datetime.now(LISBON)

def load_env(path=".env"):
    # Lê variáveis de um .env local (ex.: API_FOOTBALL_KEY); no GitHub vêm dos secrets
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def write_json(path, data):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fold(text):
    # Minúsculas, sem acentos e sem espaços repetidos: "UEFA Liga  Campeões" -> "uefa liga campeoes"
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.lower().split())

def load_allowed_leagues():
    # Ids das ligas da API-Football a extrair; sem ficheiro (ou vazio) não há filtro
    allowed = read_json(ALLOWED_FILE) or []
    return {c["id"] for c in allowed} or None

def is_allowed(fixture, allowed):
    return allowed is None or fixture["league_id"] in allowed

def load_competitions():
    # Devolve {alias normalizado: (chave, nome, ícone)} a partir do competitions.json
    competitions = read_json(COMPETITIONS_FILE, {})

    lookup = {}
    for key, info in competitions.items():
        # Sem "icon" definido, usa o caminho por omissão (onde o download_icons.py guarda)
        icon = info.get("icon") or f"assets/icons/competicoes/{key}.png"
        if not Path(icon).exists():
            print(f"Ícone em falta para '{key}': {icon}")
            icon = None
        for alias in info.get("aliases", []):
            lookup[fold(alias)] = (key, info.get("name"), icon)
    return lookup

def match_competition(competition, lookup):
    # Ignora a jornada no fim ("Liga Portugal, J10" -> "Liga Portugal") antes de comparar
    base = re.sub(r',\s*J\d+$', '', competition.strip())
    return lookup.get(fold(base), (None, None, None))
