"""Bot de veille Vinted : envoie les nouvelles annonces d'une recherche sur Discord.

Usage personnel, faible fréquence. Voir README.md.
"""
import json
import os
import random
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE = Path(__file__).parent
CONFIG_FILE = BASE / "config.json"
SEEN_FILE = BASE / "seen.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen):
    # On garde les 5000 derniers ids pour ne pas grossir indéfiniment
    SEEN_FILE.write_text(json.dumps(sorted(seen)[-5000:]))


def new_session(domain):
    """Ouvre une session : la page d'accueil fournit le cookie nécessaire à l'API."""
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(f"https://{domain}/", timeout=15)
    return s


def build_url(domain, search):
    params = {
        "search_text": search["query"],
