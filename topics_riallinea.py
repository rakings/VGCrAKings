#!/usr/bin/env python3
"""RIALLINEAMENTO DEGLI ARGOMENTI FIREBASE (FCM topics).

Porta gli argomenti di OGNI dispositivo dell'archivio iscritti a quello che quel dispositivo ha scelto (canali, promemoria, tornei seguiti).
Serve per: la MIGRAZIONE dei dispositivi che c'erano gia', e poi come controllo periodico (e' sicuro rilanciarlo quando vuoi).
Non scrive nell'archivio iscritti, salvo UNA cosa, solo se la chiedi (RIALL_RIMUOVI_MORTI = si, e solo in modo esegui): toglie dall'archivio i dispositivi che
Google dichiara NON PIU' VALIDI (UNREGISTERED: app disinstallata, dati cancellati, token scaduto): non possono ricevere niente. Se un giorno la persona riapre
il sito, il dispositivo si registra di nuovo da solo. C'e' un freno di sicurezza: se piu' della meta' dei dispositivi (almeno 5) risulta non valida tutta
insieme, non si toglie niente (e' piu' probabile un problema di configurazione che di dispositivi morti).
Su Google tocca solo gli argomenti nostri
(tutti, c_..., h_..., t_...): qualunque altro argomento (per esempio «prova-...») non si tocca mai.

  modo = controlla  ->  NON scrive niente su Google: dice solo quali dispositivi sono gia' a posto e quali no
  modo = esegui     ->  aggiunge gli argomenti che mancano e toglie quelli che non servono piu', poi ricontrolla
  RIALL_RIMUOVI_MORTI = si  ->  (solo con esegui) toglie dall'archivio i dispositivi non piu' validi; in modo controlla dice solo quanti ne toglierebbe.

Non stampa mai un token intero (solo le ultime 6 lettere).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "rAKings-VGC-riallineamento-argomenti"
NS = re.compile(r"^(tutti|c_[a-z0-9_]+|h_[a-z0-9]+|t_[0-9a-z]{1,8})$")   # gli argomenti che gestiamo noi
PARALLELE = 6
TENTATIVI = 4
_FCM = {}


def argomenti_di(m):
    """Gli argomenti voluti da un dispositivo, dalle sue scelte: stessa regola del Worker (argomentiDi)."""
    s = {"tutti"}
    for x in m.get("c") or []:
        n = "money_all" if x == "money=all" else "money_33" if x == "money=33" else x
        if isinstance(n, str) and re.fullmatch(r"[a-z0-9_]+", n):
            s.add("c_" + n)
    for x in m.get("h") or []:
        if isinstance(x, str) and re.fullmatch(r"[a-z0-9]+", x):
            s.add("h_" + x)
    for x in m.get("f") or []:
        if isinstance(x, str) and re.fullmatch(r"[0-9a-z]{1,8}", x):
            s.add("t_" + x)
    return s


def fcm_access_token():
    import base64
    import subprocess
    import tempfile
    if _FCM.get("tok") and time.time() < _FCM["exp"] - 120:
        return _FCM["tok"]
    try:
        info = json.loads(os.environ["FCM_SERVICE_ACCOUNT"])
        key, mail = info["private_key"], info["client_email"]
    except Exception:
        raise RuntimeError("FCM_SERVICE_ACCOUNT non e' valido.")
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    now = int(time.time())
    head = b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = b64(json.dumps({"iss": mail, "scope": "https://www.googleapis.com/auth/firebase.messaging",
                             "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600}, separators=(",", ":")).encode())
    msg = (head + "." + claims).encode()
    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, key.encode())
        os.close(fd)
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", path], input=msg, capture_output=True, check=True).stdout
    except Exception:
        raise RuntimeError("Firma per Firebase non riuscita.")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    form = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": head + "." + claims + "." + b64(sig)}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        raise RuntimeError("Accesso a Google rifiutato: HTTP %s" % ex.code)
    _FCM["tok"], _FCM["exp"] = r["access_token"], now + int(r.get("expires_in", 3600))
    return _FCM["tok"]


def corto(txt, n=160):
    """Una riga sola, SENZA token (i registri di questo repo sono pubblici)."""
    t = " ".join(str(txt).split())
    t = re.sub(r"(registrations/)[^\s'\"/]+", r"\1<token>", t)
    t = re.sub(r"[A-Za-z0-9_-]{8,}:APA91[A-Za-z0-9_-]*", "<token>", t)
    return t[:n]


def chiama(metodo, url, access, corpo=None, timeout=30):
    dati = None if corpo is None else json.dumps(corpo).encode("utf-8")
    hdr = {"Authorization": "Bearer " + access, "Content-Type": "application/json; charset=UTF-8", "User-Agent": UA}
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=dati, headers=hdr, method=metodo), timeout=timeout)
        return getattr(r, "status", 200), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode("utf-8", "replace")
    except Exception as ex:
        return 0, str(ex)


def morto(st, txt):
    return (st == 404 and re.search(r"UNREGISTERED|NOT_FOUND|not a valid FCM registration token", txt) is not None) or "UNREGISTERED" in txt


def elenco_iscrizioni():
    """Legge dall'archivio SOLO le iscrizioni Firebase, a pagine da 1000. Non scrive niente."""
    base = os.environ["SUBS_URL"].rstrip("/") + "/list"
    hdr = {"Authorization": "Bearer " + os.environ["SUBS_TOKEN"], "User-Agent": UA}
    subs, cursor = [], None
    for _ in range(200):
        q = [("kind", "fcm"), ("limit", "1000")]
        if cursor:
            q.append(("cursor", cursor))
        dati = json.loads(urllib.request.urlopen(urllib.request.Request(base + "?" + urllib.parse.urlencode(q), headers=hdr), timeout=30).read().decode("utf-8"))
        subs += dati.get("subs") or []
        cursor = dati.get("cursor")
        if not cursor:
            break
    return subs


