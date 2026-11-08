#!/usr/bin/env python3
"""Avviso IMMEDIATO «Vincitore Regionale» (canale winner), lanciato in automatico dalla diretta dei Regionali.

Quando la diretta (vgc_stats.py, modo live) vede che la finale della Top 8 e' decisa, lancia il flusso «Avviso vincitore Regionale (diretta)»,
che esegue questo script con i dati del tabellone (variabili AV_*). Non serve lanciarlo a mano.
Lo stato (notify_live_state.json) serve a due cose: non mandare lo stesso avviso due volte e far sapere a notify_players.py che
il vincitore e' gia' stato avvisato, cosi' quando Limitless pubblica il risultato (anche giorni dopo) non parte un secondo avviso.
Se qualcosa non funziona l'avviso di Limitless resta il piano B: non si perde niente."""
import json, os, re, sys, unicodedata
from datetime import datetime, timedelta, timezone

import update_events as ue

STATE = "notify_live_state.json"
MAX_GIORNI = 4      # non si manda un avviso per un torneo finito da piu' di 4 giorni
TENUTI = 60         # quanti vincitori tenere nello stato


def nz(s):
    """Nome o citta' senza accenti, maiuscole e segni: 'Gdańsk' = 'gdansk'."""
    t = unicodedata.normalize("NFKD", str(s or ""))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)).lower())


def persona(txt):
    nome, _, cc = str(txt or "").partition("|")
    return nome.strip(), cc.strip()


def riga(n, p):
    return "%s%s" % (p[0], (" (%s)" % p[1]) if p[1] else "")


def testo(citta, vincitore, finalista, semifinali):
    """Titolo e corpo dell'avviso: stessa forma di quello da Limitless («Regional Citta (PAESE)», poi i primi posti)."""
    v = persona(vincitore)
    righe = ["Regional %s%s" % (citta, (" (%s)" % v[1]) if v[1] else ""), "1. " + riga(1, v)]
    f = persona(finalista)
    if f[0]:
        righe.append("2. " + riga(2, f))
    semi = [persona(x) for x in str(semifinali or "").split(";") if persona(x)[0]]
    if semi:
        righe.append("Semifinali: " + ", ".join(riga(0, p) for p in semi))
    return "Vincitore Regionale: %s" % v[0], "\n".join(righe)


def main(env=None, ora=None):
    e = env if env is not None else os.environ
    if not (e.get("NTFY_PREFIX") or ue.push_on()):
        print("Avviso vincitore: notifiche non configurate, niente da fare.")
        return 0
    eid, citta, fine = (e.get("AV_ID") or "").strip(), (e.get("AV_CITTA") or "").strip(), (e.get("AV_FINE") or "").strip()
    vincitore, finalista, semi = e.get("AV_VINCITORE") or "", e.get("AV_FINALISTA") or "", e.get("AV_SEMIFINALI") or ""
    if not eid.isdigit() or not persona(vincitore)[0] or not citta:
        print("Avviso vincitore: dati incompleti (id=%r, citta=%r, vincitore=%r): non mando niente." % (eid, citta, vincitore))
        return 0
    adesso = ora or datetime.now(timezone.utc)
    try:
        d = datetime.strptime(fine[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if adesso - d > timedelta(days=MAX_GIORNI):
            print("Avviso vincitore: il torneo e' finito il %s, da piu' di %d giorni: non mando niente." % (fine[:10], MAX_GIORNI))
            return 0
    except ValueError:
        pass   # senza data valida si manda lo stesso (e' la diretta che lo ha deciso)
    st = ue.load(STATE, None)
    st = st if isinstance(st, dict) else {}
    sent = [x for x in (st.get("sent") or []) if isinstance(x, dict)]
    if any(str(x.get("id")) == eid for x in sent):
        print("Avviso vincitore: per il torneo %s e' gia' stato mandato: non lo rimando." % eid)
        return 0
    titolo, corpo = testo(citta, vincitore, finalista, semi)
    click = ue.sito_url("winner").split("#")[0] + "#stats-reg-" + eid   # il tocco apre VGC Stats sul tabellone TOP 8 di questo Regionale
    print("Avviso vincitore: %s | %s" % (titolo, corpo.replace("\n", " / ")))
    try:
        ue.deliver("winner", titolo, corpo, click)
    except Exception as ex:
        print("Avviso vincitore NON inviato: %s (resta l'avviso da Limitless)" % str(ex)[:160])
        return 1
    sent.append({"id": eid, "city": citta, "winner": persona(vincitore)[0], "t": adesso.strftime("%Y-%m-%dT%H:%M:%SZ")})
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"sent": sent[-TENUTI:]}, f, ensure_ascii=False, indent=1)
    print("Avviso vincitore inviato e stato aggiornato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
