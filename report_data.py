#!/usr/bin/env python3
"""Prepara report.json per la sezione «Report» di Altopiano Blu: statistiche dalle partite VERE dei tornei ufficiali
del regolamento in corso (abbinamenti, risultati e squadre a lista aperta che VGC Stats raccoglie gia' in vgcstats/).
- matchup: per ogni coppia di Pokemon, partite vinte e perse da chi aveva il primo contro chi aveva il secondo
- giocatori: tornei, piazzamenti, record, squadra, Pokemon battuti piu' spesso e da cui e' stato fermato
Solo tornei finiti, niente coppe online. In piu' i Victory Road del regolamento in corso (repo VGCdatiAK, stesso formato):
se un file dei VR non si legge, report.json resta com'e' (si riprova al giro dopo, ogni ora). Si scrive solo se il contenuto cambia. Nessuna richiesta in rete."""
import json, os, re, sys, collections, urllib.request
from datetime import datetime, timezone

B = "vgcstats/"
OUT = "report.json"
MIN_COPPIA = 60          # una coppia di Pokemon entra nel file solo con almeno 60 partite (le righe poco affidabili restano fuori)
KIND = {"Regional Championships": "r", "International Championships": "i", "World Championship": "w"}
VR = "https://rakings.github.io/VGCdatiAK/vr/"


