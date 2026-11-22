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
    SEEN_FILE.write_text(json.dumps(sorted(seen)[-5000:]))


def new_session(domain):
    """Ouvre une session : la page d'accueil fournit le cookie nécessaire à l'API."""
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(f"https://{domain}/", timeout=15)
    print(f"[diag] accueil statut={r.status_code} cookies={list(s.cookies.keys())}")
    return s


def build_url(domain, search):
    params = {
        "search_text": search["query"],
        "order": "newest_first",
        "per_page": search.get("per_page", 20),
    }
    if "price_max" in search:
        params["price_to"] = search["price_max"]
    if "price_min" in search:
        params["price_from"] = search["price_min"]
    query = urlencode(params)
    for key, api_key in (
        ("brand_ids", "brand_ids[]"),
        ("size_ids", "size_ids[]"),
        ("catalog_ids", "catalog_ids[]"),
        ("status_ids", "status_ids[]"),
    ):
        for v in search.get(key, []):
            query += "&" + urlencode({api_key: v})
    return f"https://{domain}/api/v2/catalog/items?{query}"


def fetch_items(session, domain, search):
    r = session.get(build_url(domain, search), timeout=15)
    if r.status_code in (401, 403):
        session.get(f"https://{domain}/", timeout=15)
        r = session.get(build_url(domain, search), timeout=15)
    print(
        f"[diag] api statut={r.status_code} "
        f"type={r.headers.get('content-type')} debut={r.text[:150]!r}"
    )
    r.raise_for_status()
    return r.json().get("items", [])


def price_of(item):
    p = item.get("price")
    if isinstance(p, dict):
        return f"{p.get('amount')} {p.get('currency_code', '€')}"
    return f"{p} {item.get('currency', '€')}"


def send_discord(webhook, domain, item, label):
    url = item.get("url") or f"https://{domain}/items/{item['id']}"
    embed = {
        "title": item.get("title", "Annonce"),
        "url": url,
        "description": f"**{price_of(item)}**",
        "color": 0x09B1BA,
        "fields": [],
        "footer": {"text": f"Recherche : {label}"},
    }
    if item.get("brand_title"):
        embed["fields"].append({"name": "Marque", "value": item["brand_title"], "inline": True})
    if item.get("size_title"):
        embed["fields"].append({"name": "Taille", "value": item["size_title"], "inline": True})
    if item.get("status"):
        embed["fields"].append({"name": "État", "value": str(item["status"]), "inline": True})
    photo = (item.get("photo") or {}).get("url")
    if photo:
        embed["thumbnail"] = {"url": photo}
    requests.post(webhook, json={"embeds": [embed]}, timeout=15).raise_for_status()


def main():
    cfg = load_config()
    domain = cfg.get("domain", "www.vinted.fr")
    webhook = os.environ.get("DISCORD_WEBHOOK") or cfg["discord_webhook"]
    once = bool(os.environ.get("RUN_ONCE"))
    interval = max(int(cfg.get("interval_seconds", 90)), 60)

    seen = load_seen()
    first_run = not seen
    session = new_session(domain)
    print(f"Bot démarré : {len(cfg['searches'])} recherche(s), intervalle ~{interval}s.")

    while True:
        for search in cfg["searches"]:
            label = search["query"]
            try:
                items = fetch_items(session, domain, search)
            except Exception as e:
                print(f"[{label}] erreur : {e}")
                time.sleep(5 if once else 30)
                continue

            fresh = [i for i in items if i["id"] not in seen]
            for item in reversed(fresh):
                seen.add(item["id"])
                if first_run:
                    continue
                try:
                    send_discord(webhook, domain, item, label)
                except Exception as e:
                    print(f"[{label}] envoi Discord échoué : {e}")
                time.sleep(1)
            if fresh:
                print(f"[{label}] {len(fresh)} nouvelle(s) annonce(s)")
            time.sleep(random.uniform(3, 8))

        if first_run:
            first_run = False
            print("Fin du premier passage.")
        save_seen(seen)
        if once:
            break
        time.sleep(interval + random.uniform(0, 20))


if __name__ == "__main__":
    main()
