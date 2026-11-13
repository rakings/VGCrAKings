#!/usr/bin/env python3
"""Chiusura di OneSignal (13 novembre 2026): toglie dall'archivio iscritti (Worker vgc-subs) i vecchi record OneSignal («os», ID in formato UUID).
Non tocca MAI gli iscritti Firebase: il Worker toglie un ID UUID solo dalla parte OneSignal (chiave s:), e qui si controlla
che gli iscritti Firebase siano gli stessi prima e dopo. Nel registro solo numeri, nessun ID."""
import json, os, re, sys, time, urllib.request

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
MASSIMO = 100   # freno: i record OneSignal erano 14; se ne trova di piu' si ferma senza togliere niente
PAUSA = 20   # secondi tra un controllo e l'altro (9 controlli = 3 minuti)
UA = "rakings-vgc-bot (chiusura OneSignal)"

def chiama(percorso, dati=None):
    url = os.environ["SUBS_URL"].rstrip("/") + percorso
    hdr = {"Authorization": "Bearer " + os.environ["SUBS_TOKEN"], "User-Agent": UA}
    if dati is not None:
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(dati).encode("utf-8") if dati is not None else None, headers=hdr, method="POST" if dati is not None else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8") or "{}")

def elenco(tipo):
    r = chiama("/list?kind=" + tipo)
    if not isinstance(r.get("subs"), list):
        raise RuntimeError("risposta del Worker non valida")
    return [s.get("id", "") for s in r["subs"]]

def main():
    if not os.environ.get("SUBS_URL") or not os.environ.get("SUBS_TOKEN"):
        print("ERRORE: mancano SUBS_URL (variabile) o SUBS_TOKEN (segreto) su GitHub.")
        return 1
    try:
        fcm_prima = elenco("fcm")
        vecchi = elenco("os")
    except Exception as ex:
        print("ERRORE: l'archivio iscritti non risponde (%s). Non ho tolto niente." % str(ex)[:120])
        return 1
    print("Archivio prima: %d iscritti Firebase, %d record OneSignal vecchi." % (len(fcm_prima), len(vecchi)))
    da_togliere = [i for i in vecchi if UUID.match(i or "")]
    if len(da_togliere) != len(vecchi):
        print("Attenzione: %d record OneSignal con ID strano: lasciati stare." % (len(vecchi) - len(da_togliere)))
    if not da_togliere:
        print("Niente da togliere: OneSignal e' gia' pulito.")
        return 0
    if len(da_togliere) > MASSIMO:
        print("FRENO: trovati %d record OneSignal (attesi circa 14). Non ho tolto niente: chiedi a Claude." % len(da_togliere))
        return 1
    tolti = 0
    for k in range(0, len(da_togliere), 200):
        try:
            tolti += int(chiama("/remove", {"ids": da_togliere[k:k + 200]}).get("removed", 0))
        except Exception as ex:
            print("ERRORE durante la rimozione (%s)." % str(ex)[:120])
            return 1
    print("Tolti: %d record OneSignal." % tolti)
    # L'elenco di Cloudflare (KV) si aggiorna con un ritardo fino a circa 60 secondi: si ricontrolla per qualche minuto.
    os_dopo = None
    for prova in range(9):
        time.sleep(PAUSA)
        try:
            fcm_dopo, os_dopo = elenco("fcm"), elenco("os")
        except Exception as ex:
            print("Controllo finale non riuscito (%s): riprovo." % str(ex)[:120])
            continue
        if not os_dopo:
            break
        print("L'elenco di Cloudflare mostra ancora %d record OneSignal: e' normale per circa un minuto, ricontrollo." % len(os_dopo))
    if os_dopo is None:
        print("Il controllo finale non e' riuscito.")
        return 1
    print("Archivio dopo: %d iscritti Firebase, %d record OneSignal." % (len(fcm_dopo), len(os_dopo)))
    if set(fcm_dopo) != set(fcm_prima):
        print("Nota: gli iscritti Firebase sono cambiati durante il lavoro (%d -> %d): normale se qualcuno si e' iscritto o ha cambiato scelte adesso." % (len(fcm_prima), len(fcm_dopo)))
    if os_dopo:
        print("ATTENZIONE: restano %d record OneSignal." % len(os_dopo))
        return 1
    print("FATTO: OneSignal tolto dall'archivio. Iscritti Firebase intatti.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
