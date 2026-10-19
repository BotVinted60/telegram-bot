# Bot Vinted → Telegram

Surveille Vinted (Nike Tech, running…) et t'envoie les nouvelles annonces
sous ton prix max, dans tes tailles, sur Telegram.

## 1. Créer le bot Telegram (2 min)

1. Sur Telegram, ouvre **@BotFather** → `/newbot` → choisis un nom.
2. Il te donne un **token** (`123456:ABC...`). Garde-le.
3. Envoie un message à ton nouveau bot (n'importe quoi).
4. Ouvre `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans ton navigateur
   et repère `"chat":{"id":123456789,...}` → c'est ton **chat id**.

## 2. Régler tes recherches

Édite `config.json` :

- `query` : mots-clés Vinted
- `max_price` : prix max en €
- `sizes` : tailles voulues (`"M"`, `"L"`, `"42"`, `"42.5"`…)
- `exclude` : mots à éviter dans le titre/description

Les valeurs fournies sont des exemples : mets tes vraies tailles et tes prix.

## 3a. Hébergement gratuit : GitHub Actions

1. Crée un dépôt GitHub **public** (minutes illimitées ; en privé tu n'as que
   2000 min/mois, donc ce serait trop juste toutes les 5 min).
2. Mets-y tous ces fichiers (garde le dossier `.github/workflows/`).
3. Dépôt → Settings → Secrets and variables → Actions → ajoute
   `TELEGRAM_TOKEN` et `TELEGRAM_CHAT_ID`.
4. Onglet Actions → "Bot Vinted" → Run workflow pour tester.

Le token reste secret même si le dépôt est public. Seul `config.json`
(tes recherches) est visible.

## 3b. Sur ton PC

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python bot.py --loop
```

Sans token, le bot affiche simplement les annonces dans le terminal (mode test).

## À savoir

- Vinted n'a pas d'API officielle : le bot utilise l'API du site, qui peut changer.
- Vinted peut bloquer les IP de serveurs (dont GitHub). Si tu ne reçois rien
  et que les logs montrent des erreurs 403, lance-le depuis ton PC (3b).
- À la première exécution d'une recherche, seules les 5 annonces les plus
  récentes valides sont envoyées, pour ne pas te noyer.
