#!/usr/bin/env python3
"""Gira nel repository PRIVATO delle richieste, quando il PROPRIETARIO mette un'etichetta sulla Issue.
Il sito pubblico è già scaricato (con la chiave di deploy) nella cartella "sito": qui si modifica solo sito/locali.json,
poi il workflow fa il commit e il push, e infine `concludi` commenta e chiude la Issue.
  (valgono sia per i report dei locali sia per gli annunci: la Issue dice quale dei due è)
  approvato -> aggiunge SOLO quel report a locali.json (o quell'annuncio a annunci.json) del sito
  rifiutato -> scarta la richiesta (il sito non viene toccato)
  rimosso   -> toglie dal sito un report già pubblicato
  fissato   -> (solo annunci) lo tiene in cima all'archivio Info; togliendo l'etichetta torna nell'archivio
Controlli doppi: il workflow filtra, e qui si ricontrolla chi ha messo l'etichetta e chi ha creato la Issue."""
import json, os, re, shutil, sys, urllib.error
from datetime import datetime, timezone

from locali_comune import (ANNUNCI_MAX, AUTORE_BOT, carica_annunci, carica_locali, data_it, gh, log, salva_annunci,
                           salva_locali, taglia_annunci)

FILE = os.path.join(os.environ.get("SITO_DIR", "sito"), "locali.json")
SITO = os.environ.get("SITO_DIR", "sito")
FILE_ANN = os.path.join(os.environ.get("SITO_DIR", "sito"), "annunci.json")
DIR_IMG = os.path.join(os.environ.get("SITO_DIR", "sito"), "img", "annunci")
RE_IMG = re.compile(r"^annunci_img/[0-9a-f]{24}\.jpg$")
ESITO = "esito_locali.json"   # resta nello spazio di lavoro del repository privato, non viene committato


def estrai(issue):
    m = re.search(r"<!-- LOCALI-DATA\s*(\{.*?\})\s*-->", issue.get("body") or "", re.S)
    if not m:
        raise RuntimeError("nella Issue non ci sono i dati della richiesta (non modificare il testo nascosto in fondo)")
    p = json.loads(m.group(1))
    for k in ("tipo", "negozio", "citta", "iso", "giocatori"):
        if k not in p:
            raise RuntimeError("dati della richiesta incompleti (manca %s)" % k)
    return p


def estrai_annuncio(issue):
    m = re.search(r"<!-- ANNUNCIO-DATA\s*(\{.*?\})\s*-->", issue.get("body") or "", re.S)
    if not m:
        raise RuntimeError("nella Issue non ci sono i dati dell'annuncio (non modificare il testo nascosto in fondo)")
    p = json.loads(m.group(1))
    if not p.get("titolo"):
        raise RuntimeError("dati dell'annuncio incompleti (manca il titolo)")
    return p


def copia_immagine(num, p):
    """Copia la foto dell'annuncio (salvata nel repository privato) nel sito; il percorso viene controllato."""
    src = p.get("img") or ""
    if not RE_IMG.match(src) or not os.path.exists(src):
        return ""
    os.makedirs(DIR_IMG, exist_ok=True)
    shutil.copyfile(src, os.path.join(DIR_IMG, "%d.jpg" % num))
    return "img/annunci/%d.jpg" % num


def voce_annuncio(num, p):
    ora = datetime.now(timezone.utc)
    e = {"id": num, "t": p["titolo"], "d": p.get("testo", ""), "pub": ora.strftime("%Y-%m-%dT%H:%M:%SZ")}
    img = copia_immagine(num, p)
    if img:
        e["img"] = img
    return e


def voce(num, p):
    mx = max(g["p"] for g in p["giocatori"])
    top, tm, rt = [""] * mx, {}, {}
    for g in p["giocatori"]:
        i = g["p"] - 1
        top[i] = g["nome"]
        if g["tm"]:
            tm[str(i)] = g["tm"]
        if g["rt"]:
            rt[str(i)] = g["rt"]
    e = {"id": num, "real": True, "pub": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "t": p["tipo"], "s": p["negozio"], "c": p["citta"], "d": data_it(p["iso"]),
         "iso": p["iso"], "n": p["n"] if p["n"] is not None else "n.d.", "top": top}
    if tm:
        e["tm"] = tm
    if rt:
        e["rt"] = rt
    return e


def commenta(num, testo):
    gh("POST", "/issues/%d/comments" % num, {"body": testo})


def chiudi(num, motivo):
    gh("PATCH", "/issues/%d" % num, {"state": "closed", "state_reason": motivo})


