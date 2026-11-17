#!/usr/bin/env python3
"""Prepara widget.json: il file PICCOLO che leggono i widget dell'app Android (pochi KB, invece dei file grandi del sito).
Contiene: prossimo VR, prossimo Regionale/Internazionale, i prossimi money tournament (dal premio piu' alto),
CP bar (soglia + primi 150) e gli ultimi annunci della bacheca. Si scrive solo se il contenuto cambia."""
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

    w = {"v": 1, "vr": ev_w(vr, "vr") if vr else None, "rg": ev_w(rg, tipo(rg)) if rg else None, "money": money, "cp": cp, "bk": bk,
         "live": {"reg": SITO + "vgcstats/index.json", "vr": "https://rakings.github.io/VGCdatiAK/vr/index.json"}}
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
