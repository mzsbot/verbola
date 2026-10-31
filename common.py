import json
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

LISBON            = ZoneInfo('Europe/Lisbon')
COMPETITIONS_FILE = "./data/competitions.json"
CHANNELS_FILE     = "./data/raw/ondebola.json"
OUTPUT_FILE       = "./data/jogos.json"

def now_lisbon():
    return datetime.now(LISBON)

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
