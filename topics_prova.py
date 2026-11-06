#!/usr/bin/env python3
"""PROVA DI FATTIBILITA' degli ARGOMENTI di Firebase (FCM topics).

NON cambia niente del sistema attuale: non tocca l'archivio iscritti, non cambia le scelte di nessuno e non usa nessun canale vero.
Usa solo argomenti di prova (nome che inizia con "prova-") e li toglie alla fine.

Cosa risponde:
  1) Google accetta di iscrivere ai nostri argomenti i token delle notifiche del SITO (browser / app installata)?
  2) Quanto tempo ci mette ogni iscrizione, e cosa succede con tante iscrizioni di fila (per decidere dove farle: Worker o GitHub)?
  3) Un avviso mandato all'argomento arriva davvero sui dispositivi? Subito (A) e dopo 60 secondi (B)?
  4) Si riesce a togliere le iscrizioni di prova?
Usa SOLO i dispositivi che hai appena TOCCATO tu: quelli con scelte attive la cui ultima modifica e' negli ultimi N minuti (di default 20).
Per far "contare" un tuo dispositivo basta aprire il sito, andare nel campanello, spegnere un canale e riaccenderlo (due tocchi: le scelte tornano
come prima). Cosi' la prova non disturba nessun altro e puoi controllare che gli avvisi arrivino proprio a te. Non stampa mai un token intero.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "rAKings-VGC-prova-argomenti"
TOPIC = "prova-fattibilita"
N_MOLTI = 55            # per provare «tante iscrizioni di fila» (un utente puo' avere fino a 50 tornei + canali)
N_PARALLELE = 6         # il Worker puo' tenere 6 chiamate aperte insieme
MAX_DISPOSITIVI = 10    # tetto di sicurezza: la prova non deve disturbare nessuno

_FCM = {}


def fcm_access_token():
    """Chiave di accesso a Google (stesso metodo degli altri script: firma con 'openssl', nessuna libreria da installare)."""
    import base64
    import subprocess
    import tempfile
    if _FCM.get("tok") and time.time() < _FCM["exp"] - 120:
        return _FCM["tok"]
    try:
        info = json.loads(os.environ["FCM_SERVICE_ACCOUNT"])
        key, mail = info["private_key"], info["client_email"]
    except Exception:
        raise RuntimeError("FCM_SERVICE_ACCOUNT non e' valido: va incollato tutto il contenuto del file JSON della chiave di servizio.")
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
        raise RuntimeError("Firma per Firebase non riuscita (chiave di servizio non valida?).")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    form = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": head + "." + claims + "." + b64(sig)}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form,
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        raise RuntimeError("Accesso a Google rifiutato: HTTP %s %s" % (ex.code, ex.read().decode("utf-8", "ignore")[:200]))
    _FCM["tok"], _FCM["exp"] = r["access_token"], now + int(r.get("expires_in", 3600))
    return _FCM["tok"]


def corto(txt, n=230):
    """Una riga sola, SENZA token: le risposte di errore di Google ripetono l'indirizzo con il token dentro, e i registri di questo repo sono pubblici."""
    import re
    t = " ".join(str(txt).split())
    t = re.sub(r"(registrations/)[^\s'\"/]+", r"\1<token>", t)
    t = re.sub(r"[A-Za-z0-9_-]{8,}:APA91[A-Za-z0-9_-]*", "<token>", t)
    return t[:n]


def chiama(metodo, url, access, corpo=None, timeout=30):
    """Una chiamata a Google. Ritorna (codice HTTP, testo, millisecondi). Codice 0 = errore di rete."""
    dati = None if corpo is None else json.dumps(corpo).encode("utf-8")
    hdr = {"Authorization": "Bearer " + access, "Content-Type": "application/json; charset=UTF-8", "User-Agent": UA}
    t0 = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=dati, headers=hdr, method=metodo), timeout=timeout)
        codice, testo = getattr(r, "status", 200), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ex:
        codice, testo = ex.code, ex.read().decode("utf-8", "replace")
    except Exception as ex:
        codice, testo = 0, str(ex)
    return codice, testo, int((time.time() - t0) * 1000)


