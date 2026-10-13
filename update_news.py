#!/usr/bin/env python3
"""Legge da Limitless VGC i risultati dei grandi tornei e prepara news.json:
report con le squadre, Best Player (top 16 dei Regionali) e italiani in evidenza.
Solo libreria standard. Prima esecuzione parziale: a ogni giro scarica fino a NEWS_BUDGET pagine
e ricorda quelle già lette in news_cache.json. Per spegnerlo: variabile NEWS_BOT diversa da 1."""
import json, os, re, time, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

BASE = "https://limitlessvgc.com"
UA = "tornei-vgc-bot (sito della community, con link alle fonti)"
OUT, CACHE = "news.json", "news_cache.json"
BUDGET = int(os.environ.get("NEWS_BUDGET", "120"))
used = 0
TOPN = {"Regionale": 8, "Special Event": 8, "Internazionale": 32, "Mondiale": 64}
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
TIPI = {"normal": "Normale", "fire": "Fuoco", "water": "Acqua", "electric": "Elettro", "grass": "Erba", "ice": "Ghiaccio", "fighting": "Lotta", "poison": "Veleno", "ground": "Terra", "flying": "Volante", "psychic": "Psico", "bug": "Coleottero", "rock": "Roccia", "ghost": "Spettro", "dragon": "Drago", "dark": "Buio", "steel": "Acciaio", "fairy": "Folletto"}
SPECIAL = {"kommo-o": "Kommo-o", "hakamo-o": "Hakamo-o", "jangmo-o": "Jangmo-o", "porygon-z": "Porygon-Z", "ho-oh": "Ho-Oh", "mr-mime": "Mr. Mime", "mime-jr": "Mime Jr.", "type-null": "Type: Null", "great-tusk": "Great Tusk", "iron-hands": "Iron Hands", "flutter-mane": "Flutter Mane", "raging-bolt": "Raging Bolt", "iron-bundle": "Iron Bundle", "walking-wake": "Walking Wake"}

class Budget(Exception):
    pass

def get(url):
    global used
    if used >= BUDGET:
        raise Budget()
    used += 1
    time.sleep(0.7)  # poche richieste, con calma
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def disp(slug):
    if slug in SPECIAL:
        return SPECIAL[slug]
    p = slug.split("-")
    if len(p) == 1:
        return p[0].capitalize()
    if p[-1] in ("f", "m") and len(p) == 2:
        return p[0].capitalize() + "-" + p[1].upper()
    return p[0].capitalize() + " (" + " ".join(x.capitalize() for x in p[1:]) + ")"

class Rows(HTMLParser):
    """Righe di tabella con testi delle celle, link (href, testo) e bandiere."""
    def __init__(s):
        super().__init__()
        s.rows, s.row, s.cell, s.link = [], None, None, False
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag == "tr":
            s.row = {"cells": [], "links": [], "flags": []}
        elif s.row is not None:
            if tag in ("td", "th"):
                s.cell = []
            elif tag == "a":
                s.row["links"].append([a.get("href") or "", ""]); s.link = True
            elif tag == "img" and "/flags/" in (a.get("src") or ""):
                s.row["flags"].append(a["src"].rsplit("/", 1)[-1].split(".")[0])
    def handle_endtag(s, tag):
        if tag in ("td", "th") and s.row is not None and s.cell is not None:
            s.row["cells"].append(" ".join(s.cell)); s.cell = None
        elif tag == "a":
            s.link = False
        elif tag == "tr" and s.row is not None:
            s.rows.append(s.row); s.row = None
    def handle_data(s, d):
        d = d.strip()
        if not d or s.row is None:
            return
        if s.cell is not None:
            s.cell.append(d)
        if s.link and s.row["links"]:
            s.row["links"][-1][1] += d

class Tok(HTMLParser):
    """Sequenza di testi, con un segnale ogni volta che compare il link a un Pokémon."""
    def __init__(s):
        super().__init__()
        s.t, s.skip = [], False
    def handle_starttag(s, tag, a):
        if tag == "a":
            m = re.search(r"/pokemon/([a-z0-9-]+)", dict(a).get("href") or "")
            if m:
                s.t.append(("p", m.group(1))); s.skip = True
    def handle_endtag(s, tag):
        if tag == "a":
            s.skip = False
    def handle_data(s, d):
        d = d.strip()
        if d and not s.skip:
            s.t.append(("t", d))

