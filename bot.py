#!/usr/bin/env python3
"""Bot Vinted -> Telegram.

Surveille Vinted pour les recherches définies dans config.json et envoie
sur Telegram les nouvelles annonces qui respectent prix max, tailles et mots exclus.

Usage :
    python bot.py            # un seul passage (idéal pour GitHub Actions)
    python bot.py --loop     # tourne en continu (idéal sur ton PC)
"""
import html
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests

BASE = "https://www.vinted.fr"
ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
SEEN_PATH = ROOT / "seen.json"

MAX_SEEN_IDS = 3000        # taille max de la mémoire anti-doublons
MAX_ALERTS_PER_RUN = 15    # évite de te spammer
FIRST_RUN_ALERTS = 5       # à la 1re exécution d'une recherche : seulement les N plus récentes

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# ---------- Vinted ----------

def new_session():
    """Ouvre une session et récupère le cookie nécessaire à l'API."""
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(BASE, timeout=20)
    r.raise_for_status()
    return s


def fetch_items(session, query, max_price, per_page=30):
    params = {
        "search_text": query,
        "order": "newest_first",
        "per_page": per_page,
        "page": 1,
    }
    if max_price:
        params["price_to"] = max_price
    url = f"{BASE}/api/v2/catalog/items"
    r = session.get(url, params=params, timeout=20)
    if r.status_code == 401:  # cookie expiré : on en reprend un
        session.get(BASE, timeout=20)
        r = session.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])


# ---------- Filtres ----------

def parse_price(item):
    p = item.get("price")
    if isinstance(p, dict):
        p = p.get("amount")
    try:
        return float(p)
    except (TypeError, ValueError):
        return None


def size_ok(item, sizes):
    """Vrai si la taille de l'annonce correspond à l'une des tailles voulues."""
    if not sizes:
        return True
    title = (item.get("size_title") or "").upper()
    tokens = {t.strip() for t in re.split(r"[/,]", title) if t.strip()}
    wanted = {str(s).upper().strip() for s in sizes}
    return bool(tokens & wanted)


def excluded(item, words):
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    return any(w.lower() in text for w in words or [])


def keep(item, search):
    price = parse_price(item)
    max_price = search.get("max_price")
    if price is None or (max_price and price > max_price):
        return False
    if not size_ok(item, search.get("sizes")):
        return False
    if excluded(item, search.get("exclude")):
        return False
    return True


# ---------- Telegram ----------

def format_message(item, search):
    price = parse_price(item)
    lines = [
        f"<b>{html.escape(search['name'])}</b>",
        html.escape(item.get("title", "")),
        f"💶 {price:.0f} € · 📏 {html.escape(item.get('size_title') or '?')}"
        f" · {html.escape(item.get('status') or '')}",
    ]
    brand = item.get("brand_title")
    if brand:
        lines.append(f"🏷️ {html.escape(brand)}")
    lines.append(item.get("url") or f"{BASE}/items/{item.get('id')}")
    return "\n".join(lines)


def send_telegram(text, photo_url=None):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[dry-run] (pas de TELEGRAM_TOKEN/CHAT_ID)\n" + text + "\n")
        return
    api = f"https://api.telegram.org/bot{token}"
    if photo_url:
        r = requests.post(
            f"{api}/sendPhoto",
            data={"chat_id": chat_id, "photo": photo_url,
                  "caption": text[:1024], "parse_mode": "HTML"},
            timeout=20,
        )
        if r.ok:
            return
    r = requests.post(
        f"{api}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=20,
    )
    if not r.ok:
        print(f"Erreur Telegram {r.status_code}: {r.text}", file=sys.stderr)


# ---------- Mémoire anti-doublons ----------

def load_seen():
    if SEEN_PATH.exists():
        try:
            data = json.loads(SEEN_PATH.read_text())
            return {"ids": list(data.get("ids", [])),
                    "initialized": list(data.get("initialized", []))}
        except json.JSONDecodeError:
            pass
    return {"ids": [], "initialized": []}


def save_seen(seen):
    seen["ids"] = seen["ids"][-MAX_SEEN_IDS:]
    SEEN_PATH.write_text(json.dumps(seen, indent=1))


# ---------- Boucle principale ----------

def run_once(session, config, seen):
    ids = set(seen["ids"])
    alerts = 0
    for search in config["searches"]:
        name = search["name"]
        first_run = name not in seen["initialized"]
        try:
            items = fetch_items(session, search["query"], search.get("max_price"))
        except requests.RequestException as e:
            print(f"[{name}] erreur Vinted : {e}", file=sys.stderr)
            continue

        new = [it for it in items if str(it.get("id")) not in ids]
        matches = [it for it in new if keep(it, search)]
        if first_run:
            matches = matches[:FIRST_RUN_ALERTS]

        for it in matches:
            if alerts >= MAX_ALERTS_PER_RUN:
                break
            photo = (it.get("photo") or {}).get("url")
            send_telegram(format_message(it, search), photo)
            alerts += 1
            time.sleep(1)

        for it in new:
            ids.add(str(it.get("id")))
            seen["ids"].append(str(it.get("id")))
        if first_run:
            seen["initialized"].append(name)
        print(f"[{name}] {len(items)} annonces, {len(new)} nouvelles, {len(matches)} alertes")
        time.sleep(random.uniform(1.5, 3.5))  # reste discret
    return seen


def main():
    config = json.loads(CONFIG_PATH.read_text())
    loop = "--loop" in sys.argv
    interval = config.get("interval_seconds", 120)
    session = new_session()
    seen = load_seen()
    while True:
        seen = run_once(session, config, seen)
        save_seen(seen)
        if not loop:
            break
        time.sleep(interval + random.uniform(0, 20))


if __name__ == "__main__":
    main()