def scarica(u):
    req = urllib.request.Request(u + "?t=%d" % int(__import__("time").time() // 600), headers={"User-Agent": "rAKings report"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def leggi(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def valido(e):
    n = str(e.get("name") or "")
    if re.search(r"professor|online", n, re.I):
        return False
    return bool(e.get("kind")) or "Special" in n


def citta(e):
    return re.sub(r"^\d{4}\s+|\s+Pok.*$", "", str(e.get("city") or e.get("name") or "")).strip()


def main():
    idx = leggi(B + "index.json", {})
    reg = idx.get("current")
    evs = [e for e in idx.get("events", []) if e.get("reg") == reg and e.get("status") == "finished" and valido(e)
           and all(os.path.exists(B + "%s/%s.json" % (e["id"], f)) for f in ("players", "swiss", "teams"))]
    dati = {e["id"]: {f: leggi(B + "%s/%s.json" % (e["id"], f), None) for f in ("players", "swiss", "teams")} for e in evs}
    # Victory Road (online, lista aperta come i regionali)
    try:
        for e in scarica(VR + "index.json").get("events", []):
            if e.get("reg") == reg and e.get("status") == "finished" and e.get("id"):
                dati[e["id"]] = {f: scarica(VR + "%s/%s.json" % (e["id"], f)) for f in ("players", "swiss", "teams")}
                e = dict(e, kind="VR")
                evs.append(e)
    except Exception as x:
        print("Dati dei Victory Road non letti (%s): report.json resta com'e', si riprova al prossimo giro." % x)
        sys.exit(0)
    evs.sort(key=lambda e: e.get("start") or "")
    known = set()
    for e in evs:
        if e.get("kind") != "VR":
            for t in (dati[e["id"]]["teams"] or {}).values():
                for m in t:
                    known.add(re.sub(r"-male$", "-m", re.sub(r"-female$", "-f", m[0])))

    def base(x):
        """I VR scrivono le forme Mega (charizard-mega-y), i regionali il Pokemon base: si usa lo stesso nome per tutti."""
        b = re.sub(r"-mega(-[xyz])?$", "", x)
        b = re.sub(r"-male$", "-m", re.sub(r"-female$", "-f", b))
        if b in known:
            return b
        alt = sorted(k for k in known if k.startswith(b + "-"))
        if b + "-m" in alt:            # Basculegion: forma maschio, come nei regionali
            return b + "-m"
        return alt[0] if len(alt) == 1 else b
    nomi, tot, mu = {}, collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
    gioc = {}
    for ei, e in enumerate(evs):
        vr = e.get("kind") == "VR"
        P = {}
        for p in dati[e["id"]]["players"] or []:
            p = list(p)
            p[8] = ",".join((base(x) if vr else re.sub(r"-male$", "-m", re.sub(r"-female$", "-f", x))) for x in str(p[8] or "").split(",") if x)
            P[str(p[0])] = p
        TM = {k: [[base(m[0]) if vr else re.sub(r"-male$", "-m", re.sub(r"-female$", "-f", m[0]))] + list(m[1:]) for m in v] for k, v in (dati[e["id"]]["teams"] or {}).items()}
        for t in TM.values():
            for m in t:
                if not vr:
                    nomi.setdefault(m[0], m[1])
        S = (dati[e["id"]]["swiss"] or {}).get("p", {})
        for pid, rs in S.items():
            p = P.get(pid)
            if not p:
                continue
            A = [re.sub(r"-male$", "-m", re.sub(r"-female$", "-f", x)) for x in str(p[8] or "").split(",") if x]
            for x in A:
                nomi.setdefault(x, x.replace("-", " ").title())
            k = (str(p[1]).strip(), str(p[2] or ""))
            g = gioc.setdefault((k[0].lower() + "|" + k[1]), {"n": k[0], "c": k[1], "t": [], "b": collections.Counter(), "f": collections.Counter(),
                                                               "bu": collections.Counter(), "fu": collections.Counter()})
            w = l = 0
            for x in rs:
                m = re.match(r"^(-?\d+)([WLTB?])$", x or "")
                if not m:
                    continue
                r = m.group(2)
                w += r in "WB"
                l += r == "L"
                o = P.get(m.group(1)) if m.group(1) not in ("0", "-1") else None
                if not o or r not in "WL":
                    continue
                Bt = [y for y in str(o[8] or "").split(",") if y]
                for y in Bt:
                    (g["b"] if r == "W" else g["f"])[y] += 1
                    if not vr:   # stessi conteggi senza i Victory Road (pulsante «Senza VR» nel Report Giocatore)
                        (g["bu"] if r == "W" else g["fu"])[y] += 1
                if not A or not Bt:
                    continue
                for a in A:
                    tot[a][0 if r == "W" else 1] += 1
                    for b in Bt:
                        if a != b and b not in A:
                            mu[(a, b)][0 if r == "W" else 1] += 1
            st = {m[0]: str(m[2] or "") for m in TM.get(pid, []) if isinstance(m, list) and len(m) > 2}   # strumenti: solo Top 256
            g["t"].append([ei, int(p[3] or 0), w, l, A, [st.get(x, "") for x in A]])
    # elenco dei Pokemon per indice (file piu' piccolo): i piu' usati per primi
    ordine = sorted(nomi, key=lambda s: -sum(tot.get(s, [0, 0])))
    pos = {s: i for i, s in enumerate(ordine)}
    strum = sorted({x for g in gioc.values() for t in g["t"] for x in t[5] if x})
    spos = {x: i for i, x in enumerate(strum)}
    out = {
        "v": 1, "reg": reg,
        "ev": [[e["id"], citta(e), ("v" if e.get("kind") == "VR" else KIND.get(e.get("kind"), "s")), e.get("start"), int(e.get("players") or 0)] for e in evs],
        "mon": [[s, nomi[s]] + list(tot.get(s, [0, 0])) for s in ordine],
        "it": strum,
        "mu": [[pos[a], pos[b], v[0], v[1]] for (a, b), v in mu.items() if sum(v) >= MIN_COPPIA],
        "pl": [[g["n"], g["c"], [[t[0], t[1], t[2], t[3], [pos[x] for x in t[4] if x in pos], [spos.get(y, -1) for x, y in zip(t[4], t[5]) if x in pos]] for t in g["t"]],
                [[pos[x], n] for x, n in g["b"].most_common(4) if x in pos], [[pos[x], n] for x, n in g["f"].most_common(4) if x in pos],
                ] + ([[[pos[x], n] for x, n in g["bu"].most_common(4) if x in pos], [[pos[x], n] for x, n in g["fu"].most_common(4) if x in pos]]
                     if any(evs[t[0]].get("kind") == "VR" for t in g["t"]) else [])   # solo per chi ha giocato anche dei VR
               for g in sorted(gioc.values(), key=lambda g: (-len(g["t"]), g["n"].lower()))],
    }
    vecchio = leggi(OUT, None)
    if vecchio:
        vecchio.pop("agg", None)
    if vecchio == out:
        print("report.json invariato")
        return
    out["agg"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("report.json scritto: %d tornei, %d Pokemon, %d coppie, %d giocatori, %d byte"
          % (len(evs), len(ordine), len(out["mu"]), len(out["pl"]), os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