def elenco_iscrizioni():
    """Legge dall'archivio SOLO le iscrizioni Firebase (a pagine da 1000), come fanno gli altri script. Non scrive niente."""
    base = os.environ["SUBS_URL"].rstrip("/") + "/list"
    hdr = {"Authorization": "Bearer " + os.environ["SUBS_TOKEN"], "User-Agent": UA}
    subs, cursor = [], None
    for _ in range(100):
        q = [("kind", "fcm"), ("limit", "1000")]
        if cursor:
            q.append(("cursor", cursor))
        req = urllib.request.Request(base + "?" + urllib.parse.urlencode(q), headers=hdr)
        dati = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        subs += dati.get("subs") or []
        cursor = dati.get("cursor")
        if not cursor:
            break
    return subs


class Prova:
    def __init__(self, access, progetto):
        self._access0, self.progetto = access, progetto
        self.codifica_iscr = False   # se Google non accetta i «:» del token nell'indirizzo, si passa alla versione codificata

    @property
    def access(self):
        """La chiave di accesso a Google dura 1 ora: si rinnova da sola (serve se si aspetta a lungo prima di mandare gli avvisi)."""
        try:
            return fcm_access_token()
        except Exception:
            return self._access0

    def url_reg(self, token, coda=""):
        t = urllib.parse.quote(token, safe="") if self.codifica_iscr else urllib.parse.quote(token, safe=":")
        return "https://fcm.googleapis.com/v1/projects/%s/registrations/%s/topicSubscriptions%s" % (self.progetto, t, coda)

    def iscrivi(self, token, argomento):
        coda = "?topic_name=" + urllib.parse.quote(argomento, safe="")
        c, t, ms = chiama("POST", self.url_reg(token, coda), self.access, {})
        if c in (400, 404) and not self.codifica_iscr and ":" in token:
            self.codifica_iscr = True   # secondo tentativo con l'indirizzo codificato
            c2, t2, ms2 = chiama("POST", self.url_reg(token, coda), self.access, {})
            if c2 in (200, 409):
                print("  (nota: l'iscrizione e' accettata solo con i «:» del token codificati nell'indirizzo: da ricordare nel progetto)")
                return c2, t2, ms + ms2
            self.codifica_iscr = False
        return c, t, ms

    def elenco(self, token):
        c, t, ms = chiama("GET", self.url_reg(token), self.access)
        nomi = []
        if c == 200:
            try:
                nomi = [x.get("topic_name") or x.get("topicName") or "" for x in (json.loads(t).get("topic_subscriptions") or json.loads(t).get("topicSubscriptions") or [])]
            except ValueError:
                pass
        return c, nomi, t

    def togli(self, token, argomento):
        return chiama("DELETE", self.url_reg(token, "/" + urllib.parse.quote(argomento, safe="")), self.access)

    def invia_token(self, token, titolo, corpo, link):
        """Avviso mandato DIRETTAMENTE al dispositivo (come fa oggi l'invio vero), per confrontarlo con quello via argomento."""
        url = "https://fcm.googleapis.com/v1/projects/%s/messages:send" % self.progetto
        dati = {"title": titolo, "body": corpo}
        if link:
            dati["link"] = link
        msg = {"message": {"token": token, "notification": {"title": titolo, "body": corpo}, "data": dati,
                           "webpush": {"headers": {"Urgency": "high", "TTL": "3600"}}}}
        return chiama("POST", url, self.access, msg)

    def invia(self, argomento, titolo, corpo, link, android_alta=False):
        url = "https://fcm.googleapis.com/v1/projects/%s/messages:send" % self.progetto
        dati = {"title": titolo, "body": corpo}
        if link:
            dati["link"] = link
        msg = {"message": {"topic": argomento, "notification": {"title": titolo, "body": corpo}, "data": dati,
                           "webpush": {"headers": {"Urgency": "high", "TTL": "3600"}}}}
        if android_alta:   # prova: priorita' ALTA di Android sul messaggio all'argomento
            msg["message"]["android"] = {"priority": "HIGH"}
        return chiama("POST", url, self.access, msg)