class Google:
    def __init__(self, access, progetto):
        self.access, self.progetto = access, progetto

    def url(self, token, coda=""):
        return "https://fcm.googleapis.com/v1/projects/%s/registrations/%s/topicSubscriptions%s" % (self.progetto, urllib.parse.quote(token, safe=":"), coda)

    def con_ritentativi(self, metodo, url, corpo=None):
        """429 e errori del server (o di rete) si ritentano con attesa crescente."""
        for n in range(TENTATIVI):
            st, txt = chiama(metodo, url, self.access, corpo)
            if st not in (0, 429, 500, 502, 503, 504):
                return st, txt
            if n < TENTATIVI - 1:
                time.sleep(2 * (n + 1))
        return st, txt

    def attuali(self, token):
        """(stato, insieme degli argomenti nostri): stato = ok | morto | errore:<testo>"""
        st, txt = self.con_ritentativi("GET", self.url(token))
        if morto(st, txt):
            return "morto", set()
        if st != 200:
            return "errore:HTTP %s %s" % (st, corto(txt, 100)), set()
        nomi = set()
        try:
            j = json.loads(txt)
            for x in j.get("topic_subscriptions") or j.get("topicSubscriptions") or []:
                n = x.get("topic_name") or x.get("topicName") or ""
                if NS.match(n):
                    nomi.add(n)
        except ValueError:
            return "errore:risposta non leggibile", set()
        return "ok", nomi

    def aggiungi(self, token, nome):
        return self.con_ritentativi("POST", self.url(token, "?topic_name=" + urllib.parse.quote(nome, safe="")), {})

    def togli(self, token, nome):
        return self.con_ritentativi("DELETE", self.url(token, "/" + urllib.parse.quote(nome, safe="")))


