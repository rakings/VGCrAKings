#!/usr/bin/env python3
"""VGC Stats - raccolta dati dei regionali VGC dalla API di Pokedata (pokedata.ovh/apiv3).

L'autore di Pokedata ha dato il permesso di usare i suoi dati, anche in tempo reale.
Solo libreria standard. UNA richiesta per regionale (classifica + squadre + swiss tutto insieme).

Uso:
  python3 vgc_stats.py --list                    elenco di tutti i regionali (1 richiesta)
  python3 vgc_stats.py --id 1000076              PROVA su un regionale: non salva nulla
  python3 vgc_stats.py --id 1000076 --write      salva in vgcstats/1000076/
  python3 vgc_stats.py --auto --write            raccoglie i regionali IN CORSO e quelli finiti non ancora raccolti
Senza --write e' sempre una prova: stampa un riepilogo e non salva niente.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

UA = "tornei-vgc-bot (sito della community, con link alle fonti)"
API = "https://www.pokedata.ovh/apiv3"
OUT = "vgcstats"
TOP = 256            # squadre complete (strumenti, mosse, nature) per i primi 256
DELAY = 2.0          # secondi tra una richiesta e l'altra
# Regolamento in base alla data di inizio del regionale (DA VERIFICARE: aggiorna le date se serve).
# Quando esce un nuovo regolamento (es. M-D) basta aggiungere una riga in cima.
REG_WINDOWS = [("M-C", "2026-09-01"), ("M-B", "2026-07-01"), ("M-A", "2026-05-25")]
RESULT = {3: "W", 0: "L", 1: "T"}
KNOWN = {"id", "subid", "name", "ability", "item", "badges", "stat alignment", "teratype"}
FORMS = {"Male": "-M", "Female": "-F", "Alolan Form": "-Alola", "Hisuian Form": "-Hisui",
         "Galarian Form": "-Galar", "Paldean Form": "-Paldea", "Paldean Form - Blaze Breed": "-Paldea-Fire",
         "Paldean Form - Aqua Breed": "-Paldea-Water", "Bloodmoon": "-Bloodmoon", "Family of Four": "-Four",
         "Family of Three": "", "Curly Form": "", "Droopy Form": "-Droopy", "Stretchy Form": "-Stretchy",
         "Unremarkable Form": "", "Masterpiece Form": "-Masterpiece"}


class Stop(Exception):
    """Pokedata ci ha chiesto di fermarci: ci fermiamo subito."""


class Budget(Exception):
    pass


used = 0
budget = 3


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def get_json(url):
    """Scarica e legge il JSON (Pokedata a volte mette un avviso PHP prima del JSON: lo ignoriamo)."""
    global used
    if used >= budget:
        raise Budget()
    used += 1
    time.sleep(DELAY)
    try:
        text = fetch_text(url)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) or e.code >= 500:
            raise Stop("Pokedata ha risposto %s per %s" % (e.code, url))
        raise
    i = text.find("{")
    if i < 0:
        raise Stop("risposta inattesa da Pokedata per %s" % url)
    return json.loads(text[i:])


# ---------- nomi e regolamento ----------

unknown_forms = set()


def showdown_name(raw):
    """'Basculegion [Male]' -> 'Basculegion-M', 'Ninetales [Alolan Form]' -> 'Ninetales-Alola'."""
    m = re.match(r"^(.*?)\s*\[(.+)\]$", raw.strip())
    if not m:
        return raw.strip()
    base, form = m.group(1), m.group(2)
    if form in FORMS:
        return base + FORMS[form]
    unknown_forms.add(raw)
    return base + "-" + form.split()[0]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def reg_of(start):
    for reg, since in REG_WINDOWS:
        if start and start >= since:
            return reg
    return "old"


def person(raw):
    """'Louis Fontvieille [FR]' -> {'name': 'Louis Fontvieille', 'cc': 'FR'}"""
    if not raw:
        return None
    m = re.match(r"^(.*?)\s*\[([A-Za-z]{2,3})\]$", raw.strip())
    return {"name": m.group(1), "cc": m.group(2).upper()} if m else {"name": raw.strip(), "cc": ""}


def city_of(name):
    m = re.match(r"^(?:\d{4} )?(?:(.+?) )?Pok.mon VGC (.*)$", name)
    if not m:
        return name, ""
    return (m.group(1) or m.group(2)), m.group(2)


# ---------- elaborazione di un regionale ----------

def process(data):
    """Dal JSON di Pokedata a giocatori, squadre e swiss."""
    info = data["tournament"]
    block = next((b for b in data["tournament_data"] if b.get("division") == "masters"), None)
    if not block:
        raise ValueError("divisione masters non trovata")
    raw = block["data"]
    swiss_total = (info.get("roundNumbers") or {}).get("masters") or 0
    plain = {}
    pid_of = {}
    for i, p in enumerate(raw):
        pid_of[i] = i + 1
    # tavoli: (round, tavolo) -> giocatori (risolve anche gli omonimi)
    tables = {}
    for i, p in enumerate(raw):
        for r, e in (p.get("rounds") or {}).items():
            if e.get("table") is not None:
                tables.setdefault((int(r), e["table"]), []).append(i)
    per_round = Counter()
    for p in raw:
        for r in (p.get("rounds") or {}):
            per_round[int(r)] += 1
    # fase 2 = dove il numero di giocatori crolla (il taglio dopo il primo giorno)
    day1, best = 0, 0.0
    for r in sorted(per_round):
        nxt = per_round.get(r + 1)
        if nxt and per_round[r] > 0:
            drop = 1.0 - nxt / per_round[r]
            if drop > best:
                best, day1 = drop, r
    if best < 0.4:
        day1 = 0
    players, swiss, teams = [], {}, {}
    for i, p in enumerate(raw):
        pid = i + 1
        m = re.match(r"^(.*?)\s*\[([A-Za-z]{2,3})\]$", p["name"])
        name, cc = (m.group(1), m.group(2).upper()) if m else (p["name"], "")
        rec = p.get("record") or {}
        rounds = p.get("rounds") or {}
        played = sorted(int(r) for r in rounds)
        entry = []
        for r in range(1, max(played or [0]) + 1):
            e = rounds.get(str(r))
            if not e:
                entry.append(None)
                continue
            if e.get("table") is None:
                entry.append("0B")
                continue
            others = [x for x in tables.get((r, e["table"]), []) if x != i]
            code = RESULT.get(e.get("result"), "?")
            entry.append("%d%s" % (others[0] + 1, code) if len(others) == 1 else "-1%s" % code)
        swiss[pid] = entry
        mons = []
        for t in p.get("teamlist") or []:
            nm = showdown_name(t.get("name", ""))
            extra = {k: v for k, v in t.items() if k not in KNOWN and v not in (None, "")}
            if t.get("teratype"):
                extra["Tera Type"] = t["teratype"]
            mons.append({"slug": slug(nm), "name": nm, "item": t.get("item") or "", "ability": t.get("ability") or "",
                         "nature": t.get("stat alignment") or "", "moves": [x for x in (t.get("badges") or []) if x],
                         "extra": extra})
        placing = p.get("placing") or pid
        players.append({"tp_id": pid, "name": name, "country": cc, "placement": placing, "wins": rec.get("wins", 0),
                        "losses": rec.get("losses", 0), "ties": rec.get("ties", 0),
                        "day2": 1 if day1 and played and max(played) > day1 else 0,
                        "topcut": 1 if swiss_total and played and max(played) > swiss_total else 0,
                        "team": ",".join(m_["slug"] for m_ in mons), "trainer": p.get("Trainer name")})
        if mons and placing <= TOP:
            teams[str(pid)] = mons
    return info, players, teams, swiss, day1, swiss_total


# ---------- statistiche ----------

def top_pairs(counter, n=None):
    return [[k, v] for k, v in counter.most_common(n)]


def compute(players, teams, names):
    rows = {}
    for p in players:
        slugs = {s for s in (p.get("team") or "").split(",") if s}
        for s in slugs:
            r = rows.setdefault(s, {"count": 0, "wins": 0, "losses": 0, "top256": 0, "day2": 0, "cut": 0, "partners": Counter()})
            r["count"] += 1
            r["wins"] += p["wins"]
            r["losses"] += p["losses"]
            r["top256"] += 1 if p["placement"] <= TOP else 0
            r["day2"] += 1 if p.get("day2") else 0
            r["cut"] += 1 if p.get("topcut") else 0
            for o in slugs:
                if o != s:
                    r["partners"][o] += 1
    det = {}
    for tp, team in teams.items():
        for mon in team:
            d = det.setdefault(mon["slug"], {"sample": 0, "nature": Counter(), "item": Counter(), "ability": Counter(),
                                              "moves": Counter(), "extra": {}, "players": []})
            d["sample"] += 1
            d["players"].append(int(tp))
            for key in ("nature", "item", "ability"):
                if mon[key]:
                    d[key][mon[key]] += 1
            for mv in mon["moves"]:
                d["moves"][mv] += 1
            for label, val in mon["extra"].items():
                d["extra"].setdefault(label, Counter())[str(val)] += 1
    out = []
    for s, r in sorted(rows.items(), key=lambda kv: -kv[1]["count"]):
        d = det.get(s)
        item = {"slug": s, "name": names.get(s) or s.replace("-", " ").title(), "count": r["count"], "wins": r["wins"],
                "losses": r["losses"], "top256": r["top256"], "day2": r["day2"], "cut": r["cut"],
                "partners": top_pairs(r["partners"], 15), "sample": 0}
        if d:
            item.update({"sample": d["sample"], "nature": top_pairs(d["nature"]), "item": top_pairs(d["item"]),
                         "ability": top_pairs(d["ability"]), "moves": top_pairs(d["moves"]),
                         "extra": {k: top_pairs(v) for k, v in d["extra"].items()}, "players": d["players"]})
        out.append(item)
    return out


# ---------- file ----------

def dump(path, obj):
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def list_events():
    data = get_json(API + "/vg/tournaments/")
    out = []
    for t in data["vg"]["data"]:
        city, kind = city_of(t["name"])
        start = (t.get("date") or {}).get("start") or ""
        out.append({"id": t["id"], "name": t["name"], "city": city, "kind": kind, "start": start,
                    "end": (t.get("date") or {}).get("end") or "", "status": t.get("tournamentStatus"),
                    "players": (t.get("players") or {}).get("masters", 0), "decklists": t.get("decklists", 0),
                    "rounds": (t.get("roundNumbers") or {}).get("masters", 0), "reg": reg_of(start),
                    "winner": (t.get("winners") or {}).get("masters"), "rk9": t.get("rk9link"),
                    "winners": {d: person((t.get("winners") or {}).get(d)) for d in ("masters", "seniors", "juniors")},
                    "players_div": t.get("players") or {}})
    out.sort(key=lambda e: e["start"], reverse=True)
    return out


def current_reg(events):
    today = time.strftime("%Y-%m-%d", time.gmtime())
    for e in events:                       # il piu' recente gia' iniziato: decide il regolamento "attuale"
        if e["start"] and e["start"] <= today:
            return e["reg"]
    return events[0]["reg"] if events else None


def save_winners(events):
    """Vincitori di ogni regionale (3 divisioni) con gli italiani in evidenza. Fonte: Pokedata."""
    out = []
    for e in events:
        if e["status"] != "finished":
            continue
        w = e.get("winners") or {}
        it = [{"div": d, "name": p["name"]} for d, p in w.items() if p and p["cc"] == "IT"]
        top = load(os.path.join(OUT, e["id"], "italiani.json"), [])
        out.append({"id": e["id"], "city": e["city"], "kind": e["kind"], "start": e["start"], "reg": e["reg"],
                    "players": e["players"], "winners": w, "italian_winners": it, "italians_top": top})
    return dump(os.path.join(OUT, "vincitori.json"), {"source": "Pokedata", "source_url": "https://www.pokedata.ovh",
                                                      "updated": time.strftime("%Y-%m-%d %H:%M", time.gmtime()), "events": out})


def save_index(events):
    """Elenco di tutti i regionali + regolamento attuale (si aggiorna da solo quando ne parte uno nuovo)."""
    done = {e["id"] for e in events if load(os.path.join(OUT, e["id"], "meta.json"), {}).get("players")}
    for e in events:
        e["collected"] = e["id"] in done
    a = dump(os.path.join(OUT, "index.json"), {"current": current_reg(events), "updated": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
                                                 "source": "Pokedata", "events": [{k: v for k, v in e.items() if k not in ("winners", "players_div")} for e in events]})
    return save_winners(events) or a


def collect(ev, write):
    tid = ev["id"]
    data = get_json("%s/vg/id/%s/division/masters" % (API, tid))
    info, players, teams, swiss, day1, swiss_total = process(data)
    names = {m["slug"]: m["name"] for t in teams.values() for m in t}
    for p in players:
        for s in (p["team"] or "").split(","):
            names.setdefault(s, s.replace("-", " ").title())
    stats = compute(players, teams, names)
    status = info.get("tournamentStatus")
    cut = sum(p["topcut"] for p in players)
    day2 = sum(p["day2"] for p in players)
    print("\n%s - %s - %s - %d giocatori, %d round" % (ev["name"], info.get("date", {}).get("start"), status, len(players), swiss_total))
    print("Squadre: %d (Top %d) - fase 2 stimata: %d (dopo il round %d) - top cut trovati: %d" % (len(teams), TOP, day2, day1, cut))
    print("%-18s %6s %7s %7s %6s %4s" % ("Pokemon", "Usati", "Vitt.%", "Top256", "Fase2", "Cut"))
    for s in stats[:10]:
        tot = s["wins"] + s["losses"]
        print("%-18s %6d %6.2f%% %7d %6d %4d" % (s["name"][:18], s["count"], 100.0 * s["wins"] / tot if tot else 0, s["top256"], s["day2"], s["cut"]))
    if unknown_forms:
        print("Forme non riconosciute (controlla il paste): %s" % ", ".join(sorted(unknown_forms)))
    unres = sum(1 for e in swiss.values() for x in e if x and x.startswith("-1"))
    print("Scontri senza avversario risolto: %d" % unres)
    if not write:
        return False
    folder = os.path.join(OUT, tid)
    old = load(os.path.join(folder, "meta.json"), {})
    meta = {"id": tid, "name": ev["name"], "city": ev["city"], "date": ev["start"], "end": ev["end"], "reg": ev["reg"],
            "players": len(players), "rounds": swiss_total, "status": status, "complete": status == "finished",
            "teams": len(teams), "top": TOP, "day1_rounds": day1, "day2_players": day2, "cut_players": cut, "source": "Pokedata (apiv3), dati RK9",
            "players_fields": ["id", "name", "country", "placement", "wins", "losses", "day2", "cut", "team"],
            "swiss": "per giocatore, una voce per round: id avversario + esito (W vinta, L persa, T pari, B bye; -1 = avversario non risolto)",
            "updated": time.strftime("%Y-%m-%d %H:%M", time.gmtime())}
    if {k: v for k, v in old.items() if k != "updated"} == {k: v for k, v in meta.items() if k != "updated"}:
        meta["updated"] = old.get("updated", meta["updated"])
    pl = [[p["tp_id"], p["name"], p["country"], p["placement"], p["wins"], p["losses"], p["day2"], p["topcut"], p["team"]]
          for p in sorted(players, key=lambda x: x["placement"])]
    tm = {k: [[m["slug"], m["name"], m["item"], m["ability"], m["nature"], m["moves"], m["extra"]] for m in v] for k, v in teams.items()}
    ita = [[p["placement"], p["name"], p["wins"], p["losses"]] for p in sorted(players, key=lambda x: x["placement"])
           if p["country"] == "IT" and p["placement"] <= 32]
    ch = [dump(os.path.join(folder, "italiani.json"), ita), dump(os.path.join(folder, "meta.json"), meta), dump(os.path.join(folder, "players.json"), pl),
          dump(os.path.join(folder, "pokemon.json"), stats), dump(os.path.join(folder, "teams.json"), tm),
          dump(os.path.join(folder, "swiss.json"), {"rounds": swiss_total, "p": {str(k): v for k, v in swiss.items()}})]
    print("File salvati in %s/ (%s)" % (folder, "cambiati" if any(ch) else "nessuna modifica"))
    return any(ch)


def main():
    global budget
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="elenco di tutti i regionali")
    g.add_argument("--id", help="id Pokedata del regionale, es. 1000076")
    g.add_argument("--auto", action="store_true", help="regionali in corso + finiti non ancora raccolti")
    ap.add_argument("--write", action="store_true", help="salva i file in vgcstats/ (senza: prova senza salvare nulla)")
    ap.add_argument("--max-events", type=int, default=2, help="con --auto: quanti regionali finiti non raccolti per giro")
    a = ap.parse_args()
    budget = int(os.environ.get("VGC_BUDGET", "6"))
    print("%s - massimo %d richieste" % ("SALVATAGGIO" if a.write else "PROVA (non salva nulla)", budget))
    try:
        if a.list or a.auto:
            events = list_events()
            print("Regionali trovati: %d - regolamento attuale: %s" % (len(events), current_reg(events)))
            for e in events[:8]:
                m = (e.get("winners") or {}).get("masters")
                print("  %s  %-22s %-9s %5d giocatori  %-5s vincitore: %s%s" % (e["start"], e["city"][:22], e["status"], e["players"], e["reg"],
                      m["name"] if m else "-", " [ITALIA]" if m and m["cc"] == "IT" else ""))
            if a.list:
                if a.write:
                    print("Elenco salvato." if save_index(events) else "Elenco invariato.")
                return 0
            todo = [e for e in events if e["status"] == "running"]
            todo += [e for e in events if e["status"] == "finished" and e["players"]
                     and not load(os.path.join(OUT, e["id"], "meta.json"), {}).get("complete")][:a.max_events]
            print("Da raccogliere ora: %s" % (", ".join(e["city"] for e in todo) or "niente"))
            for e in todo:
                collect(e, a.write)
            if a.write:
                save_index(events)
            return 0
        events = list_events()
        ev = next((e for e in events if e["id"] == a.id), None)
        if not ev:
            print("Regionale %s non trovato nell'elenco di Pokedata." % a.id)
            return 1
        collect(ev, a.write)
        if a.write:
            save_index(events)
        if not a.write:
            print("\nPROVA finita: non e' stato salvato nulla.")
        return 0
    except Budget:
        print("Raggiunto il massimo di richieste: rilancia.")
        return 0
    except Stop as e:
        print("STOP: %s - mi fermo qui" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