def classify(name):
    if re.match(r"Regional\b", name): return "Regionale"
    if re.match(r"Special Event\b", name): return "Special Event"
    if re.match(r"World Championships\b", name): return "Mondiale"
    if re.search(r"\b(NAIC|EUIC|LAIC|OCIC)\b", name): return "Internazionale"
    return None

def parse_list(page):
    p = Rows(); p.feed(page); out = []
    for r in p.rows:
        t = next((l for l in r["links"] if re.search(r"/tournaments/(\d+)$", l[0])), None)
        w = next((l for l in r["links"] if "/players/" in l[0]), None)
        d = re.search(r"(\d{2}) ([A-Za-z]{3}) (\d{2})", r["cells"][0] if r["cells"] else "")
        if not (t and d):
            continue
        typ = classify(t[1])
        if not typ:
            continue
        pl = next((c for c in r["cells"][1:] if re.fullmatch(r"\d+", c.strip())), "0")
        out.append({"id": int(re.search(r"/tournaments/(\d+)$", t[0]).group(1)), "name": t[1], "type": typ,
                    "date": "20%s-%02d-%s" % (d[3], MON.get(d[2].lower(), 1), d[1]), "players": int(pl),
                    "winner": w[1] if w else "", "wcc": r["flags"][-1] if len(r["flags"]) > 1 else ""})
    return out

def parse_results(page):
    p = Rows(); p.feed(page); rows = []
    for r in p.rows:
        pl = next((l for l in r["links"] if "/players/" in l[0]), None)
        if not (pl and r["cells"] and re.fullmatch(r"\d+", r["cells"][0].strip())):
            continue
        tid = next((re.search(r"/teams/(\d+)", l[0]).group(1) for l in r["links"] if re.search(r"/teams/(\d+)", l[0])), "")
        slugs = [m.group(1) for l in r["links"] for m in [re.search(r"/pokemon/([a-z0-9-]+)", l[0])] if m]
        rows.append({"p": int(r["cells"][0]), "pl": pl[1], "cc": r["flags"][0] if r["flags"] else "", "slugs": slugs, "tid": tid})
    reg = re.search(r"Regulation Set ([A-Z]-[A-Z])", re.sub(r"<[^>]+>", " ", page))
    return {"rows": rows, "reg": reg.group(1) if reg else ""}

def parse_team(page):
    p = Tok(); p.feed(page); blocks = []
    for kind, x in p.t:
        if kind == "p":
            blocks.append([x, []])
        elif blocks:
            blocks[-1][1].append(x)
    team = []
    for slug, texts in blocks:
        if not texts:
            continue  # icone senza dettagli
        item, ab, nt, mv = "", "", "", []
        for x in texts:
            m = re.match(r"Ability:\s*(.+)", x, re.I); n = re.fullmatch(r"(\w+) Nature", x)
            if m: ab = m.group(1)
            elif n: nt = n.group(1)
            elif re.match(r"(Level|EVs|IVs|Tera)", x): continue
            elif not ab and not item: item = x
            elif ab: mv.append(x)
        team.append({"n": disp(slug), "i": item, "a": ab, "nt": nt, "m": mv[:4], "_s": slug})
    return team if len(team) == 6 and all(t["a"] for t in team) else []

def parse_stats(page):
    p = Rows(); p.feed(page); out = []
    for r in p.rows:
        sl = next((m.group(1) for l in r["links"] for m in [re.search(r"/pokemon/([a-z0-9-]+)", l[0])] if m), None)
        sh = next((re.search(r"(\d+(?:\.\d+)?)\s*%", c) for c in r["cells"] if re.search(r"(\d+(?:\.\d+)?)\s*%", c)), None)
        if sl and sh:
            out.append([disp(sl), float(sh.group(1)), sl])
    return out[:10]

def tipi(slug):
    p = slug.split("-"); cand = [slug]
    if p[-1] == "f": cand.insert(0, "-".join(p[:-1] + ["female"]))
    cand.append(p[0])
    for c in cand:
        try:
            d = json.loads(get("https://pokeapi.co/api/v2/pokemon/" + c))
            return [TIPI.get(t["type"]["name"], t["type"]["name"]) for t in d["types"]]
        except Budget:
            raise
        except Exception:
            continue
    return []

