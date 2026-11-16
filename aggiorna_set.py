#!/usr/bin/env python3
"""Aggiorna i set E il motore di calcolo (formule) del calcolatore (calc.html) dal Nimbasa City Post Damage Calculator di nerd-of-now.
Motore (ap_calc.js, damage_*.js, ko_chance.js, dati di mosse/strumenti/abilita'/Pokedex...): si aggiorna solo se la loro pagina
(index.html) e' rimasta la stessa di quando e' stato fatto il nostro calcolatore; se l'hanno cambiata, i file del motore NON si toccano
e il flusso diventa rosso (mail da GitHub): va adattato a mano. I set invece si aggiornano sempre.
Il calcolatore tiene dentro di se' una copia del motore originale (stringa ENGINE); qui si rimpiazzano solo i file
dei set copiati per intero (Champions = setdex_ncp-g10.js, piu' Showdown, Global Link, Smogon) se online sono cambiati.
Ogni file nuovo si controlla con node prima di usarlo: se qualcosa non torna, calc.html resta com'e'."""
import datetime, json, os, re, subprocess, sys, tempfile, urllib.request

CALC = "calc.html"
STATO = "calc_set_stato.json"   # quando e' stato fatto l'ultimo controllo
OGNI_GIORNI = 52                # 1 mese e 22 giorni tra un controllo automatico e l'altro (a mano: sempre)
RAW = "https://raw.githubusercontent.com/nerd-of-now/NCP-VGC-Damage-Calculator/master/script_res/"
API = "https://api.github.com/repos/nerd-of-now/NCP-VGC-Damage-Calculator"


INDEX_SHA = "2b47ecb1b697a0b51219c65d9a50d634eaeb46071e79ecf79e160231f577cdc6"   # index.html di nerd-of-now su cui e' fatto il calcolatore


def scarica(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rakings-calc-set"})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
    for enc in ("utf-8", "cp1252", "latin-1"):   # alcuni loro file non sono in utf-8
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("latin-1")


def sintassi_ok(js):
    """node --check: il file nuovo deve essere JavaScript valido."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        nome = f.name
    try:
        return subprocess.run(["node", "--check", nome], capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False
    finally:
        os.unlink(nome)


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
    cambiati, letti, allarme = [], 0, ""
    import hashlib
    try:
        sha = hashlib.sha256(scarica(raw.replace("script_res/", "") + "index.html").replace("\r\n", "\n").encode("utf-8")).hexdigest()
        motore_ok = sha == INDEX_SHA
        if not motore_ok:
            allarme = "nerd-of-now ha cambiato la sua pagina (index.html): il motore NON e' stato aggiornato, va adattato a mano."
    except Exception as ex:
        motore_ok = False
        print("index.html di nerd-of-now non letto (%s): il motore resta com'e'." % ex)
    for blocco in re.finditer(r"<script[^>]*>(/\* script_res/([\w.-]+\.js) \*/\n)(.*?)</script>", E, re.S):
        testa, file, vecchio = blocco.group(1), blocco.group(2), blocco.group(3)
        var = (re.match(r"\s*var\s+(\w+)", vecchio) or [None, None])[1]
        e_set = bool(var and var.startswith("SETDEX"))
        if not e_set and not motore_ok:
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
        if not e_set:   # file del motore: deve essere JavaScript valido e non troppo diverso di dimensione
            if not sintassi_ok(nuovo) or len(nuovo) < len(vecchio) * 0.7 or "</script" in nuovo.lower():
                print("%s: il file nuovo non mi convince: resta quello di prima." % file)
                continue
            E = E.replace(testa + vecchio, testa + nuovo, 1)
            cambiati.append("%s (motore)" % file)
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
    if allarme:
        print("[ATTENZIONE]", allarme)
    if not cambiati:
        print("Set e motore gia' aggiornati: niente da fare." if letti else "nerd-of-now non ha risposto: riprovo la prossima volta.")
        return 1 if allarme else 0
    s = s[:m.start(1)] + json.dumps(E, ensure_ascii=False).replace("<", "\\u003c") + s[m.end(1):]
    open(CALC, "w", encoding="utf-8").write(s)
    print("Aggiornati:", "; ".join(cambiati))
    return 1 if allarme else 0


if __name__ == "__main__":
    sys.exit(main())
