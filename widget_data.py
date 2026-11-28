#!/usr/bin/env python3
"""Prepara widget.json: il file PICCOLO che leggono i widget dell'app Android (pochi KB, invece dei file grandi del sito).
Contiene: prossimo VR, prossimo Regionale/Internazionale, i prossimi money tournament (dal premio piu' alto),
CP bar (soglia + primi 150), gli ultimi annunci della bacheca, le ultime Top 8 dei locali
e l'indirizzo di widget_usage.json (usage generale del regolamento in corso, file a parte). Si scrive solo se il contenuto cambia."""
import json, os, re, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from social import premio_testo, valore_eur

ROMA = ZoneInfo("Europe/Rome")
CP_URL = "https://rakings.github.io/VGCdatiAK/dati/cp/vg-europe-masters.json"
OUT = "widget.json"
SITO = "https://rakings.github.io/VGCrAKings/"


def eh(u):
    """Stesso codice corto del sito (eh() in index.html) per aprire la scheda del torneo: #e=..."""
    h = 5381
    b = u.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = (h * 33 + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    s, a = "", "0123456789abcdefghijklmnopqrstuvwxyz"
    while True:
        h, r = divmod(h, 36)
        s = a[r] + s
        if h == 0:
            return s


def leggi(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def corto(e):
    n = str(e.get("name") or "")
    if e.get("org") == "Victory Road":
        return re.sub(r"^(VR|Victory Road)\s+", "", n, flags=re.I)
    return re.sub(r"\s+(Regional|International)\s+Championships?$", "", re.sub(r"\s+Championships?$", "", n) if not re.search(r"(Regional|International)\s+Championships?$", n) else n, flags=re.I) or n


def ev_w(e, tipo):
    return {"k": tipo, "n": corto(e), "d": e.get("date"), "e": e.get("end") or e.get("date"), "t": e.get("time") or "",
            "u": SITO + ("#e=" + eh(e["url"]) if e.get("url") else "")}


KIND_OK = ("Regional Championships", "International Championships", "Special Championships", "World Championship")
OUT_US = "widget_usage.json"


def usage():
    """Usage generale per il widget «Top usage»: somma dei tornei FINITI del regolamento in corso (Regionali, Internazionali,
    Special, Mondiali) con le squadre. Per ogni Pokemon: % di squadre che lo usano e i set piu' usati (strumento, abilita',
    natura, mosse) dalle squadre complete. Solo testo, nessuna immagine. File a parte: lo scarica solo chi ha messo il widget."""
    idx = leggi("vgcstats/index.json", {})
    cur = idx.get("current")
    ev = [e for e in idx.get("events", []) if e.get("reg") == cur and e.get("status") == "finished" and e.get("decklists")
          and e.get("kind") in KIND_OK and os.path.exists("vgcstats/%s/pokemon.json" % e.get("id"))]
    if not cur or not ev:
        return None
    tot, P = 0, {}
    for e in ev:
        tot += int(e.get("decklists") or 0)
        for x in leggi("vgcstats/%s/pokemon.json" % e["id"], []):
            q = P.setdefault(x.get("slug"), {"n": x.get("name") or x.get("slug"), "c": 0, "s": 0, "item": {}, "ability": {}, "nature": {}, "moves": {}})
            q["c"] += int(x.get("count") or 0)
            q["s"] += int(x.get("sample") or 0)
            for k in ("item", "ability", "nature", "moves"):
                for nome, c in x.get(k) or []:
                    q[k][nome] = q[k].get(nome, 0) + int(c)
    if tot <= 0:
        return None
    def top(d, s, n):
        return [[k, round(100 * v / s)] for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n] if round(100 * v / s) >= 1] if s > 0 else []
    righe = sorted(P.values(), key=lambda q: -q["c"])[:100]
    r = [[q["n"], round(100 * q["c"] / tot, 1), top(q["item"], q["s"], 3), top(q["ability"], q["s"], 2), top(q["nature"], q["s"], 2), top(q["moves"], q["s"], 6)]
         for q in righe]
    return {"v": 1, "reg": cur, "ev": len(ev), "sq": tot, "r": r}


def lettere(e):
    """Colori del calendario, come dotCols() in index.html: o online, w Mondiale, i Internazionale, s Special, r Regionale;
    in piu' v Victory Road, g Global Challenge, m money tournament."""
    c = ["o" if e.get("mode") == "online" else {"Mondiale": "w", "Internazionale": "i", "Special Event": "s"}.get(e.get("type"), "r")]
    if e.get("org") == "Victory Road" or re.search(r"victoryroad\.pro/vr-", str(e.get("url") or "")):
        c.append("v")
    if e.get("type") == "Global Challenge":
        c.append("g")
    if e.get("cash") is True:
        c.append("m")
    return c


def calendario(ev):
    """Widget Calendario: per ogni giorno le lettere dei tipi di torneo (es. {"2026-12-05":"omv"}). Pochi KB."""
    giorni = {}
    for e in ev:
        if not e.get("date"):
            continue
        try:
            d = datetime.fromisoformat(e["date"]).date()
            f = datetime.fromisoformat(e.get("end") or e["date"]).date()
        except Exception:
            continue
        for _ in range(40):            # tornei di piu' giorni (massimo 40 per sicurezza)
            if d > f:
                break
            k = d.isoformat()
            for x in lettere(e):
                if x not in giorni.get(k, ""):
                    giorni[k] = giorni.get(k, "") + x
            d += timedelta(days=1)
    return dict(sorted(giorni.items()))


def main():
    oggi = datetime.now(ROMA).date().isoformat()
    ev = leggi("events.json", {}).get("events", [])
    fut = sorted([e for e in ev if e.get("date") and (e.get("end") or e["date"]) >= oggi], key=lambda e: (e["date"], e.get("time") or ""))
    vr = next((e for e in fut if e.get("org") == "Victory Road"), None)
    rg = next((e for e in fut if e.get("mode") == "regional"), None)
    tipo = lambda e: {"Internazionale": "int", "Mondiale": "ww", "Special Event": "sp"}.get(e.get("type"), "reg")
    fine = (datetime.now(ROMA).date() + timedelta(days=7)).isoformat()
    mon = [e for e in fut if e.get("type") == "Torneo" and e.get("cash") and "victoryroad.pro" not in str(e.get("url")) and e["date"] <= fine]
    for e in mon:
        e["_p"] = premio_testo(e)
        e["_v"] = valore_eur(e["_p"]) or valore_eur(e.get("name"))
    mon.sort(key=lambda e: (e["_v"] is None, -(e["_v"] or 0), e["date"]))
    money = [{"p": e["_p"], "n": e["name"], "d": e["date"], "t": e.get("time") or "", "u": SITO + "#e=" + eh(e["url"])} for e in mon[:6] if e.get("url")]

    cp = {}
    try:
        with urllib.request.urlopen(CP_URL, timeout=30) as r:
            c = json.load(r)
        cp = {"st": c.get("stagione"), "agg": c.get("aggiornato"), "tot": c.get("giocatori_totali"),
              "sg": (c.get("soglia") or {}).get("cp"), "sp": (c.get("soglia") or {}).get("posizione"),
              "r": [[x["pos"], x["name"], x.get("country") or "", x["cp"]] for x in c.get("righe", [])[:150]],
              "tutti": "https://rakings.github.io/VGCdatiAK/dati/cp/" + c["tutti"] if c.get("tutti") else ""}
    except Exception as x:
        print("CP non letta:", x)
        cp = leggi(OUT, {}).get("cp", {})   # tengo l'ultima buona

    an = leggi("annunci.json", {}).get("annunci", [])
    an.sort(key=lambda a: (not a.get("pin"), a.get("pub") or ""), reverse=False)
    an = sorted(an, key=lambda a: a.get("pub") or "", reverse=True)
    an = [a for a in an if a.get("pin")][:1] + [a for a in an if not a.get("pin")][:4]
    bk = [{"id": a["id"], "t": a.get("t", ""), "d": a.get("d", "")[:220], "pin": bool(a.get("pin")),
           "p": {"pardini": "Francesco Pardini", "rakings": "rAKings VGC"}.get(a.get("partner"), ""), "img": SITO + a["img"] if a.get("img") else "",
           "pub": a.get("pub", ""), "u": SITO + "#annuncio-%s" % a["id"]} for a in an]

    # Top 8 dei locali: gli ultimi 3 (il widget ne mostra 1, 2 o 3 a scelta). Squadra: solo i NOMI dei Pokemon, nessuna immagine.
    lo = [l for l in leggi("locali.json", {}).get("locali", []) if l.get("real", True) and l.get("top")]
    lo.sort(key=lambda l: (l.get("iso") or "", l.get("pub") or ""), reverse=True)
    lc = [{"id": l.get("id"), "t": l.get("t", ""), "s": l.get("s", ""), "c": l.get("c", ""), "d": l.get("d", ""), "n": l.get("n") or 0,
           "top": [str(x) for x in (l.get("top") or [])[:8]],
           "tm": {k: [str(m.get("n", "")) for m in v if isinstance(m, dict) and m.get("n")] for k, v in (l.get("tm") or {}).items() if isinstance(v, list)},
           "u": SITO + "#locali-" + eh("|".join([l.get("t", ""), l.get("s", ""), l.get("c", ""), l.get("d", "")]))} for l in lo[:3]]

    # calendario: i giorni gia' passati non sono piu' in events.json, quindi si tengono quelli dell'ultimo widget.json (dal mese scorso in poi)
    cal = calendario(ev)
    inizio = (datetime.now(ROMA).date().replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    for k, x in (leggi(OUT, {}).get("cal") or {}).items():
        if inizio <= k < oggi and k not in cal:
            cal[k] = x
    cal = dict(sorted(cal.items()))

    w = {"v": 1, "vr": ev_w(vr, "vr") if vr else None, "rg": ev_w(rg, tipo(rg)) if rg else None, "money": money, "cp": cp, "bk": bk, "lc": lc,
         "cal": cal,
         "live": {"reg": SITO + "vgcstats/index.json", "vr": "https://rakings.github.io/VGCdatiAK/vr/index.json"}}
    us = usage()
    if us and leggi(OUT_US, None) != us:
        with open(OUT_US, "w", encoding="utf-8") as f:
            json.dump(us, f, ensure_ascii=False, separators=(",", ":"))
        print("widget_usage.json scritto (%d byte)" % os.path.getsize(OUT_US))
    w["us"] = SITO + OUT_US if us else ""
    vecchio = leggi(OUT, None)
    if vecchio:
        vecchio.pop("agg", None)
    if vecchio == w:
        print("widget.json invariato")
        return
    w["agg"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, separators=(",", ":"))
    print("widget.json scritto (%d byte)" % os.path.getsize(OUT))


if __name__ == "__main__":
    main()
