#!/usr/bin/env python3
"""Controllo quotidiano della salute del sito. Se qualcosa non va il flusso finisce con errore e GitHub manda
in automatico una mail ad Andrea con l'elenco dei problemi (nessun avviso quando e' tutto a posto).

Controlla: flussi di GitHub il cui ULTIMO giro e' fallito, Worker su Cloudflare, sito online, aggiornamento dei tornei,
copia di sicurezza degli iscritti (se attivata)."""
import json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "rakings/VGCrAKings")
UA = "rakings-controllo"
ora = datetime.now(timezone.utc)

def get(url, token=None, timeout=30):
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.status, r.read()

def ore_da(iso):
    return (ora - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 3600

problemi, ok = [], []
tok = os.environ.get("GITHUB_TOKEN", "")

# 1) flussi: per ogni flusso attivo si guarda solo il suo giro concluso piu' recente (ultimi 8 giorni).
#    Se dopo un errore e' andato bene, il problema e' gia' risolto e non si segnala.
try:
    _, b = get("https://api.github.com/repos/%s/actions/workflows?per_page=100" % REPO, tok)
    flussi = [f for f in json.loads(b).get("workflows", []) if f.get("state") == "active" and f.get("name") != "Controllo del sito"]
    rotti = 0
    for f in flussi:
        _, b = get("https://api.github.com/repos/%s/actions/workflows/%s/runs?per_page=1&status=completed" % (REPO, f["id"]), tok)
        rr = json.loads(b).get("workflow_runs", [])
        if not rr or ore_da(rr[0]["created_at"]) > 8 * 24:
            continue
        r = rr[0]
        if r.get("conclusion") in ("failure", "timed_out", "startup_failure"):
            rotti += 1
            problemi.append("Flusso «%s»: l'ultimo giro e' fallito (%s UTC) → %s" % (f["name"], r["created_at"][:16].replace("T", " "), r.get("html_url", "")))
    ok.append("Flussi controllati: %d, con l'ultimo giro fallito: %d" % (len(flussi), rotti))
except Exception as e:
    problemi.append("Non riesco a leggere i flussi di GitHub: %s" % e)

# 2) Worker su Cloudflare
w = os.environ.get("SUBS_URL", "").rstrip("/")
if w:
    try:
        s, b = get(w + "/")
        j = json.loads(b)
        if s == 200 and j.get("ok"):
            ok.append("Worker online, versione %s" % j.get("v"))
        else:
            problemi.append("Il Worker risponde in modo strano: %s" % b[:120])
    except Exception as e:
        problemi.append("Il Worker non risponde: %s" % e)

# 3) sito online e tornei aggiornati
s_url = os.environ.get("SITE_URL", "").rstrip("/")
if s_url:
    try:
        s, _ = get(s_url + "/index.html")
        ok.append("Sito online") if s == 200 else problemi.append("Il sito risponde con codice %s" % s)
    except Exception as e:
        problemi.append("Il sito non si apre: %s" % e)
try:
    e = json.load(open("events.json", encoding="utf-8"))
    h = ore_da(e.get("updated", "1970-01-01T00:00:00+00:00"))
    (ok if h < 10 else problemi).append("Tornei aggiornati %.0f ore fa" % h)
except Exception as ex:
    problemi.append("events.json illeggibile: %s" % ex)

# 4) copia degli iscritti (solo se la Release esiste: cioe' se la copia e' stata attivata)
try:
    s, b = get("https://api.github.com/repos/%s/releases/tags/copia-iscritti" % REPO, tok)
    a = [x for x in json.loads(b).get("assets", []) if x.get("name") == "iscritti.enc"]
    if a:
        h = ore_da(a[0]["updated_at"])
        (ok if h < 9 * 24 else problemi).append("Copia degli iscritti fatta %.0f giorni fa" % (h / 24))
except urllib.error.HTTPError as ex:
    ok.append("Copia degli iscritti non ancora attiva") if ex.code == 404 else problemi.append("Copia degli iscritti: errore %s" % ex.code)
except Exception as ex:
    problemi.append("Copia degli iscritti: %s" % ex)

for x in ok:
    print("OK  " + x)
for x in problemi:
    print("::error::" + x)
if problemi:
    print("\n%d problemi: controlla i punti qui sopra." % len(problemi))
    sys.exit(1)
print("\nTutto a posto.")
