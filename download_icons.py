import sys
import requests
from pathlib import Path

from common import COMPETITIONS_FILE, read_json

ICONS_DIR = Path("assets/icons/competicoes")

# CDN público de imagens (não precisa de chave): usa o primeiro id de "api_football_ids"
MEDIA_URL = "https://media.api-sports.io/football/leagues/{id}.png"

def icon_url(info):
    # "icon_url" manual tem prioridade; senão deduz-se do id da liga
    if info.get("icon_url"):
        return info["icon_url"]
    ids = info.get("api_football_ids") or []
    return MEDIA_URL.format(id=ids[0]) if ids else None

def download(url, path):
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.raise_for_status()
    if not response.headers.get("content-type", "").startswith("image/"):
        raise ValueError(f"resposta não é uma imagem ({response.headers.get('content-type')})")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)

if __name__ == "__main__":
    competitions = read_json(COMPETITIONS_FILE, {})
    failed = 0

    for key, info in competitions.items():
        path = Path(info.get("icon") or ICONS_DIR / f"{key}.png")
        if path.exists():
            continue

        url = icon_url(info)
        if not url:
            print(f"'{key}': sem icon_url nem api_football_ids; ícone não descarregado")
            failed += 1
            continue

        try:
            download(url, path)
            print(f"'{key}': {path} descarregado")
        except Exception as e:
            print(f"'{key}': erro ao descarregar {url}: {e}")
            failed += 1

    sys.exit(1 if failed else 0)
