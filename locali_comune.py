"""Funzioni condivise dai bot dei tornei locali (solo libreria standard, nessuna installazione)."""
import hashlib, json, os, re, urllib.error, urllib.request

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]
RETENTION_GIORNI = 142         # 4 mesi e 22 giorni
AUTORE_BOT = "github-actions[bot]"
ETICHETTE = (("locali-da-approvare", "fbca04"), ("approvato", "0e8a16"),
             ("rifiutato", "d93f0b"), ("rimosso", "b60205"), ("annuncio-da-approvare", "1d76db"))
LOCALI = "locali.json"
ANNUNCI = "annunci.json"
ANNUNCI_GIORNI = 30            # un annuncio approvato resta online 30 giorni
STATO = "locali_state.json"


def log(*a):
    print(*a, flush=True)


def pulisci(t, n=80):
    """Toglie caratteri di controllo e < > (il sito comunque li neutralizza), accorcia."""
    t = re.sub(r"[\x00-\x1f\x7f<>]", " ", str(t or ""))
    return re.sub(r"\s+", " ", t).strip()[:n]


def data_it(iso):
    y, m, g = iso.split("-")
    return "%d %s %s" % (int(g), MESI[int(m) - 1], y)


def sigla(testo):
    """Impronta non reversibile (il Message-ID è casuale, quindi non si può indovinare): nel repository pubblico
    non finisce nessun dato della mail."""
    return hashlib.sha256(testo.encode("utf-8", "replace")).hexdigest()[:24]


def carica_stato():
    try:
        s = json.load(open(STATO, encoding="utf-8"))
    except Exception:
        s = {}
    s.setdefault("msgs", {})
    s.setdefault("notificati", [])
    return s


def salva_stato(s):
    s["msgs"] = dict(list(s["msgs"].items())[-600:])
    s["notificati"] = s["notificati"][-200:]
    with open(STATO, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
        f.write("\n")


def carica_locali(path=LOCALI):
    """Se locali.json non esiste parte vuoto; se esiste ma è rovinato ci si FERMA senza toccarlo."""
    if not os.path.exists(path):
        return {"locali": []}
    try:
        d = json.load(open(path, encoding="utf-8"))
        if not isinstance(d, dict) or not isinstance(d.get("locali"), list):
            raise ValueError("manca la lista \"locali\"")
        return d
    except Exception as ex:
        raise RuntimeError("locali.json non è valido (%s): non lo modifico. Correggilo o ripristinalo e riprova." % ex)


def salva_locali(d, path=LOCALI):
    ordina(d)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def _chiama(url, method, data, token):
    req = urllib.request.Request(
        url, method=method, data=(json.dumps(data).encode("utf-8") if data is not None else None),
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "rakings-locali-bot",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def carica_annunci(path=ANNUNCI):
    """Come carica_locali: se il file è rovinato ci si ferma senza toccarlo."""
    if not os.path.exists(path):
        return {"annunci": []}
    try:
        d = json.load(open(path, encoding="utf-8"))
        if not isinstance(d, dict) or not isinstance(d.get("annunci"), list):
            raise ValueError("manca la lista \"annunci\"")
        return d
    except Exception as ex:
        raise RuntimeError("annunci.json non è valido (%s): non lo modifico. Correggilo o ripristinalo e riprova." % ex)


def salva_annunci(d, path=ANNUNCI):
    d["annunci"].sort(key=lambda v: v.get("pub", ""), reverse=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def gh(method, path, data=None):
    """Repository in cui gira il workflow (con il permesso automatico GITHUB_TOKEN: nessun token da creare)."""
    return _chiama("https://api.github.com/repos/%s%s" % (os.environ["GITHUB_REPOSITORY"], path),
                   method, data, os.environ["GITHUB_TOKEN"])


def ordina(d):
    d["locali"].sort(key=lambda v: (v.get("iso", ""), v.get("id", 0)), reverse=True)


RE_FORMA = re.compile(r"^(Alola|Alolan|Galar|Galarian|Hisui|Hisuian|Paldea|Paldean|Eternal|Therian|Incarnate|Wash|Heat|Frost|Fan|Mow|Origin|Altered|Sky|Land|Rapid[ -]Strike|Single[ -]Strike|Dusk|Dawn|Midday|Midnight|Ice|Shadow|Hearthflame|Wellspring|Cornerstone|Teal|Terastal|Stellar|Bloodmoon|Zero|Hero|Blade|Shield|Crowned|Hangry|Full Belly|Male|Female|Combat|Blaze|Aqua|Low Key|Amped|Complete|Black|White|Resolute|Ordinary|Primal|Mega|Mega X|Mega Y)$", re.I)
RE_SHOWDOWN = re.compile(r"(^|\n)\s*(Ability:|-\s)|\s@\s|\bNature\b", re.I)


def parse_team(testo):
    """Stessa logica di parseTeam() del sito: o 6 nomi, oppure l'Open Team Sheet in formato Showdown."""
    tx = (testo or "").replace("\r", "").strip()
    if not tx:
        return []
    if not RE_SHOWDOWN.search(tx):
        nomi = [n.strip() for n in re.split(r"[\n,;]+", tx) if n.strip()][:8]
        return [{"n": pulisci(n, 50), "i": "", "a": "", "nt": "", "m": [], "x": 1} for n in nomi if pulisci(n, 50)]
    out = []
    for b in re.split(r"\n\s*\n", tx):
        L = [l.strip() for l in b.split("\n") if l.strip()]
        if not L:
            continue
        h, it, nm = L[0], "", L[0]
        k = h.find(" @ ")
        if k > -1:
            nm, it = h[:k], h[k + 3:]
        nm = re.sub(r"\s*\((M|F)\)\s*$", "", nm)
        pm = re.search(r"\(([^)]+)\)\s*$", nm)
        if pm and not RE_FORMA.match(pm.group(1).strip()):   # "Floette (Eternal)" è una forma, "Rilla (Rillaboom)" un soprannome
            nm = pm.group(1)
        a = nt = ""
        mv = []
        for l in L[1:]:
            m = re.match(r"^Ability:\s*(.+)$", l, re.I)
            if m:
                a = m.group(1)
                continue
            m = re.match(r"^(\w+) Nature$", l, re.I)
            if m:
                nt = m.group(1)
                continue
            if l.startswith("-"):
                mv.append(re.sub(r"^-\s*", "", l))
        nm = pulisci(nm, 50)
        if nm:
            out.append({"n": nm, "i": pulisci(it, 40), "a": pulisci(a, 40), "nt": pulisci(nt, 20),
                        "m": [pulisci(x, 40) for x in mv[:4] if pulisci(x, 40)]})
    return out[:8]