def allinea(g, sub, esegui):
    """Allinea UN dispositivo. Ritorna un dizionario con l'esito."""
    tok, voluti = sub["id"], argomenti_di(sub)
    r = {"id": tok, "voluti": len(voluti), "agg": 0, "tol": 0, "stato": "ok"}
    stato, attuali = g.attuali(tok)
    if stato != "ok":
        r["stato"] = stato if stato == "morto" else "errore"
        r["errore"] = "" if stato == "morto" else stato[7:]
        return r
    da_agg, da_tol = sorted(voluti - attuali), sorted(attuali - voluti)
    r["agg"], r["tol"] = len(da_agg), len(da_tol)
    r["nomi_agg"], r["nomi_tol"] = da_agg, da_tol
    if not esegui or not (da_agg or da_tol):
        return r
    for cosa, nome in [("add", n) for n in da_agg] + [("del", n) for n in da_tol]:
        st, txt = g.aggiungi(tok, nome) if cosa == "add" else g.togli(tok, nome)
        if st in (200, 409) or (cosa == "del" and st == 404 and not morto(st, txt)):
            continue
        if morto(st, txt):
            r["stato"] = "morto"
            return r
        r["stato"], r["errore"] = "errore", "%s %s: HTTP %s %s" % (cosa, nome, st, corto(txt, 100))
        return r
    for _ in range(4):   # ricontrollo (l'elenco di Google puo' impiegare qualche secondo ad aggiornarsi)
        time.sleep(2)
        stato, attuali = g.attuali(tok)
        if stato == "ok" and attuali == voluti:
            r["verificato"] = True
            return r
    r["verificato"] = False
    return r


def nomi_brevi(nomi, n=6):
    """I nomi degli argomenti (canali e codici dei tornei, niente di riservato), al massimo n."""
    return ", ".join(nomi[:n]) + (" +%d altri" % (len(nomi) - n) if len(nomi) > n else "")


def rimuovi_dall_archivio(ids):
    """Toglie dall'archivio iscritti questi token (a gruppi da 200, come fa l'invio dei token morti). Ritorna (tolti, errori)."""
    tolti, errori = 0, 0
    for k in range(0, len(ids), 200):
        blocco = ids[k:k + 200]
        req = urllib.request.Request(os.environ["SUBS_URL"].rstrip("/") + "/remove", data=json.dumps({"ids": blocco}).encode("utf-8"), method="POST",
                                     headers={"Authorization": "Bearer " + os.environ["SUBS_TOKEN"], "Content-Type": "text/plain", "User-Agent": UA})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8") or "{}")
            tolti += int(r.get("removed", len(blocco)))
        except Exception as ex:
            errori += 1
            print("  pulizia dell'archivio non riuscita per un gruppo di %d: %s" % (len(blocco), corto(ex, 100)))
    return tolti, errori


