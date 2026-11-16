#!/usr/bin/env python3
"""Aggiorna i set del calcolatore (calc.html) con quelli del Nimbasa City Post Damage Calculator di nerd-of-now.
Il calcolatore tiene dentro di se' una copia del motore originale (stringa ENGINE); qui si rimpiazzano solo i file
dei set copiati per intero (Champions = setdex_ncp-g10.js, piu' Showdown, Global Link, Smogon) se online sono cambiati.
Ogni file nuovo si controlla con node prima di usarlo: se qualcosa non torna, calc.html resta com'e'."""
import datetime, json, os, re, subprocess, sys, tempfile, urllib.request

CALC = "calc.html"
STATO = "calc_set_stato.json"   # quando e' stato fatto l'ultimo controllo
OGNI_GIORNI = 52                # 1 mese e 22 giorni tra un controllo automatico e l'altro (a mano: sempre)
RAW = "https://raw.githubusercontent.com/nerd-of-now/NCP-VGC-Damage-Calculator/master/script_res/"
API = "https://api.github.com/repos/nerd-of-now/NCP-VGC-Damage-Calculator"


def scarica(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rakings-calc-set"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def conta_set(js, var):
    """Fa girare il file con node e conta Pokemon e set: se non parte o e' vuoto, None."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js + "\n;const o=" + var + ";let n=0;for(const k in o)n+=Object.keys(o[k]).length;console.log(Object.keys(o).length+' '+n);")
        nome = f.name
    try:
        out = subprocess.run(["node", nome], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return None
        a, b = out.stdout.split()
        return int(a), int(b)
    except Exception:
        return None
    finally:
        os.unlink(nome)


def main():
    oggi = datetime.date.today()
    try:
        ultimo = datetime.date.fromisoformat(json.load(open(STATO, encoding="utf-8"))["ultimo"])
    except Exception:
        ultimo = None
    if os.environ.get("FORZA") != "1" and ultimo and (oggi - ultimo).days < OGNI_GIORNI:
        print("Ultimo controllo il %s: il prossimo dal %s. Niente da fare." % (ultimo, ultimo + datetime.timedelta(days=OGNI_GIORNI)))
        return 0
    s = open(CALC, encoding="utf-8").read()
    m = re.search(r'const ENGINE=(".*?");\n', s, re.S)
    if not m:
        print("ENGINE non trovato in calc.html: non tocco niente.")
        return 1
    lit = m.group(1)
    E = json.loads(lit)
    if json.dumps(E, ensure_ascii=False).replace("<", "\\u003c") != lit:
        print("Formato di ENGINE inatteso: non tocco niente.")
        return 1
    try:
        ramo = json.loads(scarica(API)).get("default_branch") or "master"
    except Exception:
        ramo = "master"
    raw = RAW.replace("/master/", "/%s/" % ramo)
    cambiati, letti = [], 0
    for blocco in re.finditer(r"<script[^>]*>(/\* script_res/(setdex_[\w.-]+\.js) \*/\n)(.*?)</script>", E, re.S):
        testa, file, vecchio = blocco.group(1), blocco.group(2), blocco.group(3)
        var = (re.match(r"\s*var\s+(\w+)", vecchio) or [None, None])[1]
        if not var or not var.startswith("SETDEX"):
            continue
        try:
            nuovo = scarica(raw + file)
        except Exception as ex:
            print("%s: non scaricato (%s), resta quello di prima." % (file, ex))
            continue
        letti += 1
        nuovo = nuovo.lstrip("﻿").replace("\r\n", "\n")
        if nuovo.strip() == vecchio.strip():
            print("%s: invariato." % file)
            continue
        cv, cn = conta_set(vecchio, var), conta_set(nuovo, var)
        if not cn or (cv and cn[1] < cv[1] * 0.7):
            print("%s: il file nuovo non mi convince (%s set prima, %s adesso): resta quello di prima." % (file, cv, cn))
            continue
        if "</script" in nuovo.lower():
            print("%s: contiene </script>, salto." % file)
            continue
        E = E.replace(testa + vecchio, testa + nuovo, 1)
        cambiati.append("%s (%s -> %s Pokemon/set)" % (file, cv, cn))
    if letti:   # la data si segna solo se nerd-of-now ha risposto: se era giu', si riprova il lunedi' dopo
        with open(STATO, "w", encoding="utf-8") as f:
            json.dump({"ultimo": oggi.isoformat()}, f)
    if not cambiati:
        print("Set gia' aggiornati: niente da fare." if letti else "nerd-of-now non ha risposto: riprovo la prossima volta.")
        return 0
    s = s[:m.start(1)] + json.dumps(E, ensure_ascii=False).replace("<", "\\u003c") + s[m.end(1):]
    open(CALC, "w", encoding="utf-8").write(s)
    print("Aggiornati:", "; ".join(cambiati))
    return 0


if __name__ == "__main__":
    sys.exit(main())