def agisci():
    num, az = int(os.environ["ISSUE_NUMBER"]), os.environ["AZIONE"]
    if not os.environ.get("OWNER") or os.environ.get("SENDER") != os.environ["OWNER"]:
        log("Etichetta messa da chi non è il proprietario del repository: ignorata.")
        return 0
    issue = gh("GET", "/issues/%d" % num)
    if (issue.get("user") or {}).get("login") != AUTORE_BOT:
        log("La Issue non è stata creata dal bot: ignorata.")
        return 0
    if "<!-- ANNUNCIO-DATA" in (issue.get("body") or ""):
        return agisci_annuncio(num, az, issue)
    if az == "fissato":
        log("Il pin vale solo per gli annunci: ignorato.")
        return 0
    d = carica_locali(FILE)
    if az == "approvato":
        e = voce(num, estrai(issue))
        d["locali"] = [v for v in d["locali"] if v.get("id") != num] + [e]
        salva_locali(d, FILE)
        es = {"num": num, "az": az,
              "ok": "✅ Pubblicato sul sito. La notifica parte tra circa 3 minuti: per fermarla (e togliere il report) metti `rimosso`."}
    elif az == "rifiutato":
        es = {"num": num, "az": az, "ok": "❌ Rifiutata: il sito non è stato modificato.", "chiudi": "not_planned"}
    elif az == "rimosso":
        prima = len(d["locali"])
        d["locali"] = [v for v in d["locali"] if v.get("id") != num]
        if len(d["locali"]) != prima:
            salva_locali(d, FILE)
        es = {"num": num, "az": az, "chiudi": "completed",
              "ok": "🗑️ Tolto dal sito." if len(d["locali"]) != prima else "Questo report non era pubblicato: il sito non è stato modificato."}
    else:
        return 0
    json.dump(es, open(ESITO, "w", encoding="utf-8"))
    log("Preparato: %s #%d" % (az, num))
    return 0


def agisci_annuncio(num, az, issue):
    d = carica_annunci(FILE_ANN)
    if az == "fissato":
        on = os.environ.get("EVENTO", "labeled") == "labeled"
        trovati = [v for v in d["annunci"] if v.get("id") == num]
        for v in trovati:
            if on:
                v["pin"] = True
            else:
                v.pop("pin", None)
        if trovati:
            salva_annunci(d, FILE_ANN)
            ok = "📌 Fissato in cima alla sezione Info." if on else "📌 Tolto dai fissati: resta nell'archivio Info."
        else:
            ok = "📌 Va bene: lo fisso in cima appena lo approvi." if on else "Ok: non verrà fissato."
        json.dump({"num": num, "az": az, "ok": ok}, open(ESITO, "w", encoding="utf-8"))
        log("Pin %s #%d" % ("messo" if on else "tolto", num))
        return 0
    if az == "approvato":
        e = voce_annuncio(num, estrai_annuncio(issue))
        if any(l.get("name") == "fissato" for l in issue.get("labels", [])):
            e["pin"] = True
        d["annunci"] = [v for v in d["annunci"] if v.get("id") != num] + [e]
        tolti = [i for i in taglia_annunci(d, SITO) if i != num]
        salva_annunci(d, FILE_ANN)
        es = {"num": num, "az": az, "taglia": tolti,
              "ok": "✅ Annuncio pubblicato nell'archivio della sezione Info%s. La notifica a tutti parte tra circa 3 minuti: per fermarla (e togliere l'annuncio) metti `rimosso`." % (" e fissato in cima" if e.get("pin") else "")
                    + ("\n\nL'archivio ha raggiunto il limite di %d annunci: ho tolto i %d più vecchi non fissati." % (ANNUNCI_MAX, len(tolti)) if tolti else "")}
    elif az == "rifiutato":
        es = {"num": num, "az": az, "ok": "❌ Rifiutato: il sito non è stato modificato.", "chiudi": "not_planned"}
    elif az == "rimosso":
        prima = len(d["annunci"])
        d["annunci"] = [v for v in d["annunci"] if v.get("id") != num]
        if len(d["annunci"]) != prima:
            salva_annunci(d, FILE_ANN)
        try:
            os.remove(os.path.join(DIR_IMG, "%d.jpg" % num))
        except OSError:
            pass
        es = {"num": num, "az": az, "chiudi": "completed",
              "ok": "🗑️ Tolto dal sito." if len(d["annunci"]) != prima else "Questo annuncio non era pubblicato: il sito non è stato modificato."}
    else:
        return 0
    json.dump(es, open(ESITO, "w", encoding="utf-8"))
    log("Preparato annuncio: %s #%d" % (az, num))
    return 0


def concludi():
    """Dopo il push: se è andato a buon fine commenta e chiude, altrimenti avvisa e lascia la Issue aperta."""
    if not os.path.exists(ESITO):
        return 0
    es = json.load(open(ESITO, encoding="utf-8"))
    num = es["num"]
    if os.environ.get("PUSH_OUTCOME") != "success":
        commenta(num, "⚠️ Non sono riuscito a scrivere sul sito: nulla è stato pubblicato. "
                      "Controlla l'esecuzione in Actions; per riprovare togli e rimetti l'etichetta.")
        return 1
    commenta(num, es["ok"])
    for vecchio in es.get("taglia", []):   # le richieste degli annunci tolti per il limite si chiudono
        try:
            commenta(vecchio, "🗑️ Tolto dall'archivio del sito: si è raggiunto il limite di %d annunci e questo era il più vecchio." % ANNUNCI_MAX)
            chiudi(vecchio, "completed")
        except Exception:
            pass
    if es["az"] == "rimosso":
        try:
            gh("DELETE", "/issues/%d/labels/approvato" % num)
        except urllib.error.HTTPError:
            pass
    if es.get("chiudi"):
        chiudi(num, es["chiudi"])
    return 0


if __name__ == "__main__":
    try:
        a = sys.argv[1:]
        sys.exit(agisci() if a == ["agisci"] else concludi() if a == ["concludi"] else 2)
    except (RuntimeError, urllib.error.URLError) as ex:
        log("[ERRORE]", type(ex).__name__, ex if isinstance(ex, RuntimeError) else "")
        sys.exit(1)