def main():
    for k in ("FCM_SERVICE_ACCOUNT", "SUBS_URL", "SUBS_TOKEN"):
        if not os.environ.get(k):
            print("Manca %s (segreto o variabile del repo)." % k)
            return 1
    esegui = (os.environ.get("RIALL_MODO") or "controlla").lower() == "esegui"
    rimuovi = (os.environ.get("RIALL_RIMUOVI_MORTI") or "no").lower() == "si"
    try:
        massimo = max(1, min(int(os.environ.get("RIALL_MAX") or 1000), 20000))
    except ValueError:
        massimo = 1000
    chiave = json.loads(os.environ["FCM_SERVICE_ACCOUNT"])
    print("RIALLINEAMENTO ARGOMENTI FIREBASE - modo: %s" % ("ESEGUI (aggiunge e toglie argomenti)" if esegui else "CONTROLLA (non scrive niente su Google)"))
    print("Progetto Firebase: %s | account di servizio: %s | al massimo %d dispositivi\n" % (chiave["project_id"], chiave.get("client_email", "?"), massimo))
    subs = elenco_iscrizioni()
    subs.sort(key=lambda s: s.get("t") or 0, reverse=True)
    print("Archivio: %d iscrizioni Firebase (%d con scelte attive)." % (len(subs), len([s for s in subs if s.get("c") or s.get("h") or s.get("f")])))
    if len(subs) > massimo:
        print("Attenzione: ne controllo solo %d (i piu' recenti): rilancia alzando il massimo se serve." % massimo)
    subs = subs[:massimo]
    g = Google(fcm_access_token(), chiave["project_id"])
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=PARALLELE) as ex:
        esiti = list(ex.map(lambda s: allinea(g, s, esegui), subs))
    durata = time.time() - t0

    ok = [e for e in esiti if e["stato"] == "ok" and not e["agg"] and not e["tol"]]
    diff = [e for e in esiti if e["stato"] == "ok" and (e["agg"] or e["tol"])]
    morti = [e for e in esiti if e["stato"] == "morto"]
    errori = [e for e in esiti if e["stato"] == "errore"]
    non_verificati = [e for e in diff if esegui and e.get("verificato") is False]
    for e in (diff + errori)[:25]:
        riga = "  dispositivo ...%s | voluti %d | da aggiungere %d%s, da togliere %d%s" % (
            e["id"][-6:], e["voluti"], e["agg"], " (%s)" % nomi_brevi(e["nomi_agg"]) if e.get("nomi_agg") else "", e["tol"], " (%s)" % nomi_brevi(e["nomi_tol"]) if e.get("nomi_tol") else "")
        if esegui:
            riga += " | %s" % ("allineato e verificato" if e.get("verificato") else "NON verificato" if e.get("verificato") is False else "")
        if e["stato"] == "errore":
            riga = "  dispositivo ...%s | ERRORE: %s" % (e["id"][-6:], corto(e.get("errore", ""), 140))
        print(riga)
    print("\n=========== RISULTATO (%.0f secondi) ===========" % durata)
    print("Dispositivi esaminati: %d" % len(esiti))
    print("  gia' a posto: %d" % len(ok))
    if esegui:
        print("  sistemati: %d (verificati: %d)" % (len(diff), len([e for e in diff if e.get("verificato")])))
    else:
        print("  da sistemare: %d (mancano %d iscrizioni, ne sono di troppo %d)" % (len(diff), sum(e["agg"] for e in diff), sum(e["tol"] for e in diff)))
    print("  non piu' validi (Google non li riconosce, nessuna modifica): %d" % len(morti))
    print("  con errori: %d" % len(errori))
    pulizia_fallita = False
    if morti and rimuovi:
        freno = len(morti) >= 5 and len(morti) / float(len(esiti)) > 0.5
        if freno:
            print("  FRENO DI SICUREZZA: %d dispositivi su %d risultano non validi tutti insieme. Non ne tolgo nessuno dall'archivio: controlla la configurazione di Firebase." % (len(morti), len(esiti)))
        elif not esegui:
            print("  in modo controlla non tolgo niente: con esegui verrebbero tolti dall'archivio %d dispositivi non piu' validi." % len(morti))
        else:
            tolti, err = rimuovi_dall_archivio([e["id"] for e in morti])
            print("  tolti dall'archivio iscritti: %d dispositivi non piu' validi (Google non li riconosce)" % tolti)
            pulizia_fallita = err > 0
    elif morti:
        print("  (i non piu' validi restano nell'archivio: per toglierli rilancia con esegui e «togli non validi» = si)")
    if non_verificati:
        print("  ATTENZIONE: %d non risultano ancora allineati al ricontrollo: rilancia tra qualche minuto." % len(non_verificati))
    if not esegui and diff:
        print("\nPer sistemarli rilancia con modo = esegui.")
    return 1 if (errori or non_verificati or pulizia_fallita) else 0


if __name__ == "__main__":
    sys.exit(main())