def ora_ora():
    """L'ora di adesso, in UTC e in ora italiana, per confrontarla con l'ora a cui l'avviso compare sul dispositivo."""
    adesso = time.time()
    utc = time.strftime("%H:%M:%S", time.gmtime(adesso))
    try:
        from zoneinfo import ZoneInfo
        import datetime
        it = datetime.datetime.fromtimestamp(adesso, ZoneInfo("Europe/Rome")).strftime("%H:%M:%S")
        return utc + " UTC (" + it + " ora italiana)", it
    except Exception:
        return utc + " UTC", utc


def ok_iscr(c):
    return c in (200, 409)   # 409 = gia' iscritto: va bene


def main():
    for k in ("FCM_SERVICE_ACCOUNT", "SUBS_URL", "SUBS_TOKEN"):
        if not os.environ.get(k):
            print("Manca %s (segreto o variabile del repo)." % k)
            return 1
    try:
        ultimi = max(1, min(int(os.environ.get("TEST_ULTIMI") or 2), MAX_DISPOSITIVI))
    except ValueError:
        ultimi = 2
    try:
        minuti = max(1, min(int(os.environ.get("TEST_MINUTI") or 20), 1440))
    except ValueError:
        minuti = 20
    molte = (os.environ.get("TEST_MOLTE") or "no").lower() == "si"
    parallele = (os.environ.get("TEST_PARALLELE") or "no").lower() == "si"
    confronto = (os.environ.get("TEST_CONFRONTO") or "no").lower() == "si"
    priorita = (os.environ.get("TEST_PRIORITA") or "no").lower() == "si"
    try:
        attesa_min = max(0, min(int(os.environ.get("TEST_ATTESA") or 0), 180))
    except ValueError:
        attesa_min = 0
    link = (os.environ.get("SITE_URL") or "").strip()
    chiave = json.loads(os.environ["FCM_SERVICE_ACCOUNT"])
    progetto = chiave["project_id"]
    account = chiave.get("client_email", "?")

    print("PROVA ARGOMENTI FIREBASE - non cambia niente del sistema attuale (argomenti di prova «prova-...», tolti alla fine)")
    print("Progetto Firebase: %s | dispositivi: al massimo %d, toccati negli ultimi %d minuti | molte iscrizioni di fila: %s" % (progetto, ultimi, minuti, "SI" if molte else "no"))
    print("Account di servizio usato: %s\n" % account)

    subs = elenco_iscrizioni()
    vivi = [s for s in subs if (s.get("c") or s.get("h") or s.get("f"))]
    vivi.sort(key=lambda s: s.get("t") or 0, reverse=True)
    adesso = time.time() * 1000
    if not vivi:
        print("\nNessun dispositivo con scelte attive nell'archivio: apri il sito sul tuo dispositivo, attiva le notifiche, scegli almeno un canale e rilancia.")
        return 1
    toccati = [s for s in vivi if (s.get("t") or 0) >= adesso - minuti * 60000]
    scelti = toccati[:ultimi]
    print("Archivio: %d iscrizioni Firebase, %d con scelte attive (le altre sono record vuoti, saltate), %d toccate negli ultimi %d minuti." % (len(subs), len(vivi), len(toccati), minuti))
    if not scelti:
        print("\nNessun dispositivo toccato negli ultimi %d minuti: non mando niente a nessuno." % minuti)
        print("Su OGNI tuo dispositivo: apri il sito, campanello, spegni un canale e riaccendilo (due tocchi), poi rilancia entro %d minuti." % minuti)
        return 1
    if len(toccati) > len(scelti):
        print("Attenzione: ci sono %d dispositivi toccati nel periodo, ne uso solo i %d piu' recenti (alza «ultimi» se servono tutti)." % (len(toccati), len(scelti)))
    for i, s in enumerate(scelti, 1):
        mi = (adesso - (s.get("t") or adesso)) / 60000.0
        print("  dispositivo %d: ...%s | %d canali, %d tornei seguiti | ultima modifica %.0f minuti fa" % (
            i, s["id"][-6:], len(s.get("c") or []), len(s.get("f") or []), mi))
    print("  Sono i TUOI? Se il numero non torna con i dispositivi che hai toccato, ferma la prova e rilancia dopo aver rifatto i due tocchi.")

    t0 = time.time()
    access = fcm_access_token()
    print("\nAccesso a Google ottenuto in %d ms (da GitHub: nessun problema; questo tempo conta solo se si facesse nel Worker)." % int((time.time() - t0) * 1000))
    p = Prova(access, progetto)

    problemi = []
    print("\n--- 1) ISCRIZIONE all'argomento «%s» ---" % TOPIC)
    iscritti, tempi, rifiuti = [], [], []
    for i, s in enumerate(scelti, 1):
        c, t, ms = p.iscrivi(s["id"], TOPIC)
        tempi.append(ms)
        stato = "OK" if ok_iscr(c) else "RIFIUTATA"
        extra = " (gia' iscritto)" if c == 409 else ""
        print("  dispositivo %d: HTTP %s %s%s in %d ms%s" % (i, c, stato, extra, ms, "" if ok_iscr(c) else " -> " + corto(t)))
        if ok_iscr(c):
            iscritti.append(s)
        else:
            rifiuti.append(c)
    if not iscritti:
        permessi = [c for c in rifiuti if c == 403]
        print("\nRISULTATO: Google NON ha accettato nessuna iscrizione (vedi l'errore sopra). Non si cambia niente e ci fermiamo qui.")
        if permessi:
            print("\nE' UN PROBLEMA DI PERMESSI, non dei token: all'account di servizio «%s» manca il permesso di gestire le iscrizioni agli argomenti" % account)
            print("(cloudmessaging.topicSubscriptions.*). Il ruolo con cui oggi manda gli avvisi ha solo «cloudmessaging.messages.create».")
            print("Serve un ruolo con i 5 permessi cloudmessaging.topicSubscriptions (create, delete, get, list, update): vedi le istruzioni nel file LEGGIMI_permessi.txt.")
            print("Dopo averlo aggiunto aspetta 2-3 minuti e rilancia la prova.")
        return 1
    c, nomi, _ = p.elenco(iscritti[0]["id"])
    print("  elenco degli argomenti del dispositivo 1 (GET): HTTP %s -> %s" % (c, ", ".join(nomi) if nomi else "(vuoto o non leggibile)"))

    print("\n--- 2) AVVISO all'argomento ---")
    titolo = "Prova tecnica argomenti (ignora)"
    if attesa_min:
        quando, _ = ora_ora()
        print("\n--- ATTESA di %d minuti prima di mandare gli avvisi (adesso: %s) ---" % (attesa_min, quando))
        print("  Lascia il telefono FERMO, a schermo spento. Gli avvisi partiranno da soli: guarda l'ora a cui compaiono, e l'ora di invio scritta nel testo.")
        time.sleep(attesa_min * 60)

    def manda_diretti(etichetta, quando_dopo):
        for i, d in enumerate(iscritti, 1):
            quando, breve = ora_ora()
            c, t, ms = p.invia_token(d["id"], titolo + " - " + etichetta, "Avviso " + etichetta + " DIRETTO al dispositivo: inviato alle " + breve + ". Controlla anche la cronologia (campanella).", link)
            print("  avviso %s DIRETTO al dispositivo %d (%s): HTTP %s in %d ms, inviato alle %s%s" % (etichetta, i, quando_dopo, c, ms, quando, "" if c == 200 else " -> " + corto(t)))
            if c != 200:
                problemi.append("avviso " + etichetta)

    if priorita:
        print("  PRIORITA': 3 avvisi a distanza di 60 secondi, SENZA un avviso diretto prima che sveglia il telefono:")
        print("     P1 = via argomento, come ora   |   P2 = via argomento con priorita' ALTA di Android   |   D3 = diretto (controllo)")
        quando, breve = ora_ora()
        c, t, ms = p.invia(TOPIC, titolo + " - P1", "Avviso P1 (argomento, come ora): inviato alle " + breve + ".", link)
        print("  avviso P1 (argomento, come ora): HTTP %s in %d ms, inviato alle %s%s" % (c, ms, quando, "" if c == 200 else " -> " + corto(t)))
        if c != 200:
            problemi.append("avviso P1")
        print("  aspetto 60 secondi...")
        time.sleep(60)
        quando, breve = ora_ora()
        c, t, ms = p.invia(TOPIC, titolo + " - P2", "Avviso P2 (argomento, priorita' ALTA): inviato alle " + breve + ".", link, android_alta=True)
        print("  avviso P2 (argomento, priorita' ALTA di Android): HTTP %s in %d ms, inviato alle %s%s" % (c, ms, quando, "" if c == 200 else " -> " + corto(t)))
        if c != 200:
            problemi.append("avviso P2")
        print("  aspetto 60 secondi...")
        time.sleep(60)
        manda_diretti("D3", "controllo")
    elif confronto:
        print("  CONFRONTO: stessi avvisi mandati in due modi, uno via argomento (A, B) e uno diretto (D1, D2), a distanza di 30 secondi.")
        manda_diretti("D1", "subito")
    if not priorita:
        quando, breve = ora_ora()
        c, t, ms = p.invia(TOPIC, titolo + " - A", "Avviso A (via argomento): inviato alle " + breve + " (subito dopo l'iscrizione). Controlla anche la cronologia (campanella).", link)
        print("  avviso A (via argomento, subito dopo l'iscrizione): HTTP %s in %d ms, inviato alle %s%s" % (c, ms, quando, "" if c == 200 else " -> " + corto(t)))
        if c != 200:
            problemi.append("avviso A")
        if confronto:
            print("  aspetto 30 secondi...")
            time.sleep(30)
            manda_diretti("D2", "30 secondi dopo")
            print("  aspetto 30 secondi...")
            time.sleep(30)
        else:
            print("  aspetto 60 secondi...")
            time.sleep(60)
        quando, breve = ora_ora()
        c, t, ms = p.invia(TOPIC, titolo + " - B", "Avviso B (via argomento): inviato alle " + breve + " (60 secondi dopo). Controlla anche la cronologia (campanella).", link)
        print("  avviso B (via argomento, 60 secondi dopo): HTTP %s in %d ms, inviato alle %s%s" % (c, ms, quando, "" if c == 200 else " -> " + corto(t)))
        if c != 200:
            problemi.append("avviso B")

    molti = []
    if molte:
        print("\n--- 3) TANTE ISCRIZIONI DI FILA (%d argomenti sul dispositivo 1) ---" % N_MOLTI)
        stati, t1 = {}, time.time()
        for k in range(1, N_MOLTI + 1):
            nome = "prova-molti-%02d" % k
            c, t, ms = p.iscrivi(iscritti[0]["id"], nome)
            stati[c] = stati.get(c, 0) + 1
            if ok_iscr(c):
                molti.append(nome)
            elif c == 429:
                time.sleep(2)
        durata = time.time() - t1
        print("  esito: %s | tempo totale %.1f s (%.0f ms a iscrizione)" % (", ".join("HTTP %s: %d" % (a, b) for a, b in sorted(stati.items())), durata, 1000 * durata / N_MOLTI))
        c, nomi, _ = p.elenco(iscritti[0]["id"])
        print("  il dispositivo 1 risulta iscritto a %d argomenti di prova (GET: HTTP %s)" % (len([n for n in nomi if n.startswith("prova-")]), c))
        if stati.get(429):
            problemi.append("%d iscrizioni su %d rifiutate con 429 (troppe richieste)" % (stati[429], N_MOLTI))

    if parallele:
        from concurrent.futures import ThreadPoolExecutor
        print("\n--- 3b) ISCRIZIONI IN PARALLELO (%d argomenti, %d alla volta, come farebbe il Worker) ---" % (N_MOLTI, N_PARALLELE))
        nomi_par = ["prova-par-%02d" % k for k in range(1, N_MOLTI + 1)]
        t1 = time.time()
        with ThreadPoolExecutor(max_workers=N_PARALLELE) as ex:
            risultati = list(ex.map(lambda nome: (nome, p.iscrivi(iscritti[0]["id"], nome)), nomi_par))
        durata = time.time() - t1
        stati = {}
        for nome, (c, t, ms) in risultati:
            stati[c] = stati.get(c, 0) + 1
            if ok_iscr(c):
                molti.append(nome)
        lenti = max((ms for _, (c, t, ms) in risultati), default=0)
        print("  esito: %s | tempo totale %.1f s (%.0f ms a iscrizione in media, la piu' lenta %d ms)" % (
            ", ".join("HTTP %s: %d" % (a, b) for a, b in sorted(stati.items())), durata, 1000 * durata / N_MOLTI, lenti))
        if stati.get(429):
            problemi.append("in parallelo %d iscrizioni su %d rifiutate con 429 (troppe richieste)" % (stati[429], N_MOLTI))
        altri = {c: n for c, n in stati.items() if c not in (200, 409, 429)}
        if altri:
            problemi.append("in parallelo, risposte inattese: %s" % ", ".join("HTTP %s x%d" % (c, n) for c, n in sorted(altri.items())))
        c, nomi, _ = p.elenco(iscritti[0]["id"])
        print("  il dispositivo 1 risulta iscritto a %d argomenti di prova in totale (GET: HTTP %s)" % (len([n for n in nomi if n.startswith("prova-")]), c))

    print("\n--- 4) PULIZIA (si tolgono tutte le iscrizioni di prova) ---")
    tolte = falliti = 0
    for s in iscritti:
        elenco = [TOPIC] + (molti if s is iscritti[0] else [])
        for nome in elenco:
            c, t, ms = p.togli(s["id"], nome)
            if c in (200, 404):
                tolte += 1
            else:
                falliti += 1
                print("  non tolta «%s» dal dispositivo ...%s: HTTP %s %s" % (nome, s["id"][-6:], c, corto(t, 120)))
    c, nomi, _ = p.elenco(iscritti[0]["id"])
    resto = [n for n in nomi if n.startswith("prova-")]
    attesa = 0
    while resto and attesa < 12:   # l'elenco di Google puo' mostrare ancora per qualche secondo un argomento appena tolto: si riguarda ogni secondo
        time.sleep(1)
        attesa += 1
        c, nomi, _ = p.elenco(iscritti[0]["id"])
        resto = [n for n in nomi if n.startswith("prova-")]
    if attesa and not resto:
        print("  nota: l'elenco di Google ha impiegato circa %d secondi ad aggiornarsi dopo la cancellazione (le cancellazioni erano gia' riuscite)" % attesa)
    print("  iscrizioni tolte: %d, non riuscite: %d | argomenti di prova rimasti sul dispositivo 1: %d" % (tolte, falliti, len(resto)))
    if falliti or resto:
        problemi.append("pulizia incompleta (relancia la prova per riprovare a toglierle)")

    print("\n=========== RISULTATO ===========")
    print("Iscrizione dei token del sito: %d dispositivi su %d accettati da Google | tempo medio %d ms a iscrizione." % (len(iscritti), len(scelti), sum(tempi) // max(1, len(tempi))))
    print("Avvisi all'argomento: %s." % ("accettati da Google" if "avviso A" not in problemi and "avviso B" not in problemi else "NON accettati (vedi sopra)"))
    print("Problemi: %s." % ("; ".join(problemi) if problemi else "nessuno"))
    print("\nORA CONTROLLA TU sui tuoi dispositivi (PC, Android, iPhone se ce l'hai):")
    print("  - Ti e' arrivato l'avviso A «Prova tecnica argomenti (ignora) - A»?  E il B (dopo 60 secondi)?")
    if priorita:
        print("  PRIORITA': per il telefono scrivimi a che ora e' COMPARSO ognuno di questi 3 (confrontando con l'ora di invio nel testo): P1 (argomento come ora), P2 (argomento priorita' alta), D3 (diretto).")
        print("  Se P2 compare subito e P1 no, la priorita' alta risolve il ritardo degli argomenti. Se P1 e P2 compaiono tardi e D3 subito, non cambia niente.")
    elif confronto:
        print("  CONFRONTO: scrivimi per ogni dispositivo (PC e telefono) quali di questi 4 sono arrivati e a che ora: D1 (diretto), A (argomento), D2 (diretto), B (argomento).")
        print("  Se il telefono perde anche i DIRETTI, e' il telefono (non gli argomenti). Se perde solo A e B, sono gli argomenti.")
    else:
        print("  - Scrivimi per ogni dispositivo: A si/no, B si/no, e a che ora sono comparse (confrontale con l'ora di invio scritta sopra).")
    print("  - Se ti sembra di aver perso un avviso, controlla la cronologia nel sito (campanella): li elenca anche se non li hai visti comparire.")
    print("  (Arriva solo ai dispositivi elencati sopra, cioe' a quelli che hai toccato tu.)")
    return 1 if ("avviso A" in problemi or "avviso B" in problemi) else 0


if __name__ == "__main__":
    sys.exit(main())