def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d

def dateit(d):
    y, m, g = d.split("-"); return "%d %s %s" % (int(g), MESI[int(m) - 1], y)

def main():
    if os.environ.get("NEWS_BOT", "1") != "1":
        print("News disattivate"); return
    c = load(CACHE, {}); c.setdefault("res", {}); c.setdefault("teams", {}); c.setdefault("stats", {}); c.setdefault("types", {})
    lst = []
    try:
        lst = sorted(parse_list(get(BASE + "/tournaments")), key=lambda t: t["date"], reverse=True)
        print("Tornei trovati:", len(lst))
        for t in lst:  # risultati
            if str(t["id"]) not in c["res"]:
                c["res"][str(t["id"])] = parse_results(get("%s/tournaments/%d" % (BASE, t["id"])))
        for t in lst:  # squadre
            for r in c["res"].get(str(t["id"]), {"rows": []})["rows"][:TOPN[t["type"]]]:
                if r["tid"] and r["tid"] not in c["teams"]:
                    c["teams"][r["tid"]] = parse_team(get("%s/teams/%s" % (BASE, r["tid"])))
        for t in lst[:12]:  # statistiche
            if str(t["id"]) not in c["stats"]:
                c["stats"][str(t["id"])] = parse_stats(get("%s/tournaments/%d/statistics" % (BASE, t["id"])))
        for t in lst:  # tipi dei Pokémon
            sl = [s for r in c["res"].get(str(t["id"]), {"rows": []})["rows"][:TOPN[t["type"]]] for s in r["slugs"]]
            sl += [x[2] for x in c["stats"].get(str(t["id"]), [])]
            for s in sl:
                if disp(s) not in c["types"]:
                    c["types"][disp(s)] = tipi(s)
    except Budget:
        print("Limite di pagine raggiunto: si riprende al prossimo giro")
    except Exception as ex:
        print("Errore:", ex)
    news, bp, ita = [], [], []
    for t in lst:
        res = c["res"].get(str(t["id"]))
        if not res or not res["rows"]:
            continue
        top = TOPN[t["type"]]; rows = []
        for r in res["rows"][:top]:
            tm = c["teams"].get(r["tid"]) or [{"n": disp(s), "i": "", "a": "", "nt": "", "m": []} for s in r["slugs"]]
            rows.append({"pl": r["pl"], "cc": r["cc"], "team": [{k: v for k, v in x.items() if k != "_s"} for x in tm]})
        d = dateit(t["date"]) + " · %d giocatori" % t["players"] + (" · Regolamento " + res["reg"] if res["reg"] else "")
        e = {"t": t["type"], "n": t["name"], "d": d, "top": top, "real": True, "src": "%s/tournaments/%d" % (BASE, t["id"]), "rows": rows}
        if c["stats"].get(str(t["id"])):
            e["stats"] = [[x[0], x[1]] for x in c["stats"][str(t["id"])]]
        news.append(e)
        for r in res["rows"]:
            if t["type"] == "Regionale" and r["p"] <= 16:
                bp.append([r["pl"], r["cc"], re.sub(r"^Regional\s+", "", t["name"]), t["id"], r["p"]])
            if r["cc"] == "IT" and r["p"] <= 8:
                ita.append({"pl": r["pl"], "t": t["name"], "p": r["p"], "d": dateit(t["date"]), "n": t["players"], "id": t["id"]})
    for t in lst:  # vincitori italiani anche se la pagina non è ancora stata letta
        if t["wcc"] == "IT" and not any(x["id"] == t["id"] and x["p"] == 1 for x in ita):
            ita.append({"pl": t["winner"], "t": t["name"], "p": 1, "d": dateit(t["date"]), "n": t["players"], "id": t["id"]})
    json.dump(c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    if not news:
        print("Nessuna news: file non aggiornato"); return
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "news": news, "bp": bp, "ita": ita, "types": c["types"]}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("News: %d tornei, %d risultati Best Player, %d italiani, %d pagine lette" % (len(news), len(bp), len(ita), used))

main()
